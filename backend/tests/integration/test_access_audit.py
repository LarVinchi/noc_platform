import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_ftth_intake_api import api, REQUEST, pytestmark  # noqa: F401


def test_transactional_audit_redaction_and_protection(api):
    client, session = api
    order = client.post('/api/provisioning/intake/preview', json={'raw_text': REQUEST}).json()['order']
    result = client.post('/api/provisioning/', json=order)
    assert result.status_code == 200, result.text
    entity_id = result.json()['order_id']
    records = client.get('/api/audit/', params={'entity_id': entity_id}).json()['items']
    assert len(records) == 1
    row = records[0]
    assert row['action'] == 'INSERT' and row['actor_id'] == 'local-preview'
    assert not row['actor_verified'] and row['request_id'] == result.headers['x-request-id']
    assert 'raw_request_text' not in row['after_state'] and 'email' not in row['after_state']
    for sql in ('UPDATE audit_events SET actor_id = \'tampered\' WHERE audit_id = :id',
                'DELETE FROM audit_events WHERE audit_id = :id', 'TRUNCATE audit_events'):
        with pytest.raises(DBAPIError), session.begin_nested():
            session.execute(text(sql), {'id': row['audit_id']})
    with session.begin_nested() as savepoint:
        session.execute(text("UPDATE service_orders SET bandwidth = '200Mbps' WHERE order_id = :id"), {'id': entity_id})
        assert session.execute(text('SELECT count(*) FROM audit_events WHERE entity_id = :id'), {'id': entity_id}).scalar() == 2
        savepoint.rollback()
    assert session.execute(text('SELECT count(*) FROM audit_events WHERE entity_id = :id'), {'id': entity_id}).scalar() == 1


def test_http_guard_covers_api_documents_and_preview_escape(api, monkeypatch):
    client, _ = api
    from app.core.config import settings
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'production')
    for path in ('/api/provisioning/', '/static/documents/private.pdf', '/docs', '/openapi.json'):
        assert client.get(path).status_code == 503
    assert client.get('/api/auth/config').json()['configured'] is False
    assert client.get('/health/ready').status_code == 200


def test_viewer_blocked_at_http_boundary(api, monkeypatch):
    client, _ = api
    from app.core import security
    monkeypatch.setattr(security, 'auth_configuration', lambda: {'configured': True, 'mode': 'entra'})
    monkeypatch.setattr(security, 'validate_token', lambda token: {'id': 'viewer', 'verified': True, 'roles': ['NOC.Viewer']})
    headers = {'authorization': 'Bearer test'}
    assert client.get('/api/provisioning/', headers=headers).status_code == 200
    assert client.post('/api/provisioning/', headers=headers, json={}).status_code == 403
    assert client.get('/api/audit/', headers=headers).status_code == 403
    assert client.get('/api/provisioning/').status_code == 401
