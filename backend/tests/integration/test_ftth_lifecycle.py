from datetime import timedelta
from uuid import uuid4
import base64
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_ftth_intake_api import api,REQUEST,pytestmark  # noqa: F401


def create_order(client,isp='MTNN'):
    data=client.post('/api/provisioning/intake/preview',json={'raw_text':REQUEST,'isp':isp}).json()['order']
    response=client.post('/api/provisioning/',json=data)
    assert response.status_code==200,response.text
    return response.json()


def complete_order(client,order,reschedule=False):
    nap=client.get('/api/inventory/assignment-options').json()['naps'][0]
    response=client.patch(f"/api/provisioning/{order['order_id']}/allocate",json={'nap_id':nap['nap_id'],'port_number':nap['available_ports'][0],
        'new_drop_cable_code':'DROP-LIFECYCLE-TEST','installer':'TEST INSTALLER','planned_install_date':'2099-01-01T10:00:00+01:00'})
    assert response.status_code==200,response.text
    client.patch(f"/api/provisioning/{order['order_id']}/status",json={'status':'IN_PROGRESS'})
    if reschedule:
        assert client.patch(f"/api/provisioning/{order['order_id']}/status",json={'status':'SCHEDULED'}).status_code==200
        assert client.patch(f"/api/provisioning/{order['order_id']}/status",json={'status':'IN_PROGRESS'}).status_code==200
    image=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jqO0AAAAASUVORK5CYII=')
    response=client.post(f"/api/provisioning/{order['order_id']}/complete",data={'flexscan_result_dbm':'-22.5','checklist_completed':'true'},files={key:('test.png',image,'image/png') for key in ('photo_nap','photo_routing','photo_rosette','photo_flexscan')})
    assert response.status_code==200,response.text


def issue(client,order,kind='installation_blocker',**extra):
    data={'request_key':str(uuid4()),'kind':kind,'title':'FTTH regression issue','note':'Verified lifecycle evidence','severity':'High',**extra}
    response=client.post(f"/api/ftth/orders/{order['order_id']}/incidents",json=data)
    assert response.status_code==200,response.text
    return response.json(),data


def test_stage_history_counts_retry_and_blocker_resolution(api):
    client,db=api
    from app.models.ftth_operations import FtthStageEvent
    before_report=client.get('/api/ftth/reports',params={'isp':'MTNN'}).json()
    order=create_order(client);record,data=issue(client,order)
    identifier=record['incident']['incident_id']
    path=f"/api/ftth/orders/{order['order_id']}/incidents"
    retry=client.post(path,json=data)
    assert retry.json()['incident']['incident_id']==identifier
    assert client.post(path,json={**data,'note':'Changed evidence under same retry key'}).status_code==409
    complete_order(client,order)
    assert client.patch(f"/api/provisioning/{order['order_id']}/accept").status_code==409
    assert client.patch(f'/api/incidents/{identifier}',json={'status':'resolved'}).status_code==422
    resolved=client.patch(f'/api/incidents/{identifier}',json={'status':'resolved','resolution_method':'Site access verified with installer','rfo_root_cause':'Access restriction'})
    assert resolved.status_code==200,resolved.text
    assert resolved.json()['closed_by']=='local-preview'
    assert client.patch(f"/api/provisioning/{order['order_id']}/accept").status_code==200
    history=client.get(f"/api/ftth/orders/{order['order_id']}").json()
    assert history['history_complete']
    assert [value['to_stage'] for value in history['events']]==['REQUESTED','SCHEDULED','IN_PROGRESS','PENDING_ACCEPTANCE','MONITORED']
    assert history['incidents'][0]['resolution_method']=='Site access verified with installer'
    report=client.get('/api/ftth/reports',params={'isp':'MTNN'}).json()
    assert report['lifetime']=={key:value+1 for key,value in before_report['lifetime'].items()}
    for key in ('accepted','completed','resolved_incidents'):
        assert report['period'][key]==before_report['period'][key]+1
    assert any(value['category']=='TRANSMISSION' and value['samples']>=1 for value in report['incident_mttr'])
    assert report['unknown_acceptance_dates']==before_report['unknown_acceptance_dates']
    event=db.query(FtthStageEvent).filter_by(order_id=order['order_id']).first()
    with pytest.raises(DBAPIError),db.begin_nested():
        db.execute(text("UPDATE ftth_stage_events SET note='rewritten' WHERE event_id=:id"),{'id':event.event_id})


def test_service_fault_links_shared_ticket_without_invented_outage(api):
    client,db=api
    from app.models.incidents import Ticket
    from app.models.response import ServiceOutage
    before_active=client.get('/api/ftth/reports',params={'isp':'MTNN'}).json()['active_incidents']
    order=create_order(client);complete_order(client,order)
    invalid=client.post(f"/api/ftth/orders/{order['order_id']}/incidents",json={'request_key':str(uuid4()),'kind':'service_fault','title':'Invalid premature fault','note':'No activated service'})
    assert invalid.status_code==409
    accepted=client.patch(f"/api/provisioning/{order['order_id']}/accept").json()
    record,data=issue(client,order,'service_fault');identifier=record['incident']['incident_id']
    assert db.query(Ticket).filter_by(incident_id=identifier,service_id=accepted['activated_service_id']).count()==1
    assert db.query(ServiceOutage).filter_by(incident_id=identifier).count()==0
    linked,_=issue(client,order,'service_fault',incident_id=identifier)
    assert linked['outcome']=='already_linked'
    assert db.query(Ticket).filter_by(incident_id=identifier).count()==1
    assert client.post(f"/api/ftth/orders/{order['order_id']}/incidents",json={**data,'request_key':str(uuid4()),'kind':'installation_blocker'}).status_code==409
    assert client.get('/api/ftth/reports',params={'isp':'MTNN'}).json()['active_incidents']==before_active+1


def test_legacy_history_has_no_guessed_dates_and_provider_scope(api):
    client,db=api
    from app.models.provisioning import ServiceOrder,WorkflowStage,ISPType,ServiceCategory
    from app.services.incident_response import now_utc
    before=client.get('/api/ftth/reports',params={'isp':'MTNN'}).json()
    legacy=ServiceOrder(customer_name='LEGACY TEST',service_address='Test address',bandwidth='50Mbps',isp=ISPType.MTNN,service_category=ServiceCategory.FTTH,status=WorkflowStage.MONITORED,completion_date=(now_utc()-timedelta(days=40)).replace(tzinfo=None))
    db.add(legacy);db.commit()
    create_order(client,'METROREACH')
    report=client.get('/api/ftth/reports',params={'isp':'MTNN'}).json()
    assert report['lifetime']=={key:value+1 for key,value in before['lifetime'].items()}
    assert report['period']['accepted']==before['period']['accepted'] and report['period']['completed']==before['period']['completed']
    assert report['unknown_acceptance_dates']==before['unknown_acceptance_dates']+1 and report['partial_histories']==before['partial_histories']+1
    assert report['stage_durations']==before['stage_durations']
    assert client.get('/api/ftth/reports',params={'isp':'INVALID'}).status_code==422


def test_rescheduling_preserves_visits_and_repeat_intake_events(api):
    client,db=api
    from app.models.ftth_operations import FtthStageEvent
    order=create_order(client);complete_order(client,order,reschedule=True)
    events=db.query(FtthStageEvent).filter_by(order_id=order['order_id']).all()
    assert sum(value.to_stage=='IN_PROGRESS' for value in events)==2
    assert sum(value.to_stage=='SCHEDULED' for value in events)==2
    before=db.query(FtthStageEvent).filter_by(order_id=order['order_id']).count()
    preview=client.post('/api/provisioning/intake/preview',json={'raw_text':REQUEST,'isp':'MTNN'}).json()['order']
    assert client.post('/api/provisioning/',json=preview).status_code==200
    assert db.query(FtthStageEvent).filter_by(order_id=order['order_id']).count()==before
    assert client.patch(f"/api/provisioning/{order['order_id']}/status",json={'status':'IN_PROGRESS'}).status_code==409
    assert db.query(FtthStageEvent).filter_by(order_id=order['order_id']).count()==before


def test_legacy_ftth_service_ticket_is_counted_without_order(api):
    client,db=api
    from app.models.crm import Service
    from app.models.incidents import Ticket
    service=db.query(Service).filter_by(service_type='FTTH').first()
    assert service is not None
    before=client.get('/api/ftth/reports').json()['active_incidents']
    provider_before=client.get('/api/ftth/reports',params={'isp':'MTNN'}).json()['active_incidents']
    incident=client.post('/api/incidents/',json={'incident_type':'Monitoring Alert','ticket_category':'TECHNICAL','severity':'High','short_description':'Legacy service fault'}).json()
    db.add(Ticket(incident_id=incident['incident_id'],service_id=service.service_id,status='open'));db.commit()
    report=client.get('/api/ftth/reports').json()
    assert report['active_incidents']==before+1 and report['unattributed_services']>=1
    assert client.get('/api/ftth/reports',params={'isp':'MTNN'}).json()['active_incidents']==provider_before
    assert client.patch(f"/api/incidents/{incident['incident_id']}",json={'status':'resolved'}).status_code==422


def test_viewer_can_report_but_cannot_escalate(api,monkeypatch):
    client,_=api
    order=create_order(client)
    from app.core import security
    monkeypatch.setattr(security,'auth_configuration',lambda:{'configured':True,'mode':'entra'})
    monkeypatch.setattr(security,'validate_token',lambda token:{'id':'viewer','verified':True,'roles':['NOC.Viewer']})
    headers={'authorization':'Bearer test'}
    assert client.get('/api/ftth/reports',headers=headers).status_code==200
    assert client.get(f"/api/ftth/orders/{order['order_id']}",headers=headers).status_code==200
    assert client.post(f"/api/ftth/orders/{order['order_id']}/incidents",headers=headers,json={}).status_code==403
