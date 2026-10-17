"""Single-source sync, immutable snapshots and last-good report selection."""
import datetime as dt
import hashlib
import os
from pathlib import Path
import tempfile
from uuid import uuid4
from sqlalchemy import case, text, update
from sqlalchemy.dialects.postgresql import insert
from app.core.config import settings
from app.core.db import set_audit_actor
from app.models.energy import EnergyImport, EnergySourceRevision, EnergySyncState
from app.models.response import WorkerHeartbeat
from app.services.energy_import import InvalidEnergyWorkbook, parse_workbook
from app.services.energy_onedrive import GraphWorkbookClient, SyncFailure, configuration_errors, source_key
from app.services.energy_reporting import records_to_json

WORKER = 'energy-onedrive-sync'
STATE = 'onedrive'


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def matching_state(db):
    if settings.ENERGY_FILE_PUSH_ENABLED:
        from app.services.energy_file_push import STATE as file_state, source_key as file_key
        value = db.get(EnergySyncState, file_state)
        return value if value and value.source_key == file_key() else None
    value = db.get(EnergySyncState, STATE)
    return value if value and value.source_key == source_key(settings) else None


def selected_import(db):
    state = matching_state(db)
    if state and state.active_revision_id:
        revision = db.get(EnergySourceRevision, state.active_revision_id)
        return db.get(EnergyImport, revision.import_id)
    if settings.ENERGY_ONEDRIVE_ENABLED or settings.ENERGY_FILE_PUSH_ENABLED:
        return None
    return db.query(EnergyImport).filter(EnergyImport.entered_by.notin_([WORKER, 'energy-file-push'])).order_by(
        EnergyImport.entered_at.desc(), EnergyImport.import_id.desc()).first()


def sync_status(db):
    if settings.ENERGY_FILE_PUSH_ENABLED:
        from app.services.energy_file_push import push_status
        return push_status(db)
    state, now = matching_state(db), utcnow()
    enabled = settings.ENERGY_ONEDRIVE_ENABLED
    errors = configuration_errors(settings) if enabled else []
    heartbeat = db.get(WorkerHeartbeat, WORKER)
    worker_healthy = bool(heartbeat and (now - heartbeat.updated_at).total_seconds() < 300)
    fresh = bool(state and state.last_success_at and
                 (now - state.last_success_at).total_seconds() <= max(120, settings.ENERGY_SYNC_INTERVAL_SECONDS * 3))
    connected = bool(enabled and not errors and state and state.active_revision_id
                     and not state.last_error_code and fresh and worker_healthy)
    return {'enabled': enabled, 'configured': bool(enabled and not errors), 'configuration_errors': errors,
            'connected': connected, 'worker_healthy': worker_healthy,
            'stale': bool(enabled and not connected), 'interval_seconds': settings.ENERGY_SYNC_INTERVAL_SECONDS,
            'pending': bool(state and state.requested_at),
            **{field: getattr(state, field) if state else None for field in (
                'source_name', 'source_modified_at', 'last_checked_at', 'last_success_at',
                'last_import_at', 'next_attempt_at', 'last_error_code', 'last_error_message', 'active_revision_id')}}


def queue_sync(db):
    now = utcnow()
    set_audit_actor(db, None, None)
    db.execute(insert(EnergySyncState).values(name=STATE, source_key=source_key(settings), failure_count=0)
               .on_conflict_do_nothing(index_elements=['name']))
    value = db.get(EnergySyncState, STATE)
    if value.requested_at is None:
        value.requested_at = now
    db.commit()


def snapshot_path(key, digest):
    if len(key) != 64 or len(digest) != 64 or any(c not in '0123456789abcdef' for c in key + digest):
        raise ValueError('Invalid snapshot identity')
    return Path(settings.DOCUMENT_STORAGE_ROOT) / 'energy_sources' / key / (digest + '.xlsx')


def save_snapshot(key, digest, content):
    path = snapshot_path(key, digest)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise SyncFailure('snapshot_integrity_failed', 'An existing source snapshot failed its integrity check')
        return
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.download-')
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _secret():
    if settings.ENERGY_GRAPH_CLIENT_SECRET_FILE:
        try:
            value = Path(settings.ENERGY_GRAPH_CLIENT_SECRET_FILE).read_text().strip()
        except OSError:
            raise SyncFailure('credential_unavailable', 'The worker could not read its protected Graph credential') from None
    else:
        value = settings.ENERGY_GRAPH_CLIENT_SECRET.get_secret_value()
    if not value:
        raise SyncFailure('credential_required', 'Configure the worker application credential on the server')
    return value


def run_sync(db, client=None, now=None):
    """Caller commits heartbeat separately. One transaction holds a worker-only lock."""
    now = now or utcnow()
    if not settings.ENERGY_ONEDRIVE_ENABLED or settings.ENERGY_FILE_PUSH_ENABLED:
        return 'disabled'
    key = source_key(settings)
    if db.get(EnergySyncState, STATE) is None:
        # Make the queue row visible before slow IO, so the first admin refresh
        # is not blocked behind an uncommitted insertion for the whole download.
        set_audit_actor(db, None, None)
        db.execute(insert(EnergySyncState).values(name=STATE, source_key=key, failure_count=0)
                   .on_conflict_do_nothing(index_elements=['name']))
        db.commit()
    if not db.execute(text("SELECT pg_try_advisory_xact_lock(hashtextextended('energy-onedrive-sync',0))")).scalar():
        return 'busy'
    state = db.get(EnergySyncState, STATE, populate_existing=True)
    if state.source_key != key:
        state.source_key, state.active_revision_id, state.remote_etag = key, None, None
        state.source_name = state.source_modified_at = None
        state.last_success_at = state.last_import_at = state.next_attempt_at = None
        state.failure_count = 0
    # An explicit refresh never bypasses Microsoft's Retry-After/backoff.
    if state.next_attempt_at and state.next_attempt_at > now:
        if state.last_error_code or not state.requested_at:
            return 'waiting'
    error = None
    outcome = 'unchanged'
    revision = None
    try:
        errors = configuration_errors(settings)
        if errors:
            raise SyncFailure('configuration_required', 'Complete Graph source configuration and company sign-in before enabling live synchronization')
        version = (client or GraphWorkbookClient(settings, _secret())).fetch(state.remote_etag if state.active_revision_id else None)
        if version is not None:
            records = parse_workbook(version.content)
            digest = hashlib.sha256(version.content).hexdigest()
            save_snapshot(key, digest, version.content)
            db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('energy-import',0))"))
            revision = db.query(EnergySourceRevision).filter_by(source_key=key, remote_etag=version.etag).first()
            if revision is not None and revision.content_hash != digest:
                raise SyncFailure('source_version_mismatch', 'The same Microsoft version returned different content; review the source')
            imported = db.query(EnergyImport).filter_by(content_hash=digest).first()
            if imported is None:
                imported = EnergyImport(import_id=uuid4(), content_hash=digest, source_name=version.name,
                                        records=records_to_json(records), record_count=len(records), entered_by=WORKER)
                db.add(imported)
                db.flush()
            if revision is None:
                revision = EnergySourceRevision(revision_id=uuid4(), source_key=key, remote_etag=version.etag,
                                                import_id=imported.import_id, content_hash=digest,
                                                source_modified_at=version.modified_at)
                db.add(revision)
                db.flush()
            state.active_revision_id, state.remote_etag = revision.revision_id, version.etag
            state.source_name, state.source_modified_at = version.name, version.modified_at
            state.last_import_at = now
            outcome = 'updated'
    except InvalidEnergyWorkbook:
        error = SyncFailure('invalid_workbook', 'Downloaded workbook failed RawData validation; the last valid report is retained')
    except SyncFailure as failure:
        error = failure
    except OSError:
        error = SyncFailure('snapshot_storage_failed', 'The source snapshot could not be retained; the last valid report is retained')
    state.last_checked_at = now
    if error:
        state.failure_count += 1
        state.last_error_code, state.last_error_message = error.code, error.message
        delay = max(error.retry_after, min(3600, settings.ENERGY_SYNC_INTERVAL_SECONDS * 2 ** min(state.failure_count - 1, 6)))
        outcome = error.code
    else:
        state.failure_count = 0
        state.last_error_code = state.last_error_message = None
        state.last_success_at = now
        delay = settings.ENERGY_SYNC_INTERVAL_SECONDS
    state.next_attempt_at = now + dt.timedelta(seconds=delay)
    db.flush()
    # Keep a refresh queued while IO was in progress. Use the database's current value.
    db.execute(update(EnergySyncState).where(EnergySyncState.name == STATE).values(
        requested_at=case((EnergySyncState.requested_at <= now, None), else_=EnergySyncState.requested_at)))
    db.commit()
    return outcome
