from uuid import uuid4
from test_ftth_intake_api import api,pytestmark  # noqa: F401


def payload(**extra):
    return {'request_key':str(uuid4()),'subject':'Urgent service down','sender':'noc-test@example.com','body':'Service down for FN659353. Full private message content beyond the excerpt. '+('Evidence '*80),**extra}


def test_preview_is_not_connected_and_retains_only_bounded_excerpt(api):
    client,db=api
    from app.models.mail import MailTriageItem
    connection=client.get('/api/mail/connection').json()
    assert not connection['connected'] and not connection['rag_connected'] and connection['last_sync_at'] is None
    data=payload();result=client.post('/api/mail/preview',json=data)
    assert result.status_code==200,result.text
    item=result.json()['item']
    assert item['source']=='manual_preview' and item['received_at'] is None
    assert item['classification']['category']=='outage' and len(item['excerpt'])==400
    assert 'body' not in item and 'request_hash' not in item
    row=db.query(MailTriageItem).filter_by(item_id=item['item_id']).one()
    assert not hasattr(row,'body')
    routine=client.post('/api/mail/preview',json=payload(subject='Weekly bulletin',body='Newsletter, unsubscribe here')).json()['item']
    assert routine['excerpt']==''
    ordered=[value['item_id'] for value in client.get('/api/mail/items').json()['items']]
    assert ordered.index(item['item_id'])<ordered.index(routine['item_id'])


def test_retries_review_links_and_private_scope(api,monkeypatch):
    client,_=api
    data=payload();item=client.post('/api/mail/preview',json=data).json()['item']
    retry=client.post('/api/mail/preview',json=data)
    assert retry.json()['outcome']=='already_logged' and retry.json()['item']['item_id']==item['item_id']
    assert client.post('/api/mail/preview',json={**data,'body':'Changed content'}).status_code==409
    incident=client.post('/api/incidents/',json={'incident_type':'Monitoring Alert','ticket_category':'TECHNICAL','short_description':'Mail link regression'}).json()
    path=f"/api/mail/items/{item['item_id']}"
    linked=client.patch(path,json={'state':'acknowledged','note':'Incident correlation verified','incident_id':incident['incident_id']})
    assert linked.status_code==200,linked.text
    assert linked.json()['reviewed_by']=='local-preview'
    assert client.patch(path,json={'state':'dismissed','note':'Duplicate of existing investigation'}).json()['incident_id']==incident['incident_id']
    invalid=client.patch(path,json={'state':'acknowledged','note':'Missing record link','order_id':'00000000-0000-0000-0000-000000000000'})
    assert invalid.status_code==422
    from app.core import security
    monkeypatch.setattr(security,'auth_configuration',lambda:{'configured':True,'mode':'entra'})
    actor={'id':'another-operator','verified':True,'roles':['NOC.Operator']}
    monkeypatch.setattr(security,'validate_token',lambda token:actor.copy())
    headers={'authorization':'Bearer test'}
    assert item['item_id'] not in [value['item_id'] for value in client.get('/api/mail/items',headers=headers).json()['items']]
    assert client.patch(path,headers=headers,json={'state':'dismissed','note':'Unauthorized private action'}).status_code==404
    actor['roles']=['NOC.Admin']
    assert client.patch(path,headers=headers,json={'state':'needs_review','note':'Administrator reopened for review'}).status_code==200
    actor['roles']=['NOC.Viewer']
    assert client.post('/api/mail/preview',headers=headers,json=data).status_code==403


def test_invalid_dates_and_production_preview_guard(api,monkeypatch):
    client,_=api
    assert client.post('/api/mail/preview',json=payload(received_at='2099-01-01T10:00:00+01:00')).status_code==422
    assert client.post('/api/mail/preview',json=payload(body='')).status_code==422
    from app.core import security
    from app.core.config import settings
    monkeypatch.setattr(settings,'ENVIRONMENT','production')
    monkeypatch.setattr(security,'auth_configuration',lambda:{'configured':True,'mode':'entra'})
    monkeypatch.setattr(security,'validate_token',lambda token:{'id':'operator','verified':True,'roles':['NOC.Operator']})
    headers={'authorization':'Bearer test'}
    assert client.post('/api/mail/preview',headers=headers,json=payload()).status_code==409
    assert client.get('/api/mail/connection',headers=headers).json()['mode']=='unavailable'
