from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_ftth_intake_api import api,pytestmark,REQUEST  # noqa: F401


def edit(client,kind,identifier,changes,revision=None,reason='Correct data entry mistake'):
    path=f'/api/corrections/{kind}/{identifier}'
    state=client.get(path)
    assert state.status_code==200,state.text
    return client.patch(path,json={'expected_revision':revision or state.json()['revision'],'changes':changes,'reason':reason})


def order(client):
    fields=client.post('/api/provisioning/intake/preview',json={'raw_text':REQUEST,'isp':'MTNN'}).json()['order']
    response=client.post('/api/provisioning/intake',json={'order':fields,'raw_text':REQUEST})
    assert response.status_code==200,response.text
    return response.json()['order']


def activated_graph(client,db):
    from app.models.crm import Customer,Service
    from app.models.provisioning import ServiceOrder,WorkflowStage
    from app.models.infrastructure import DropCable
    from app.models.allocations import DropAllocation
    data=order(client)
    customer=Customer(customer_name=data['customer_name'],service_id_code='CORRECTION-'+str(uuid4()),customer_type='ISP',email=data['email'],phone=data['phone_number'],address=data['service_address'])
    db.add(customer);db.flush()
    service=Service(customer_id=customer.customer_id,service_type='FTTH',bandwidth_mbps=100,status='active')
    db.add(service);db.flush()
    nap=client.get('/api/inventory/assignment-options').json()['naps'][0]
    drop=DropCable(nap_id=nap['nap_id'],drop_cable_code='CORRECTION-'+str(uuid4()),status='active')
    db.add(drop);db.flush()
    record=db.get(ServiceOrder,data['order_id']);record.activated_service_id=service.service_id;record.status=WorkflowStage.MONITORED
    record.nap_id=drop.nap_id;record.nap_port=nap['available_ports'][0];record.drop_cable_id=drop.drop_cable_id
    allocation=DropAllocation(service_id=service.service_id,drop_cable_id=drop.drop_cable_id,nap_port_number=record.nap_port,is_active=True)
    db.add(allocation);db.commit()
    return record,customer,service,allocation


def test_incident_category_changes_ticket_id_and_old_id_remains_searchable(api):
    client,db=api
    incident=client.post('/api/incidents/',json={'incident_type':'Interface or Link Issue','ticket_category':'TECHNICAL','severity':'High','short_description':'Transmission mistake'}).json()
    identifier=incident['incident_id'];old=incident['tt_number']
    assert old.startswith('TN_')
    assert incident['ticket_category']=='TRANSMISSION' and incident['ticket_id']==old
    state=client.get(f'/api/corrections/incident/{identifier}').json()
    response=edit(client,'incident',identifier,{'ticket_category':'POWER','incident_type':'Power Issue','short_description':'Corrected power incident','severity':'Critical'})
    assert response.status_code==200,response.text
    current=client.get(f'/api/incidents/{identifier}').json()
    assert current['tt_number'].startswith('PW_') and current['tt_number']!=old
    assert current['incident_id']==identifier
    for field in ('reported_at','ack_deadline_at','restore_deadline_at','response_policy_id','status'):
        assert current[field]==incident[field]
    assert any(row['incident_id']==identifier for row in client.get('/api/incidents/',params={'search':old}).json())
    history=response.json()['history'][0]
    assert history['previous_ticket_id']==old and history['current_ticket_id']==current['tt_number']
    assert history['actor_id']=='local-preview' and history['reason']=='Correct data entry mistake'
    assert edit(client,'incident',identifier,{'ticket_category':'TRANSMISSION','incident_type':'Transmission'}).status_code==200
    latest=client.get(f'/api/incidents/{identifier}').json()
    assert latest['ticket_id']==latest['tt_number'] and latest['ticket_id'].startswith('TN_')
    assert latest['ticket_id']!=old and latest['incident_id']==identifier
    for previous in (old,current['tt_number']):
        assert any(row['incident_id']==identifier and row['ticket_id']==latest['ticket_id'] for row in client.get('/api/incidents/',params={'search':previous}).json())

    assert edit(client,'incident',identifier,{'notes':'stale overwrite'},revision=state['revision']).status_code==409
    assert edit(client,'incident',identifier,{'reported_at':'2000-01-01T00:00:00Z'}).status_code==422
    assert edit(client,'incident',identifier,{'notes':'new note'},reason='     ').status_code==422
    with pytest.raises(DBAPIError),db.begin_nested():
        db.execute(text('UPDATE record_corrections SET reason=\'remove evidence\' WHERE correction_id=:id'),{'id':history['correction_id']})


def test_ftth_edits_synchronize_customer_service_and_preserve_allocation(api):
    client,db=api
    record,customer,service,allocation=activated_graph(client,db)
    from app.models.provisioning import ServiceOrder
    original=(record.service_order_number,record.service_id,record.raw_request_text,record.status,record.nap_id,record.nap_port,record.drop_cable_id)
    response=edit(client,'ftth_order',record.order_id,{'customer_name':'Corrected FTTH name','service_address':'Corrected site address','phone_number':'08012345678','email':'corrected@example.com','bandwidth':'250 Mbps','fn_number':'fn987654322'})
    assert response.status_code==200,response.text
    db.refresh(record);db.refresh(customer);db.refresh(service);db.refresh(allocation)
    assert (record.service_order_number,record.service_id,record.raw_request_text,record.status,record.nap_id,record.nap_port,record.drop_cable_id)==original
    assert record.customer_name==customer.customer_name=='Corrected FTTH name'
    assert record.email==customer.email=='corrected@example.com'
    assert record.service_address==customer.address=='Corrected site address'
    assert record.phone_number==customer.phone=='08012345678'
    assert service.bandwidth_mbps==250 and record.bandwidth=='250Mbps' and record.fn_number=='FN987654322'
    assert allocation.is_active and allocation.drop_cable_id==record.drop_cable_id
    assert edit(client,'customer',customer.customer_id,{'customer_name':'CRM corrected name','address':'CRM corrected address'}).status_code==200
    db.refresh(record);assert record.customer_name=='CRM corrected name' and record.service_address=='CRM corrected address'
    assert edit(client,'service',service.service_id,{'bandwidth_mbps':500}).status_code==200
    db.refresh(record);assert record.bandwidth=='500Mbps'
    assert edit(client,'ftth_order',record.order_id,{'nap_port':999}).status_code==422
    assert edit(client,'ftth_order',record.order_id,{'fn_number':None}).status_code==422
    assert edit(client,'customer',customer.customer_id,{'service_id_code':'rewrite generated identity'}).status_code==422
    assert edit(client,'customer',customer.customer_id,{'address':None}).status_code==422
    assert edit(client,'service',service.service_id,{'customer_id':str(uuid4())}).status_code==422
    assert edit(client,'service',service.service_id,{'bandwidth_mbps':0}).status_code==422
    linked=client.get('/api/services/',params={'customer_id':str(customer.customer_id)}).json()['items']
    assert linked[0]['service_id']==str(service.service_id) and linked[0]['ftth_orders'][0]['order_id']==str(record.order_id)


def test_order_duplicate_conflict_and_unchanged_retry_preserve_history(api):
    client,db=api
    first=order(client)
    second=client.post('/api/provisioning/',json={'customer_name':'Other test','service_address':'Other address','isp':'MTNN','bandwidth':'100Mbps','fn_number':'FN987654399','work_order_id':'CO987654399'}).json()
    rejected=edit(client,'ftth_order',first['order_id'],{'fn_number':second['fn_number'],'customer_name':'Should roll back'})
    assert rejected.status_code==409,rejected.text
    state=client.get(f"/api/corrections/ftth_order/{first['order_id']}").json()
    assert state['values']['customer_name']==first['customer_name'] and not state['history']
    assert edit(client,'ftth_order',first['order_id'],{'bandwidth':'invalid'}).status_code==422
    assert edit(client,'ftth_order',first['order_id'],{'customer_name':first['customer_name']}).json()['outcome']=='unchanged'


def test_viewer_cannot_correct_records(api,monkeypatch):
    client,db=api
    from app.models.crm import Customer
    customer=Customer(customer_name='Readonly test',service_id_code='READONLY-'+str(uuid4()),customer_type='ISP')
    db.add(customer);db.commit()
    state=client.get(f'/api/corrections/customer/{customer.customer_id}').json()
    from app.core import security
    monkeypatch.setattr(security,'auth_configuration',lambda:{'configured':True,'mode':'entra'})
    monkeypatch.setattr(security,'validate_token',lambda token:{'id':'viewer','verified':True,'roles':['NOC.Viewer']})
    response=client.patch(f'/api/corrections/customer/{customer.customer_id}',headers={'authorization':'Bearer test'},json={'expected_revision':state['revision'],'reason':'Forbidden correction','changes':{'customer_name':'bad overwrite'}})
    assert response.status_code==403
    db.refresh(customer);assert customer.customer_name=='Readonly test'


def test_standalone_worker_registers_all_referenced_models():
    import subprocess,sys
    result=subprocess.run([sys.executable,'-c',"from app.response_worker import SessionLocal; from app.core.db import Base; assert all(fk.column is not None for table in Base.metadata.tables.values() for fk in table.foreign_keys)"],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
