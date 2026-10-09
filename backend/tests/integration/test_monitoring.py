from datetime import datetime, timezone, timedelta
import pytest
from test_ftth_intake_api import api, pytestmark  # noqa: F401


def test_alarm_deduplication_recovery_and_stale_event(api):
    client, session = api
    from app.models.infrastructure import FiberCable
    from app.models.incidents import Incident, Ticket
    cable = session.query(FiberCable).filter_by(cable_name='CABLE-N1').one()
    cable.route.geometry = 'SRID=4326;LINESTRING(3.40 6.45,3.41 6.46)'
    session.commit()
    mapping = client.post('/api/monitoring/mappings', json={'sensor_id': 'test-sensor', 'cable_id': str(cable.cable_id)})
    assert mapping.status_code == 200, mapping.text
    assert client.post('/api/monitoring/mappings', json=mapping.json()).status_code == 409
    now = datetime.now(timezone.utc) - timedelta(minutes=1)
    payload = {'event_id': 'test-alarm-1', 'sensor_id': 'test-sensor', 'state': 'down', 'observed_at': now.isoformat()}
    result = client.post('/api/monitoring/simulate', json=payload)
    assert result.status_code == 200, result.text
    incident_id = result.json()['event']['incident_id']
    assert incident_id is not None
    geography = client.get('/api/topology/geography').json()
    feature = next(row for row in geography['features'] if row['properties'].get('kind') == 'route' and row['properties']['inventory_route_id'] == str(cable.route_id))
    assert feature['properties']['monitoring_alarms'][0]['sensor_id'] == 'test-sensor'
    assert session.query(Ticket).filter_by(incident_id=incident_id).count() > 0
    repeated = client.post('/api/monitoring/simulate', json=payload)
    assert repeated.json()['outcome'] == 'duplicate'
    assert client.post('/api/monitoring/simulate', json={**payload, 'state': 'up'}).status_code == 409
    more_down = client.post('/api/monitoring/simulate', json={**payload, 'event_id': 'test-alarm-2', 'observed_at': (now + timedelta(seconds=10)).isoformat()})
    assert more_down.json()['event']['incident_id'] == incident_id
    recovery = client.post('/api/monitoring/simulate', json={**payload, 'event_id': 'test-up', 'state': 'up', 'observed_at': (now + timedelta(seconds=20)).isoformat()})
    assert recovery.status_code == 200, recovery.text
    assert session.get(Incident, incident_id).status == 'open'
    stale = client.post('/api/monitoring/simulate', json={**payload, 'event_id': 'test-stale'})
    assert stale.json()['event']['disposition'] == 'stale'
    sensor = next(row for row in client.get('/api/monitoring/mappings').json() if row['sensor_id'] == 'test-sensor')
    assert sensor['last_state'] == 'up'
    feature = next(row for row in client.get('/api/topology/geography').json()['features'] if row['properties'].get('kind') == 'route' and row['properties']['inventory_route_id'] == str(cable.route_id))
    assert feature['properties']['monitoring_alarms'] == []


def test_unmapped_and_non_alarm_states_do_not_create_incidents(api):
    client, session = api
    from app.models.incidents import Incident
    from app.models.infrastructure import FiberCable
    count = session.query(Incident).count()
    cable = session.query(FiberCable).first()
    client.post('/api/monitoring/mappings', json={'sensor_id': 'quiet-sensor', 'cable_id': str(cable.cable_id)})
    for index, state in enumerate(('up', 'warning', 'paused', 'unknown')):
        response = client.post('/api/monitoring/simulate', json={'event_id': f'quiet-{index}', 'sensor_id': 'quiet-sensor', 'state': state, 'observed_at': datetime.now(timezone.utc).isoformat()})
        assert response.status_code == 200, response.text
    response = client.post('/api/monitoring/simulate', json={'event_id': 'unmapped', 'sensor_id': 'missing', 'state': 'down', 'observed_at': datetime.now(timezone.utc).isoformat()})
    assert response.json()['event']['disposition'] == 'unmapped'
    assert session.query(Incident).count() == count


def test_intake_requires_separate_credential_and_simulation_is_preview_only(api, monkeypatch):
    client, _ = api
    from app.core.config import settings
    data = {'event_id': 'bridge-event', 'sensor_id': 'bridge-sensor', 'state': 'down', 'observed_at': datetime.now(timezone.utc).isoformat()}
    monkeypatch.setattr(settings, 'MONITORING_INGEST_TOKEN', 'a' * 40)
    assert client.post('/api/monitoring/events', json=data).status_code == 401
    assert client.post('/api/monitoring/events', json=data, headers={'authorization': 'Bearer wrong'}).status_code == 401
    response = client.post('/api/monitoring/events', json=data, headers={'authorization': 'Bearer ' + 'a' * 40})
    assert response.status_code == 200, response.text
    assert client.get('/api/provisioning/', headers={'authorization': 'Bearer ' + 'a' * 40}).status_code == 200  # preview only
    monkeypatch.setattr(settings, 'AUTH_MODE', 'entra')
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'production')
    assert client.post('/api/monitoring/simulate', json=data).status_code == 503
    assert client.post('/api/monitoring/events', json={**data, 'event_id': 'production-bridge'}, headers={'authorization': 'Bearer ' + 'a' * 40}).status_code == 200


def test_invalid_sensor_target_and_future_time(api):
    client, _ = api
    assert client.post('/api/monitoring/mappings', json={'sensor_id': 'invalid'}).status_code == 422
    assert client.post('/api/monitoring/mappings', json={'sensor_id': 'missing', 'cable_id': '00000000-0000-0000-0000-000000000001'}).status_code == 404
    assert client.post('/api/monitoring/simulate', json={'event_id': 'future', 'sensor_id': 'missing', 'state': 'down', 'observed_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}).status_code == 422
