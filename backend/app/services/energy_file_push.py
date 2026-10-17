"""Validated, idempotent workbook delivery over an authenticated SSH connection."""
import datetime as dt
import hashlib
import json
from uuid import uuid4

from sqlalchemy import case, text, update
from sqlalchemy.dialects.postgresql import insert

from app.services.energy_import import MAX_WORKBOOK_BYTES, parse_workbook
from app.services.energy_reporting import records_to_json

STATE = 'file-push'
WORKER = 'energy-file-push'


def validate_modified(modified):
    now = dt.datetime.now(dt.timezone.utc)
    if modified.tzinfo is None or not dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc) <= modified <= now + dt.timedelta(minutes=5):
        raise ValueError('Workbook save time is invalid; check the source computer clock')


def source_key():
    from app.core.config import settings
    return hashlib.sha256(('file-push:' + settings.ENERGY_FILE_PUSH_SOURCE_ID).encode()).hexdigest()


def configuration_errors():
    from app.core.config import settings
    errors = []
    if settings.ENERGY_ONEDRIVE_ENABLED:
        errors.append('Disable Graph synchronization before enabling file delivery')
    if not settings.ENERGY_FILE_PUSH_SOURCE_ID.strip():
        errors.append('Set a stable file delivery source ID')
    return errors


def push_status(db):
    from app.core.config import settings
    from app.models.energy import EnergySyncState
    from app.services.energy_sync import utcnow
    state = db.get(EnergySyncState, STATE)
    if state and state.source_key != source_key():
        state = None
    errors = configuration_errors()
    from app.models.response import WorkerHeartbeat
    heartbeat = db.get(WorkerHeartbeat, WORKER)
    agent_online = bool(heartbeat and (utcnow() - heartbeat.updated_at).total_seconds() < 180)
    fresh = bool(state and state.last_success_at and
                 (utcnow() - state.last_success_at).total_seconds() <= settings.ENERGY_FILE_PUSH_INTERVAL_SECONDS * 2 + 300)
    pending = bool(state and state.requested_at)
    request_state = ('delayed' if (utcnow() - state.requested_at).total_seconds() >= 180 else 'waiting') if pending else 'idle'
    return {'enabled': True, 'transport': 'ssh_push', 'configured': not errors,
            'configuration_errors': errors, 'connected': bool(fresh and not errors and state.active_revision_id),
            'stale': not fresh or bool(errors), 'worker_healthy': fresh,
            'agent_online': agent_online, 'agent_last_seen_at': heartbeat.updated_at if heartbeat else None,
            'pending': pending, 'request_state': request_state,
            'interval_seconds': settings.ENERGY_FILE_PUSH_INTERVAL_SECONDS,
            **{field: getattr(state, field) if state else None for field in (
                'source_name', 'source_modified_at', 'last_checked_at', 'last_success_at',
                'last_import_at', 'next_attempt_at', 'last_error_code', 'last_error_message', 'active_revision_id', 'requested_at')}}


def queue_delivery(db):
    from app.core.config import settings
    from app.models.energy import EnergySyncState
    from app.services.energy_sync import utcnow
    if not settings.ENERGY_FILE_PUSH_ENABLED or configuration_errors():
        raise ValueError('File delivery is not configured')
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('energy-import',0))"))
    state = db.get(EnergySyncState, STATE, populate_existing=True)
    if state is None:
        state = EnergySyncState(name=STATE, source_key=source_key())
        db.add(state)
    elif state.source_key != source_key():
        state.source_key = source_key()
        state.active_revision_id = state.remote_etag = state.source_name = state.source_modified_at = None
        state.last_success_at = state.last_import_at = state.next_attempt_at = state.requested_at = None
    now = utcnow()
    if state.requested_at is None or (now - state.requested_at).total_seconds() >= 180:
        state.requested_at = now
    requested_at = state.requested_at
    db.commit()
    return requested_at


def poll_delivery(db):
    """Fixed-key agent heartbeat and server-owned upload decision; never commands."""
    from app.core.config import settings
    from app.models.energy import EnergySyncState
    from app.models.response import WorkerHeartbeat
    from app.services.energy_sync import utcnow
    if not settings.ENERGY_FILE_PUSH_ENABLED or configuration_errors():
        raise ValueError('File delivery is not configured')
    now = utcnow()
    db.execute(insert(WorkerHeartbeat).values(worker_name=WORKER, updated_at=now)
               .on_conflict_do_update(index_elements=['worker_name'], set_={'updated_at': now}))
    state = db.get(EnergySyncState, STATE, populate_existing=True)
    if state and state.source_key != source_key():
        state = None
    due = not state or not state.active_revision_id or not state.last_success_at or bool(state.requested_at)
    if not due:
        due = (now - state.last_success_at).total_seconds() >= settings.ENERGY_FILE_PUSH_INTERVAL_SECONDS
    result = {'outcome': 'poll', 'upload_required': bool(due),
              'request_token': state.requested_at.isoformat() if state and state.requested_at else None,
              'poll_interval_seconds': 60}
    db.commit()
    return result


def read_delivery(stream, header=None):
    """Read one bounded JSON header + exact binary body. No remote paths or commands."""
    header = read_header(stream) if header is None else header
    try:
        size, digest, modified = header['size'], header['sha256'], header['modified_at']
        if type(size) is not int or not 0 < size <= MAX_WORKBOOK_BYTES:
            raise ValueError()
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError()
        modified = dt.datetime.fromisoformat(modified.replace('Z', '+00:00'))
        validate_modified(modified)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValueError('Invalid delivery metadata') from None
    content = stream.read(size + 1)
    if len(content) != size or hashlib.sha256(content).hexdigest() != digest:
        raise ValueError('Incomplete delivery or checksum mismatch')
    return content, modified


def read_header(stream):
    line = stream.readline(2049)
    if len(line) > 2048 or not line.endswith(b'\n'):
        raise ValueError('Invalid delivery header')
    try:
        header = json.loads(line)
        if not isinstance(header, dict):
            raise ValueError()
        return header
    except (ValueError, TypeError):
        raise ValueError('Invalid delivery header') from None


def request_token(header):
    value = header.get('request_token')
    if value is None:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        validate_modified(parsed)
        return parsed
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Invalid refresh acknowledgement') from None


def publish(db, content, modified, acknowledged_request=None):
    from app.core.config import settings
    from app.models.energy import EnergyImport, EnergySourceRevision, EnergySyncState
    from app.services.energy_sync import save_snapshot, utcnow
    if not settings.ENERGY_FILE_PUSH_ENABLED or configuration_errors():
        raise ValueError('Enable file delivery and disable Graph synchronization in the target deployment')
    validate_modified(modified)
    # Browser File.lastModified has millisecond precision. Normalize SSH and
    # browser timestamps alike so the same saved file is safe to send by either.
    modified = modified.replace(microsecond=modified.microsecond // 1000 * 1000)
    # Validate the complete workbook before changing either the active pointer or data.
    records = parse_workbook(content)
    digest, key, now = hashlib.sha256(content).hexdigest(), source_key(), utcnow()
    # Use the same lock as manual and Graph imports. Serializes retries and publishers.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('energy-import',0))"))
    state = db.get(EnergySyncState, STATE, populate_existing=True)
    previous_modified = state.source_modified_at if state and state.source_key == key else None
    if previous_modified:
        previous_modified = previous_modified.replace(microsecond=previous_modified.microsecond // 1000 * 1000)
    if previous_modified and modified < previous_modified:
        raise ValueError('Delivery is older than the active workbook; check OneDrive synchronization and source clock')
    save_snapshot(key, digest, content)
    imported = db.query(EnergyImport).filter_by(content_hash=digest).first()
    if imported is None:
        imported = EnergyImport(import_id=uuid4(), content_hash=digest, source_name='SiteEnergyTracker.xlsx',
                                records=records_to_json(records), record_count=len(records), entered_by=WORKER)
        db.add(imported)
        db.flush()
    revision = db.query(EnergySourceRevision).filter_by(source_key=key, remote_etag=digest).first()
    if revision is None:
        revision = EnergySourceRevision(revision_id=uuid4(), source_key=key, remote_etag=digest,
                                        import_id=imported.import_id, content_hash=digest, source_modified_at=modified)
        db.add(revision)
        db.flush()
    if state is None:
        state = EnergySyncState(name=STATE, source_key=key)
        db.add(state)
    changed = state.source_key != key or state.active_revision_id != revision.revision_id
    state.source_key, state.active_revision_id, state.remote_etag = key, revision.revision_id, digest
    state.source_name, state.source_modified_at = 'SiteEnergyTracker.xlsx', modified
    state.last_checked_at = state.last_success_at = now
    if changed:
        state.last_import_at = now
    state.next_attempt_at = now + dt.timedelta(seconds=settings.ENERGY_FILE_PUSH_INTERVAL_SECONDS)
    state.failure_count = 0
    state.last_error_code = state.last_error_message = None
    db.flush()
    if acknowledged_request is not None:
        # Do not clear a newer request that arrived after the agent's poll.
        db.execute(update(EnergySyncState).where(EnergySyncState.name == STATE).values(
            requested_at=case((EnergySyncState.requested_at <= acknowledged_request, None),
                              else_=EnergySyncState.requested_at)))
    db.commit()
    return {'outcome': 'updated' if changed else 'unchanged', 'sha256': digest, 'records': len(records)}
