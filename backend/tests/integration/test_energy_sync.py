import datetime as dt
import hashlib
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile, ZipInfo
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_ftth_intake_api import api, pytestmark  # noqa: F401


def workbook(closing=90):
    content = BytesIO()
    with ZipFile(content, 'w') as archive:
        # Stable ZIP metadata models resending the same saved file across runs.
        def write(name, value):
            archive.writestr(ZipInfo(name, date_time=(2026, 7, 4, 0, 0, 0)), value)
        write('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="RawData" r:id="r1"/></sheets></workbook>')
        write('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        labels = ''.join(f'<c r="{col}3" t="inlineStr"><is><t>{label}</t></is></c>' for col, label in
                         {'B': 'StartTime', 'C': 'StopTime', 'D': 'SitePowerSource', 'G': 'EkedcStatus', 'S': 'GeneratorStatus'}.items())
        write('xl/worksheets/sheet1.xml', f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="3">{labels}</row><row r="4"><c r="B4"><v>46207</v></c><c r="C4"><v>46207.5</v></c><c r="D4" t="inlineStr"><is><t>PROJN01-grid</t></is></c><c r="E4"><v>100</v></c><c r="F4"><v>{closing}</v></c><c r="G4" t="inlineStr"><is><t>ON</t></is></c></row></sheetData></worksheet>')
    return content.getvalue()


@pytest.fixture
def configured(api, monkeypatch, tmp_path):
    from app.core.config import settings
    from app.core import security
    values = {'ENERGY_ONEDRIVE_ENABLED': True, 'ENVIRONMENT': 'production', 'AUTH_MODE': 'entra',
              'ENERGY_GRAPH_DRIVE_ID': 'test-drive', 'ENERGY_GRAPH_ITEM_ID': 'test-item',
              'DOCUMENT_STORAGE_ROOT': str(tmp_path), 'ENERGY_SYNC_INTERVAL_SECONDS': 60}
    for name in ['ENTRA_TENANT_ID', 'ENTRA_API_CLIENT_ID', 'ENTRA_SPA_CLIENT_ID', 'ENERGY_GRAPH_TENANT_ID', 'ENERGY_GRAPH_CLIENT_ID']:
        values[name] = str(uuid4())
    for name, value in values.items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(security, 'auth_configuration', lambda: {'configured': True, 'mode': 'entra'})
    actor = {'id': str(uuid4()), 'verified': True, 'roles': ['NOC.Admin']}
    monkeypatch.setattr(security, 'validate_token', lambda token: actor.copy())
    client, db = api
    client.headers['Authorization'] = 'Bearer test'
    return client, db, actor


class Source:
    def __init__(self, content, tag='v1', error=None):
        self.content, self.tag, self.error, self.calls = content, tag, error, []

    def fetch(self, previous_etag=None):
        from app.services.energy_onedrive import WorkbookVersion
        self.calls.append(previous_etag)
        if self.error:
            raise self.error
        if previous_etag == self.tag:
            return None
        return WorkbookVersion(self.tag, 'tracker.xlsx', dt.datetime(2026, 7, 4, tzinfo=dt.timezone.utc), self.content)


def test_sync_publish_unchanged_and_reverted_source_version(configured):
    client, db, _ = configured
    from app.services.energy_sync import run_sync, utcnow, snapshot_path, source_key, settings
    from app.models.energy import EnergyImport, EnergySourceRevision, EnergySyncState
    now = utcnow()
    a = Source(workbook(90))
    assert run_sync(db, a, now) == 'updated'
    first = db.get(EnergySyncState, 'onedrive').active_revision_id
    digest = hashlib.sha256(a.content).hexdigest()
    assert snapshot_path(source_key(settings), digest).read_bytes() == a.content
    assert client.get('/api/energy/report', params={'day': '2026-07-04'}).json()['sites'][0]['gridUsed'] == 10
    assert run_sync(db, a, now + dt.timedelta(seconds=61)) == 'unchanged'
    assert a.calls == [None, 'v1']
    assert db.query(EnergyImport).count() == 1 and db.query(EnergySourceRevision).count() == 1
    assert run_sync(db, Source(workbook(80), 'v2'), now + dt.timedelta(seconds=122)) == 'updated'
    assert client.get('/api/energy/report', params={'day': '2026-07-04'}).json()['sites'][0]['gridUsed'] == 20
    assert run_sync(db, a, now + dt.timedelta(seconds=183)) == 'updated'
    assert db.get(EnergySyncState, 'onedrive').active_revision_id == first
    assert db.query(EnergyImport).count() == 2 and db.query(EnergySourceRevision).count() == 2
    assert client.get('/api/energy/report', params={'day': '2026-07-04'}).json()['sites'][0]['gridUsed'] == 10


def test_failure_keeps_last_good_report_and_request_does_not_bypass_throttling(configured):
    client, db, _ = configured
    from app.services.energy_sync import run_sync, utcnow
    from app.services.energy_onedrive import SyncFailure
    from app.models.energy import EnergySyncState, EnergyImport
    now = utcnow()
    assert run_sync(db, Source(workbook()), now) == 'updated'
    assert run_sync(db, Source(b'broken', 'v2'), now + dt.timedelta(seconds=61)) == 'invalid_workbook'
    assert db.query(EnergyImport).count() == 1
    assert client.get('/api/energy/report', params={'day': '2026-07-04'}).status_code == 200
    state = db.get(EnergySyncState, 'onedrive')
    assert state.remote_etag == 'v1' and state.last_error_code == 'invalid_workbook'
    throttled = Source(None, error=SyncFailure('microsoft_throttled', 'Microsoft requested a retry', 600))
    retry = now + dt.timedelta(seconds=122)
    assert run_sync(db, throttled, retry) == 'microsoft_throttled'
    assert client.post('/api/energy/sync').status_code == 202
    assert run_sync(db, throttled, retry + dt.timedelta(seconds=1)) == 'waiting'
    assert len(throttled.calls) == 1
    assert db.get(EnergySyncState, 'onedrive').next_attempt_at == retry + dt.timedelta(seconds=600)
    assert not client.get('/api/energy/status').json()['connected']


def test_snapshot_integrity_and_admin_only_queue_and_download(configured):
    client, db, actor = configured
    from app.services.energy_sync import run_sync, utcnow, snapshot_path
    from app.models.energy import EnergySyncState, EnergySourceRevision
    assert run_sync(db, Source(workbook()), utcnow()) == 'updated'
    revision = db.get(EnergySourceRevision, db.get(EnergySyncState, 'onedrive').active_revision_id)
    url = f'/api/energy/sync/revisions/{revision.revision_id}/download'
    downloaded = client.get(url)
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == revision.content_hash
    actor['roles'] = ['NOC.Viewer']
    assert client.get('/api/energy/status').status_code == 200
    assert client.get(url).status_code == 403
    assert client.post('/api/energy/sync').status_code == 403
    actor['roles'] = ['NOC.Operator']
    assert client.post('/api/energy/sync').status_code == 403
    assert client.get(url).status_code == 403
    actor['roles'] = ['NOC.Admin']
    snapshot_path(revision.source_key, revision.content_hash).write_bytes(b'corrupted')
    assert client.get(url).status_code == 409
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(text('DELETE FROM energy_source_revisions'))


def test_preview_cannot_enable_live_sync_and_manual_import_cannot_override(configured, monkeypatch):
    client, db, _ = configured
    from app.services.energy_sync import run_sync, utcnow
    from app.core.config import settings
    from app.models.energy import EnergySourceRevision
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'development')
    monkeypatch.setattr(settings, 'AUTH_MODE', 'preview')
    source = Source(workbook())
    assert run_sync(db, source, utcnow()) == 'configuration_required'
    assert not source.calls and db.query(EnergySourceRevision).count() == 0
    assert client.post('/api/energy/sync').status_code == 409
    result = client.post('/api/energy/imports', files={'file': ('tracker.xlsx', workbook())})
    assert result.status_code == 409


def test_switching_source_hides_previous_source_until_valid_new_snapshot(configured, monkeypatch):
    client, db, _ = configured
    from app.services.energy_sync import run_sync, utcnow
    from app.core.config import settings
    now = utcnow()
    assert run_sync(db, Source(workbook()), now) == 'updated'
    monkeypatch.setattr(settings, 'ENERGY_GRAPH_ITEM_ID', 'different-source')
    assert client.get('/api/energy/report', params={'day': '2026-07-04'}).status_code == 404
    assert run_sync(db, Source(b'broken'), now + dt.timedelta(seconds=61)) == 'invalid_workbook'
    assert client.get('/api/energy/report', params={'day': '2026-07-04'}).status_code == 404


def test_same_content_new_version_deduplicates_and_reports_worker_freshness(configured, monkeypatch):
    client, db, _ = configured
    from app.services.energy_sync import run_sync, utcnow, WORKER
    from app.models.energy import EnergyImport, EnergySourceRevision
    from app.models.response import WorkerHeartbeat
    from app.core.config import settings
    now = utcnow()
    content = workbook()
    assert run_sync(db, Source(content), now) == 'updated'
    assert run_sync(db, Source(content, 'v2'), now + dt.timedelta(seconds=61)) == 'updated'
    assert db.query(EnergyImport).count() == 1 and db.query(EnergySourceRevision).count() == 2
    assert not client.get('/api/energy/status').json()['connected']
    heartbeat = WorkerHeartbeat(worker_name=WORKER, updated_at=utcnow())
    db.add(heartbeat)
    db.commit()
    assert client.get('/api/energy/status').json()['connected']
    heartbeat.updated_at = utcnow() - dt.timedelta(seconds=301)
    db.commit()
    assert not client.get('/api/energy/status').json()['connected']
    monkeypatch.setattr(settings, 'ENERGY_ONEDRIVE_ENABLED', False)
    paused = client.get('/api/energy/status').json()
    assert paused['mode'] == 'cached_workbook' and not paused['connected']
    assert client.get('/api/energy/report', params={'day': '2026-07-04'}).status_code == 200


def test_refresh_queued_during_download_is_preserved(configured):
    _, db, _ = configured
    from app.services.energy_sync import run_sync, utcnow
    now = utcnow()
    later = now + dt.timedelta(seconds=1)
    class QueueWhileFetching(Source):
        def fetch(self, previous_etag=None):
            db.execute(text("UPDATE energy_sync_state SET requested_at=:later WHERE name='onedrive'"), {'later': later})
            return super().fetch(previous_etag)
    assert run_sync(db, QueueWhileFetching(workbook()), now) == 'updated'
    assert db.execute(text("SELECT requested_at FROM energy_sync_state WHERE name='onedrive'")).scalar() == later
