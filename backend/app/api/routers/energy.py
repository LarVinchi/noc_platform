"""Energy workbook reporting; collector writes deliberately remain a local trial."""
import datetime as dt
import hashlib
import json
from uuid import UUID, uuid4
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from fastapi.responses import Response
from app.core.db import get_db
from app.core.config import settings
from app.core.security import actor_context
from app.models.energy import EnergyImport, EnergyTrialEvent, EnergySourceRevision
from app.services.energy_reporting import make_report, metadata, records_from_json, records_to_json
from app.services.energy_collector import trial_records, trial_coverage
from app.services.energy_import import MAX_WORKBOOK_BYTES, InvalidEnergyWorkbook, parse_workbook
from app.services.energy_sync import selected_import, sync_status, queue_sync, snapshot_path
from app.services.energy_onedrive import configuration_errors
from app.services.energy_onedrive import SyncFailure
from app.services.energy_file_push import publish as publish_delivery, configuration_errors as delivery_errors, queue_delivery

router = APIRouter(prefix='/energy', tags=['Energy operations'])
WAT = dt.timezone(dt.timedelta(hours=1))


def trial_enabled():
    return settings.ENVIRONMENT == 'development' and settings.AUTH_MODE == 'preview'


def latest_import(db):
    return selected_import(db)


def import_info(value):
    return {'id': str(value.import_id), 'source': value.source_name, 'record_count': value.record_count,
            'entered_at': value.entered_at, 'entered_by': value.entered_by}


@router.get('/status')
def status(db: Session = Depends(get_db)):
    latest = latest_import(db)
    synchronization = sync_status(db)
    return {'connected': synchronization['connected'],
            'mode': 'file_push_workbook_sync' if settings.ENERGY_FILE_PUSH_ENABLED else
                    'onedrive_workbook_sync' if synchronization['enabled'] else
                    'cached_workbook' if synchronization['active_revision_id'] else 'manual_workbook_import',
            'sync': synchronization, 'trial_enabled': trial_enabled(),
            'last_import': import_info(latest) if latest else None,
            'metadata': metadata(records_from_json(latest.records), latest.source_name) if latest else None,
            'timezone': 'Africa/Lagos', 'telemetry_connected': False}


@router.post('/imports')
async def import_workbook(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if 'NOC.Admin' not in actor_context.get().get('roles', []):
        raise HTTPException(403, 'Administrator role required to publish workbook imports')
    if settings.ENERGY_ONEDRIVE_ENABLED or settings.ENERGY_FILE_PUSH_ENABLED:
        raise HTTPException(409, 'Disable automatic synchronization before publishing a manual workbook')
    if not file.filename or not file.filename.lower().endswith('.xlsx'):
        raise HTTPException(422, 'Upload the main XLSX tracker containing RawData')
    content = await file.read(MAX_WORKBOOK_BYTES + 1)
    await file.close()
    if len(content) > MAX_WORKBOOK_BYTES:
        raise HTTPException(413, 'Workbook exceeds the 10 MB import limit')
    digest = hashlib.sha256(content).hexdigest()
    try:
        records = await run_in_threadpool(parse_workbook, content)
    except InvalidEnergyWorkbook as exc:
        raise HTTPException(422, str(exc)) from exc
    db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'), {'key': 'energy-import'})
    previous = db.query(EnergyImport).filter_by(content_hash=digest).first()
    if previous:
        return {'outcome': 'already_imported', 'import': import_info(previous)}
    value = EnergyImport(import_id=uuid4(), content_hash=digest, source_name=file.filename.replace('\\','/').split('/')[-1][:200],
                         records=records_to_json(records), record_count=len(records), entered_by=actor_context.get()['id'])
    db.add(value)
    db.commit()
    db.refresh(value)
    return {'outcome': 'imported', 'import': import_info(value)}


@router.post('/deliveries')
async def deliver_local_workbook(file: UploadFile = File(...), modified_at: AwareDatetime = Form(...),
                                 db: Session = Depends(get_db)):
    if 'NOC.Admin' not in actor_context.get().get('roles', []):
        raise HTTPException(403, 'Administrator role required to update the workbook')
    if not settings.ENERGY_FILE_PUSH_ENABLED or delivery_errors():
        raise HTTPException(409, 'Enable file delivery and disable Graph synchronization before updating the local workbook')
    started_at = dt.datetime.now(dt.timezone.utc)
    try:
        if not file.filename or not file.filename.lower().endswith('.xlsx'):
            raise HTTPException(422, 'Choose the main XLSX tracker containing RawData')
        content = await file.read(MAX_WORKBOOK_BYTES + 1)
    finally:
        await file.close()
    if len(content) > MAX_WORKBOOK_BYTES:
        raise HTTPException(413, 'Workbook exceeds the 10 MB import limit')
    try:
        result = await run_in_threadpool(publish_delivery, db, content, modified_at, acknowledged_request=started_at)
    except InvalidEnergyWorkbook as error:
        db.rollback()
        raise HTTPException(422, str(error)) from None
    except ValueError as error:
        db.rollback()
        raise HTTPException(409, str(error)) from None
    except (OSError, SyncFailure):
        db.rollback()
        raise HTTPException(503, 'Workbook could not be stored; the last valid report is retained') from None
    return {**result, 'notice': 'Workbook updated. Reports use the latest valid copy; the hourly job remains enabled.'
            if result['outcome'] == 'updated' else 'This workbook is already current. No duplicate import was created.'}


@router.post('/sync', status_code=202)
def request_sync(db: Session = Depends(get_db)):
    if 'NOC.Admin' not in actor_context.get().get('roles', []):
        raise HTTPException(403, 'Administrator role required to request synchronization')
    if settings.ENERGY_FILE_PUSH_ENABLED:
        if delivery_errors():
            raise HTTPException(409, 'File delivery configuration needs administrator attention')
        requested_at = queue_delivery(db)
        return {'outcome': 'queued', 'requested_at': requested_at,
                'notice': 'Sync requested. The source computer will send the latest workbook, normally within one minute. You can keep viewing the current report.'}
    if not settings.ENERGY_ONEDRIVE_ENABLED or configuration_errors(settings):
        raise HTTPException(409, 'Configure the OneDrive source and company sign-in before requesting synchronization')
    queue_sync(db)
    return {'outcome': 'queued', 'notice': 'The sync worker will check the source; Microsoft retry delays still apply'}


@router.get('/sync/revisions/{revision_id}/download')
def download_source(revision_id: UUID, db: Session = Depends(get_db)):
    if 'NOC.Admin' not in actor_context.get().get('roles', []):
        raise HTTPException(403, 'Administrator role required to download original source snapshots')
    revision = db.get(EnergySourceRevision, revision_id)
    if revision is None:
        raise HTTPException(404, 'Source revision not found')
    try:
        content = snapshot_path(revision.source_key, revision.content_hash).read_bytes()
    except OSError:
        raise HTTPException(503, 'Source snapshot is unavailable') from None
    if hashlib.sha256(content).hexdigest() != revision.content_hash:
        raise HTTPException(409, 'Source snapshot integrity check failed')
    return Response(content, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': f'attachment; filename="energy-source-{revision_id}.xlsx"',
                             'Cache-Control': 'no-store'})


@router.get('/report')
def report(day: dt.date, source: Literal['workbook', 'trial'] = 'workbook', db: Session = Depends(get_db)):
    if not dt.date(2000, 1, 2) <= day <= dt.datetime.now(WAT).date():
        raise HTTPException(422, 'Report date must be between 2000-01-02 and today in Lagos')
    if source == 'trial':
        if not trial_enabled():
            raise HTTPException(409, 'Collector trial reports are available only in local preview')
        events = db.query(EnergyTrialEvent).order_by(EnergyTrialEvent.site, EnergyTrialEvent.revision).all()
        records = trial_records(events)
        provenance = {'source': 'Isolated collector trial', 'import': None}
    else:
        value = latest_import(db)
        if value is None:
            raise HTTPException(404, 'Import the RawData tracker before opening workbook reports')
        records = records_from_json(value.records)
        provenance = {'source': value.source_name, 'import': import_info(value)}
    return {**make_report(records, day.isoformat()), **provenance, 'mode': source,
            'trial_coverage': trial_coverage(events, day.isoformat()) if source == 'trial' else None,
            'telemetry_connected': False, 'notice': 'Unaccounted time is not downtime: all sites have batteries.'}


class Observation(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    request_key: UUID
    expected_revision: int = Field(ge=0)
    effective_at: AwareDatetime
    grid: Literal['on', 'off', 'unknown']
    gen: Literal['on', 'off', 'unknown']
    grid_balance: float | None = Field(default=None, ge=0, le=10000000, allow_inf_nan=False)
    diesel_litres: float | None = Field(default=None, ge=0, le=100000, allow_inf_nan=False)
    comment: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def valid_time(self):
        if not dt.datetime(2000, 1, 2, tzinfo=dt.timezone.utc) <= self.effective_at <= dt.datetime.now(dt.timezone.utc):
            raise ValueError('Observation time must be in the past and after 2000-01-02')
        return self


def event_info(event):
    return {'id': str(event.event_id), 'site': event.site, 'revision': event.revision, 'effective_at': event.effective_at,
            'observation': event.observation, 'entered_by': event.entered_by, 'entered_at': event.entered_at}


@router.get('/trial/{site}')
def trial_state(site: Literal['PROJN01', 'LEKKP01', 'ADEMP01'], db: Session = Depends(get_db)):
    if not trial_enabled():
        raise HTTPException(409, 'Collector trial is available only in local preview')
    events = db.query(EnergyTrialEvent).filter_by(site=site).order_by(EnergyTrialEvent.revision.desc()).limit(50).all()
    return {'revision': events[0].revision if events else 0, 'events': [event_info(e) for e in events],
            'notice': 'Trial entries never modify Excel or the operational workbook reports.'}


@router.post('/trial/{site}')
def observe(site: Literal['PROJN01', 'LEKKP01', 'ADEMP01'], data: Observation, db: Session = Depends(get_db)):
    if not trial_enabled():
        raise HTTPException(409, 'Collector trial is available only in local preview')
    if site != 'PROJN01' and data.diesel_litres is not None:
        raise HTTPException(422, 'Gas consumption is not tracked at this site')
    payload = data.model_dump(mode='json', exclude={'request_key', 'expected_revision'})
    payload['effective_at'] = data.effective_at.astimezone(dt.timezone.utc).isoformat()
    digest = hashlib.sha256(json.dumps({'site': site, **payload}, sort_keys=True).encode()).hexdigest()
    # Lock retry identity, then site state. Prevent duplicate requests and stale-tab overwrites.
    for key in (f'energy-request:{data.request_key}', f'energy-trial:{site}'):
        db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'), {'key': key})
    existing = db.query(EnergyTrialEvent).filter_by(request_key=data.request_key).first()
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(409, 'This request was already submitted with different details')
        return {'outcome': 'already_recorded', 'event': event_info(existing)}
    previous = db.query(EnergyTrialEvent).filter_by(site=site).order_by(EnergyTrialEvent.revision.desc()).first()
    revision = previous.revision if previous else 0
    if revision != data.expected_revision:
        raise HTTPException(409, 'Site state changed; refresh before submitting')
    if previous and data.effective_at <= previous.effective_at:
        raise HTTPException(422, 'Trial observations must follow the previous event; corrections require the later review workflow')
    value = EnergyTrialEvent(event_id=uuid4(), request_key=data.request_key, request_hash=digest, site=site,
                             revision=revision + 1, effective_at=data.effective_at, observation=payload,
                             entered_by=actor_context.get()['id'])
    db.add(value)
    db.commit()
    db.refresh(value)
    return {'outcome': 'recorded', 'event': event_info(value)}
