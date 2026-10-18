"""Database-backed host telemetry API checks, collected alongside unit tests."""
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from pydantic import SecretStr
from test_ftth_intake_api import api, pytestmark  # noqa: F401


def sample():
    return {'sample_id':str(uuid4()),'host_id':'noc-review-host','observed_at':datetime.now(timezone.utc).isoformat(),
        'host':{'hostname':'ci-host','distribution':'Linux','version':'test','kernel':'test','architecture':'x86_64',
                'cpu_model':'CI CPU','cpu_cores':2,'uptime_seconds':100},
        'metrics':{'cpu_percent':20,'memory_total_bytes':1000,'memory_available_bytes':500,'memory_used_percent':50},
        'docker':{'available':False,'context':'desktop-linux'}}


def test_intake_auth_idempotency_host_binding_history_and_replay(api,monkeypatch):
    client,db=api
    from app.core.config import settings
    from app.models.platform_health import PlatformHost,PlatformSample
    monkeypatch.setattr(settings,'PLATFORM_AGENT_INGEST_TOKEN',SecretStr('a'*48))
    headers={'authorization':'Bearer '+'a'*48}
    value=sample()
    assert client.post('/api/platform-health/ingest',json=value).status_code==401
    assert client.post('/api/platform-health/ingest',headers=headers,json={**value,'host_id':'another-host'}).status_code==403
    response=client.post('/api/platform-health/ingest',headers=headers,json=value)
    assert response.status_code==200,response.text
    assert client.post('/api/platform-health/ingest',headers=headers,json=value).json()['outcome']=='duplicate'
    assert client.post('/api/platform-health/ingest',headers=headers,json={**value,'application_ready':True}).status_code==409
    older={**value,'sample_id':str(uuid4()),'observed_at':(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()}
    assert client.post('/api/platform-health/ingest',headers=headers,json=older).status_code==200
    assert db.query(PlatformSample).count()==2
    assert db.get(PlatformHost,'noc-review-host').payload['sample_id']==value['sample_id']
    status=client.get('/api/platform-health/hosts').json()
    assert status['hosts'][0]['summary']['state']=='Status stale'
    history=client.get('/api/platform-health/hosts/noc-review-host/history?hours=24')
    assert history.status_code==200,history.text
    assert sum(point['samples'] for point in history.json()['points'])==2
    assert client.post('/api/platform-health/ingest',headers=headers,content=b' '*262145).status_code==413
    assert client.get('/api/platform-health/hosts/noc-review-host/history?hours=99999').status_code==422


def test_host_dashboard_is_admin_only(api,monkeypatch):
    client,_=api
    from app.core import security
    monkeypatch.setattr(security,'auth_configuration',lambda:{'configured':True,'mode':'entra'})
    monkeypatch.setattr(security,'validate_token',lambda token:{'id':'viewer','verified':True,'roles':['NOC.Viewer']})
    assert client.get('/api/platform-health/hosts',headers={'authorization':'Bearer viewer'}).status_code==403
    assert client.get('/api/platform-health/hosts').status_code==401
