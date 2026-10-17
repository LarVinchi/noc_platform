import datetime as dt
import pytest

from test_energy_sync import configured, workbook  # noqa: F401
from test_ftth_intake_api import api, pytestmark  # noqa: F401


@pytest.fixture
def delivery(configured, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, 'ENERGY_ONEDRIVE_ENABLED', False)
    monkeypatch.setattr(settings, 'ENERGY_FILE_PUSH_ENABLED', True)
    return configured


def test_delivery_retries_replace_active_dataset_without_duplicate_rows(delivery):
    client, db, _ = delivery
    from app.services.energy_file_push import publish
    from app.models.energy import EnergyImport, EnergySourceRevision
    saved = dt.datetime(2026, 7, 4, tzinfo=dt.timezone.utc)
    assert publish(db, workbook(90), saved)['outcome'] == 'updated'
    assert publish(db, workbook(90), saved)['outcome'] == 'unchanged'
    assert db.query(EnergyImport).count() == db.query(EnergySourceRevision).count() == 1
    assert publish(db, workbook(80), saved + dt.timedelta(hours=1))['outcome'] == 'updated'
    report = lambda: client.get('/api/energy/report', params={'day': '2026-07-04'}).json()
    assert report()['sites'][0]['gridUsed'] == 20
    # A deliberate saved revert selects the original data without inserting it again.
    assert publish(db, workbook(90), saved + dt.timedelta(hours=2))['outcome'] == 'updated'
    assert report()['sites'][0]['gridUsed'] == 10
    assert db.query(EnergyImport).count() == db.query(EnergySourceRevision).count() == 2
    state = client.get('/api/energy/status').json()
    assert state['mode'] == 'file_push_workbook_sync' and state['connected']
    assert state['sync']['transport'] == 'ssh_push'
    assert client.post('/api/energy/sync').status_code == 202
    assert client.post('/api/energy/imports', files={'file': ('tracker.xlsx', workbook())}).status_code == 409


def test_invalid_and_out_of_order_deliveries_keep_last_good_data(delivery):
    client, db, _ = delivery
    from app.services.energy_file_push import publish
    from app.services.energy_import import InvalidEnergyWorkbook
    from app.models.energy import EnergyImport
    saved = dt.datetime(2026, 7, 4, tzinfo=dt.timezone.utc)
    publish(db, workbook(90), saved)
    with pytest.raises(InvalidEnergyWorkbook):
        publish(db, b'broken', saved + dt.timedelta(hours=1))
    with pytest.raises(ValueError, match='older'):
        publish(db, workbook(80), saved - dt.timedelta(hours=1))
    assert db.query(EnergyImport).count() == 1
    assert client.get('/api/energy/report', params={'day': '2026-07-04'}).json()['sites'][0]['gridUsed'] == 10


def test_delivery_freshness_source_switch_and_conflicting_configuration(delivery, monkeypatch):
    client, db, _ = delivery
    from app.core.config import settings
    from app.services.energy_file_push import publish
    from app.services.energy_sync import utcnow
    from app.models.energy import EnergySyncState
    publish(db, workbook(), utcnow())
    db.get(EnergySyncState, 'file-push').last_success_at = utcnow() - dt.timedelta(hours=3)
    db.commit()
    assert not client.get('/api/energy/status').json()['connected']
    assert client.get('/api/energy/report', params={'day': '2026-07-04'}).status_code == 200
    monkeypatch.setattr(settings, 'ENERGY_FILE_PUSH_SOURCE_ID', 'other-tracker')
    assert client.get('/api/energy/report', params={'day': '2026-07-04'}).status_code == 404
    monkeypatch.setattr(settings, 'ENERGY_ONEDRIVE_ENABLED', True)
    with pytest.raises(ValueError, match='disable Graph'):
        publish(db, workbook(), utcnow())


def test_disabled_delivery_is_not_mistaken_for_a_manual_import(delivery, monkeypatch):
    client, db, _ = delivery
    from app.core.config import settings
    from app.services.energy_file_push import publish
    from app.services.energy_sync import utcnow
    publish(db, workbook(), utcnow())
    monkeypatch.setattr(settings, 'ENERGY_FILE_PUSH_ENABLED', False)
    assert client.get('/api/energy/report', params={'day': '2026-07-04'}).status_code == 404


def test_browser_update_and_hourly_upload_share_deduplication_and_timestamp_precision(delivery):
    client, db, _ = delivery
    from app.services.energy_file_push import publish
    from app.models.energy import EnergyImport, EnergySourceRevision
    saved = dt.datetime(2026, 7, 4, 12, 0, 0, 123456, tzinfo=dt.timezone.utc)
    publish(db, workbook(90), saved)
    # Browser timestamps are rounded to milliseconds; SSH sends microseconds.
    response = client.post('/api/energy/deliveries', files={'file': ('tracker.xlsx', workbook(90))},
                           data={'modified_at': saved.replace(microsecond=123000).isoformat()})
    assert response.status_code == 200, response.text
    assert response.json()['outcome'] == 'unchanged'
    response = client.post('/api/energy/deliveries', files={'file': ('tracker.xlsx', workbook(80))},
                           data={'modified_at': (saved + dt.timedelta(hours=1)).isoformat()})
    assert response.status_code == 200 and response.json()['outcome'] == 'updated'
    assert client.get('/api/energy/report', params={'day': '2026-07-04'}).json()['sites'][0]['gridUsed'] == 20
    assert publish(db, workbook(80), saved + dt.timedelta(hours=1))['outcome'] == 'unchanged'
    assert db.query(EnergyImport).count() == db.query(EnergySourceRevision).count() == 2


def test_browser_update_rejects_invalid_stale_and_oversized_files(delivery):
    client, db, _ = delivery
    from app.services.energy_file_push import publish
    from app.models.energy import EnergyImport
    saved = dt.datetime(2026, 7, 4, 12, tzinfo=dt.timezone.utc)
    publish(db, workbook(90), saved)
    def send(content, modified=saved.isoformat(), name='tracker.xlsx'):
        return client.post('/api/energy/deliveries', files={'file': (name, content)}, data={'modified_at': modified})
    assert send(b'broken').status_code == 422
    assert send(workbook(80), (saved - dt.timedelta(hours=1)).isoformat()).status_code == 409
    assert send(workbook(), '2999-01-01T00:00:00Z').status_code == 409
    assert send(workbook(), '2026-07-04T00:00:00').status_code == 422
    assert send(workbook(), name='tracker.csv').status_code == 422
    assert send(b'x' * (10 * 1024 * 1024 + 1)).status_code == 413
    assert db.query(EnergyImport).count() == 1
    assert client.get('/api/energy/report', params={'day': '2026-07-04'}).json()['sites'][0]['gridUsed'] == 10


def test_browser_update_requires_admin_and_file_delivery_mode(delivery, monkeypatch):
    client, db, actor = delivery
    from app.core.config import settings
    from app.models.energy import EnergyImport
    def send():
        return client.post('/api/energy/deliveries', files={'file': ('tracker.xlsx', workbook())},
                           data={'modified_at': '2026-07-04T00:00:00Z'})
    for role in ['NOC.Viewer', 'NOC.Operator']:
        actor['roles'] = [role]
        assert send().status_code == 403
    actor['roles'] = ['NOC.Admin']
    monkeypatch.setattr(settings, 'ENERGY_FILE_PUSH_ENABLED', False)
    assert send().status_code == 409
    monkeypatch.setattr(settings, 'ENERGY_FILE_PUSH_ENABLED', True)
    monkeypatch.setattr(settings, 'ENERGY_ONEDRIVE_ENABLED', True)
    assert send().status_code == 409
    assert db.query(EnergyImport).count() == 0


def test_web_refresh_is_queued_for_agent_and_unchanged_upload_acknowledges_it(delivery):
    client, db, _ = delivery
    from app.services.energy_file_push import publish, poll_delivery
    from app.models.energy import EnergyImport
    saved = dt.datetime(2026, 7, 4, tzinfo=dt.timezone.utc)
    publish(db, workbook(), saved)
    assert not poll_delivery(db)['upload_required']
    assert client.post('/api/energy/sync').status_code == 202
    status = client.get('/api/energy/status').json()['sync']
    assert status['pending'] and status['agent_online']
    request = poll_delivery(db)
    assert request['upload_required'] and request['request_token']
    # Repeated clicks coalesce instead of moving the acknowledgement target.
    assert client.post('/api/energy/sync').status_code == 202
    assert poll_delivery(db)['request_token'] == request['request_token']
    acknowledged = dt.datetime.fromisoformat(request['request_token'])
    assert publish(db, workbook(), saved, acknowledged_request=acknowledged)['outcome'] == 'unchanged'
    assert not client.get('/api/energy/status').json()['sync']['pending']
    assert not poll_delivery(db)['upload_required']
    assert db.query(EnergyImport).count() == 1


def test_agent_preserves_newer_requests_and_uploads_when_hourly_due(delivery):
    client, db, _ = delivery
    from app.services.energy_file_push import publish, poll_delivery
    from app.services.energy_sync import utcnow
    from app.models.energy import EnergySyncState
    from app.models.response import WorkerHeartbeat
    from app.services.energy_file_push import WORKER
    saved = dt.datetime(2026, 7, 4, tzinfo=dt.timezone.utc)
    publish(db, workbook(), saved)
    state = db.get(EnergySyncState, 'file-push')
    state.last_success_at = utcnow() - dt.timedelta(hours=1, seconds=1)
    db.commit()
    assert poll_delivery(db)['upload_required']
    assert client.post('/api/energy/sync').status_code == 202
    old = dt.datetime.fromisoformat(poll_delivery(db)['request_token'])
    later = old + dt.timedelta(microseconds=1)
    state.requested_at = later
    db.commit()
    publish(db, workbook(), saved, acknowledged_request=old)
    assert db.get(EnergySyncState, 'file-push').requested_at == later
    db.get(WorkerHeartbeat, WORKER).updated_at = utcnow() - dt.timedelta(minutes=4)
    db.commit()
    status = client.get('/api/energy/status').json()['sync']
    assert not status['agent_online'] and status['pending']


def test_sync_queue_requires_admin_and_does_not_claim_offline_completion(delivery):
    client, db, actor = delivery
    from app.models.energy import EnergySyncState
    for role in ['NOC.Viewer', 'NOC.Operator']:
        actor['roles'] = [role]
        assert client.post('/api/energy/sync').status_code == 403
    assert db.get(EnergySyncState, 'file-push') is None
    actor['roles'] = ['NOC.Admin']
    assert client.post('/api/energy/sync').status_code == 202
    sync = client.get('/api/energy/status').json()['sync']
    assert sync['pending'] and not sync['agent_online'] and not sync['connected']


def test_delayed_request_can_retry_then_complete_without_losing_report(delivery):
    client, db, _ = delivery
    from app.services.energy_file_push import publish, poll_delivery
    from app.services.energy_sync import utcnow
    from app.models.energy import EnergySyncState
    saved = dt.datetime(2026, 7, 4, tzinfo=dt.timezone.utc)
    publish(db, workbook(), saved)
    assert client.post('/api/energy/sync').status_code == 202
    state = db.get(EnergySyncState, 'file-push')
    old = utcnow() - dt.timedelta(minutes=4)
    state.requested_at = old
    db.commit()
    sync = client.get('/api/energy/status').json()['sync']
    assert sync['request_state'] == 'delayed' and sync['pending']
    assert client.get('/api/energy/report', params={'day': '2026-07-04'}).status_code == 200
    retry = client.post('/api/energy/sync')
    assert retry.status_code == 202
    requested = dt.datetime.fromisoformat(retry.json()['requested_at'])
    assert requested > old
    assert client.get('/api/energy/status').json()['sync']['request_state'] == 'waiting'
    publish(db, workbook(), saved, acknowledged_request=old)
    assert client.get('/api/energy/status').json()['sync']['pending']
    token = dt.datetime.fromisoformat(poll_delivery(db)['request_token'])
    publish(db, workbook(), saved, acknowledged_request=token)
    sync = client.get('/api/energy/status').json()['sync']
    assert not sync['pending'] and sync['request_state'] == 'idle'


def test_manual_fallback_can_complete_a_waiting_request(delivery):
    client, db, _ = delivery
    assert client.post('/api/energy/sync').status_code == 202
    result = client.post('/api/energy/deliveries', files={'file': ('tracker.xlsx', workbook())},
                         data={'modified_at': '2026-07-04T00:00:00Z'})
    assert result.status_code == 200
    assert not client.get('/api/energy/status').json()['sync']['pending']
