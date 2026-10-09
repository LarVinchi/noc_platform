from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_ftth_intake_api import api, pytestmark  # noqa: F401


def incident(client, **extra):
    result = client.post('/api/incidents/', json={'incident_type':'Monitoring Alert','ticket_category':'TECHNICAL','severity':'High','short_description':'Response regression incident',**extra})
    assert result.status_code == 200, result.text
    return result.json()


def engineer(client):
    result = client.post('/api/operations/engineers',json={'name':'TEST RESPONSE ENGINEER','email':'response-test@example.com','team':'NOC Engineering'})
    assert result.status_code == 200, result.text
    return result.json()


def policy(client, **extra):
    result = client.post('/api/operations/policies',json={'name':'Preview regression policy','severity':'High','acknowledgment_minutes':5,'restoration_minutes':10,'followup_minutes':5,'effective_from':'2020-01-01T00:00:00Z',**extra})
    assert result.status_code == 200, result.text
    return result.json()


def test_assignment_acknowledgment_policy_version_and_history(api):
    client, session = api
    owner = engineer(client)
    rules = policy(client,default_engineer_id=owner['engineer_id'])
    record = incident(client)
    assert record['assigned_engineer_id'] == owner['engineer_id']
    assert record['response_policy_id'] == rules['policy_id']
    assert record['ack_deadline_at']
    new_rules = policy(client,acknowledgment_minutes=8,restoration_minutes=20)
    assert new_rules['version'] == rules['version']+1
    assert client.get(f"/api/incidents/{record['incident_id']}").json()['response_policy_id'] == rules['policy_id']
    ack = client.post(f"/api/operations/incidents/{record['incident_id']}/acknowledge")
    assert ack.status_code == 200, ack.text
    repeated = client.post(f"/api/operations/incidents/{record['incident_id']}/acknowledge")
    assert repeated.json()['acknowledged_at'] == ack.json()['acknowledged_at']
    assert ack.json()['status'] == 'investigating'
    details = client.get(f"/api/operations/incidents/{record['incident_id']}").json()
    assert sum(row['event_type']=='acknowledged' for row in details['timeline']) == 1
    assert any(row['event_type']=='engineer_assigned' for row in details['timeline'])
    with pytest.raises(DBAPIError), session.begin_nested():
        session.execute(text('UPDATE response_policies SET acknowledgment_minutes=1 WHERE policy_id=:id'),{'id':rules['policy_id']})


def test_confirmed_outage_guard_restoration_reporting_and_drafts(api):
    client, session = api
    from app.models.crm import Service
    service = session.query(Service).first()
    rules = policy(client,severity=None,service_id=str(service.service_id),acknowledgment_minutes=15,restoration_minutes=60)
    record = incident(client)
    start = datetime.now(timezone.utc)-timedelta(minutes=30)
    payload = {'service_id':str(service.service_id),'started_at':start.isoformat(),'note':'Operator verified customer connectivity failure'}
    created = client.post(f"/api/operations/incidents/{record['incident_id']}/outages",json=payload)
    assert created.status_code == 200, created.text
    outage = created.json()
    assert outage['policy_id'] == rules['policy_id']
    assert client.post(f"/api/operations/incidents/{record['incident_id']}/outages",json=payload).json()['outage_id'] == outage['outage_id']
    assert client.post(f"/api/operations/incidents/{record['incident_id']}/outages",json={**payload,'note':'Different outage evidence'}).status_code == 409
    for status in ('resolved','closed','aborted'):
        assert client.patch(f"/api/incidents/{record['incident_id']}",json={'status':status}).status_code == 409
    restored = client.post(f"/api/operations/outages/{outage['outage_id']}/restore",json={'restored_at':(start+timedelta(minutes=20)).isoformat(),'note':'Customer link and application access tested'})
    assert restored.status_code == 200, restored.text
    assert restored.json()['restoration_minutes'] == 20
    assert client.get(f"/api/incidents/{record['incident_id']}").json()['status'] == 'open'
    assert client.patch(f"/api/incidents/{record['incident_id']}",json={'status':'resolved','resolution_method':'Customer test verified'}).status_code == 200
    drafts = client.get('/api/operations/drafts',params={'incident_id':record['incident_id']}).json()
    assert len(drafts) == 2 and {value['status'] for value in drafts} == {'discarded','draft'}
    report = client.get('/api/operations/reports',params={'start':(start-timedelta(minutes=1)).isoformat()}).json()
    assert report['mttr_minutes'] == 20 and report['availability_percent'] is None
    assert report['monitoring_coverage'] == 'unverified'
    assert next(row for row in report['services'] if row['service_id']==str(service.service_id))['recorded_downtime_minutes'] == 20


def test_scheduler_levels_are_idempotent_and_suppress_planned_incidents(api):
    client, session = api
    from app.services.escalation import run_escalations
    from app.models.response import ResponseEvent, NotificationDraft
    policy(client)
    start = datetime.now(timezone.utc)-timedelta(hours=1)
    active = incident(client,reported_at=start.isoformat())
    planned = incident(client,reported_at=start.isoformat(),is_planned=True)
    now = datetime.now(timezone.utc)
    assert run_escalations(session,now) == 3
    session.flush()
    assert run_escalations(session,now) == 0
    rows = session.query(ResponseEvent).filter_by(incident_id=active['incident_id'],event_type='escalated').all()
    assert len(rows) == 3
    assert session.query(ResponseEvent).filter_by(incident_id=planned['incident_id'],event_type='escalated').count() == 0
    assert session.query(NotificationDraft).filter_by(incident_id=active['incident_id'],audience='escalation').count() == 3


def test_unassigned_and_disabled_engineer_guards(api):
    client, _ = api
    record = incident(client)
    assert client.post(f"/api/operations/incidents/{record['incident_id']}/acknowledge").status_code == 409
    owner = engineer(client)
    assert client.patch(f"/api/operations/engineers/{owner['engineer_id']}",json={'enabled':False}).status_code == 200
    assert client.post(f"/api/operations/incidents/{record['incident_id']}/assign",json={'engineer_id':owner['engineer_id']}).status_code == 422


def test_draft_review_requires_recipient_and_never_sends(api):
    client, _ = api
    owner = engineer(client); record = incident(client)
    client.post(f"/api/operations/incidents/{record['incident_id']}/assign",json={'engineer_id':owner['engineer_id']})
    draft = client.get('/api/operations/drafts',params={'incident_id':record['incident_id']}).json()[0]
    assert client.patch(f"/api/operations/drafts/{draft['draft_id']}",json={'status':'reviewed','recipients':[]}).status_code == 422
    reviewed = client.patch(f"/api/operations/drafts/{draft['draft_id']}",json={'status':'reviewed','recipients':['engineer@example.com'],'subject':'Reviewed engineer assignment'})
    assert reviewed.status_code == 200 and reviewed.json()['reviewed_by']=='local-preview'
    assert client.patch(f"/api/operations/drafts/{draft['draft_id']}",json={'status':'sent'}).status_code == 422


def test_policy_and_outage_inputs_reject_invalid_scope_and_future_times(api):
    client, session = api
    from app.models.crm import Service
    service = session.query(Service).first(); record = incident(client)
    assert client.post('/api/operations/policies',json={'name':'Invalid','acknowledgment_minutes':1,'restoration_minutes':2}).status_code == 422
    assert client.post(f"/api/operations/incidents/{record['incident_id']}/outages",json={'service_id':str(service.service_id),'started_at':(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat(),'note':'Verified future outage'}).status_code == 422
    assert client.post(f"/api/operations/incidents/{record['incident_id']}/outages",json={'service_id':str(service.service_id),'started_at':datetime.now(timezone.utc).isoformat(),'note':'Confirmed excluded outage','excluded':True}).status_code == 422


def test_operator_cannot_modify_directory_or_target_policies(api,monkeypatch):
    client, _ = api
    from app.core import security
    monkeypatch.setattr(security,'auth_configuration',lambda:{'configured':True,'mode':'entra'})
    monkeypatch.setattr(security,'validate_token',lambda token:{'id':'operator','verified':True,'roles':['NOC.Operator']})
    headers={'authorization':'Bearer test'}
    assert client.get('/api/operations/summary',headers=headers).status_code == 200
    assert client.post('/api/operations/engineers',headers=headers,json={}).status_code == 403
    assert client.post('/api/operations/policies',headers=headers,json={}).status_code == 403


def test_customer_deadline_escalation_and_obsolete_draft_invalidation(api):
    client, session = api
    from app.models.crm import Service
    from app.services.escalation import run_escalations
    service = session.query(Service).first()
    policy(client,severity=None,service_id=str(service.service_id),acknowledgment_minutes=5,restoration_minutes=10)
    record = incident(client)
    start = datetime.now(timezone.utc)-timedelta(minutes=20)
    outage = client.post(f"/api/operations/incidents/{record['incident_id']}/outages",json={'service_id':str(service.service_id),'started_at':start.isoformat(),'note':'Connectivity loss verified by NOC'}).json()
    assert run_escalations(session) == 2
    session.flush()
    assert run_escalations(session) == 0
    before = client.get('/api/operations/drafts',params={'incident_id':record['incident_id']}).json()
    assert len(before) == 3
    restored = client.post(f"/api/operations/outages/{outage['outage_id']}/restore",json={'note':'Customer application and connectivity tests passed'})
    assert restored.status_code == 200, restored.text
    after = client.get('/api/operations/drafts',params={'incident_id':record['incident_id']}).json()
    assert sum(value['status']=='draft' for value in after) == 1
    obsolete = next(value for value in after if value['status']=='discarded')
    assert client.patch(f"/api/operations/drafts/{obsolete['draft_id']}",json={'status':'reviewed','recipients':['customer@example.com']}).status_code == 409


def test_overlapping_faults_do_not_claim_full_customer_restoration(api):
    client, session = api
    from app.models.crm import Service
    service = session.query(Service).first()
    records = [incident(client) for _ in range(2)]
    start = datetime.now(timezone.utc)-timedelta(minutes=5)
    outages = [client.post(f"/api/operations/incidents/{value['incident_id']}/outages",json={'service_id':str(service.service_id),'started_at':start.isoformat(),'note':'Confirmed service interruption under separate fault'}).json() for value in records]
    assert client.post(f"/api/operations/outages/{outages[0]['outage_id']}/restore",json={'note':'Restoration for first fault verified'}).status_code == 200
    drafts = client.get('/api/operations/drafts',params={'incident_id':records[0]['incident_id']}).json()
    current = next(value for value in drafts if value['status']=='draft')
    assert current['subject'].startswith('Partial restoration update')
    assert 'other confirmed outage record' in current['body']
    report = client.get('/api/operations/reports',params={'start':(start-timedelta(minutes=1)).isoformat()}).json()
    downtime = next(value for value in report['services'] if value['service_id']==str(service.service_id))['recorded_downtime_minutes']
    assert 5 <= downtime < 6  # two overlapping fault intervals are counted once
