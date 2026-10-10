"""Validated metadata corrections, separate from lifecycle and infrastructure mutations."""
import hashlib,json,re
from datetime import datetime,timezone
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field,EmailStr,ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import actor_context
from app.models.incidents import Incident,VALID_INCIDENT_TYPES
from app.models.crm import Customer,Service
from app.models.provisioning import ServiceOrder
from app.models.corrections import RecordCorrection,IncidentTicketIdentifier
from app.schemas.provisioning import ServiceOrderCreate
from app.services.incident_response import timeline,invalidate_drafts

router=APIRouter(prefix='/corrections',tags=['Record corrections'])
Kind=Literal['incident','customer','service','ftth_order']
MODELS={'incident':Incident,'customer':Customer,'service':Service,'ftth_order':ServiceOrder}
KEYS={'incident':'incident_id','customer':'customer_id','service':'service_id','ftth_order':'order_id'}
# Field descriptors are shared by form rendering and the server allowlist.
FIELDS={
 'incident': [('incident_type','Incident type','text',True),('ticket_category','Category','select',True,['FIBER','POWER','TRANSMISSION','MAINTENANCE','OTHER']),('short_description','Summary','text',False),('description','Description','textarea',False),('severity','Severity','select',False,['Critical','High','Medium','Low']),('is_planned','Planned incident','boolean',False),('network_route','Route description','text',False),('network_node','Node description','text',False),('notes','Notes','textarea',False),('reason_for_delay','Delay reason','textarea',False),('resolution_method','Resolution action / evidence','textarea',False),('rfo_root_cause','Root cause','text',False),('rfo_root_cause_detail','Root cause details','textarea',False)],
 'customer':[('customer_name','Customer name','text',True),('service_id_code','Customer reference','text',True),('customer_type','Customer type','select',True,['METROREACH','ISP']),('email','Email','email',False),('phone','Phone','text',False),('address','Address','textarea',False)],
 'service':[('bandwidth_mbps','Bandwidth (Mbps)','number',True)],
 'ftth_order':[('customer_name','Customer name','text',True),('service_address','Service address','textarea',True),('phone_number','Phone','text',False),('email','Email','email',False),('bandwidth','Service package','text',True),('fn_number','FN number','text',False),('work_order_id','Work order ID','text',False)]}


class Patch(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision:str=Field(pattern=r'^[a-f0-9]{64}$')
    reason:str=Field(min_length=5,max_length=1000)
    changes:dict=Field(min_length=1,max_length=20)


def scalar(value):
    return getattr(value,'value',value)


def row(record):
    return {column.name:scalar(getattr(record,column.name)) for column in record.__table__.columns}


def related(db,kind,record):
    customer=record if kind=='customer' else None
    service=record if kind=='service' else db.get(Service,record.activated_service_id) if kind=='ftth_order' and record.activated_service_id else None
    if service: customer=db.get(Customer,service.customer_id)
    services=db.query(Service).filter_by(customer_id=customer.customer_id).order_by(Service.service_id).all() if customer else []
    orders=db.query(ServiceOrder).filter(ServiceOrder.activated_service_id.in_([s.service_id for s in services])).order_by(ServiceOrder.order_id).all() if services else []
    return customer,service,services,orders


def revision(db,kind,record):
    customer,service,services,orders=related(db,kind,record)
    snapshot={'record':row(record),'customer':row(customer) if customer else None,'services':[row(s) for s in services],'orders':[row(o) for o in orders]}
    return hashlib.sha256(json.dumps(snapshot,default=str,sort_keys=True).encode()).hexdigest()


def fields(db,kind,record):
    result=[{'name':f[0],'label':f[1],'type':f[2],'required':f[3],'options':f[4] if len(f)>4 else None} for f in FIELDS[kind]]
    if kind=='incident':
        result[0].update(type='select',options=sorted(VALID_INCIDENT_TYPES))
        result[1]['label']='Category (updates Ticket ID)'
    if kind=='service' and record.service_type=='DARKFIBER': result=[]
    if kind=='customer' and related(db,kind,record)[3]:
        result=[f for f in result if f['name'] not in {'service_id_code','customer_type'}]
    return result


def get_record(db,kind,identifier):
    record=db.get(MODELS[kind],identifier)
    if not record:raise HTTPException(404,'Record not found')
    if kind=='ftth_order' and scalar(record.service_category)!='FTTH':raise HTTPException(422,'Use this editor for FTTH orders')
    return record


def view(db,kind,record):
    editable=fields(db,kind,record)
    history=db.query(RecordCorrection).filter_by(entity_type=kind,entity_id=getattr(record,KEYS[kind])).order_by(RecordCorrection.created_at.desc(),RecordCorrection.correction_id.desc()).limit(20).all()
    customer,service,services,orders=related(db,kind,record)
    return {'entity_type':kind,'entity_id':getattr(record,KEYS[kind]),'revision':revision(db,kind,record),'fields':editable,
      'values':{f['name']:scalar(getattr(record,f['name'])) for f in editable},
      'title':getattr(record,'tt_number',None) or getattr(record,'fn_number',None) or getattr(record,'customer_name',None) or (customer.customer_name if customer else None) or str(getattr(record,KEYS[kind])),
      'linked_order_count':len(orders),'linked_service_count':len(services),
      'history':[row(h) for h in history],
      'notice':'Correct details only. Incident category changes generate a new Ticket ID and preserve the old one for search. Internal IDs, lifecycle, physical allocations and timestamps remain protected. Linked FTTH customer/package details are synchronized; existing PDFs and original pasted requests retain their original contents.',
      'policy_notice':'Existing response policies, deadlines and escalation evidence remain pinned; changing severity does not restart SLA clocks.' if kind=='incident' else None}


@router.get('/{kind}/{identifier}')
def detail(kind:Kind,identifier:UUID,db:Session=Depends(get_db)):
    return view(db,kind,get_record(db,kind,identifier))


def validate_changes(db,kind,record,changes):
    allowed={f['name']:f for f in fields(db,kind,record)}
    if set(changes)-set(allowed):raise HTTPException(422,'These fields require their dedicated workflow or cannot be changed')
    cleaned={}
    for name,value in changes.items():
        field=allowed[name]
        if field['type']=='boolean':
            if not isinstance(value,bool):raise HTTPException(422,f"{field['label']} must be true or false")
        elif field['type']=='number':
            if isinstance(value,bool) or not isinstance(value,int) or not 1<=value<=10000000:raise HTTPException(422,'Bandwidth must be a positive whole number of Mbps')
        else:
            if value is not None and not isinstance(value,str):raise HTTPException(422,f"{field['label']} must be text")
            value=value.strip() or None if isinstance(value,str) else None
            if name=='ticket_category' and value:
                value=value.upper()
                if value=='TECHNICAL':value='TRANSMISSION'
            if field['required'] and value is None:raise HTTPException(422,f"{field['label']} is required")
            maximum=2000 if name in {'address','service_address'} else 100 if name=='service_id_code' else 10000 if field['type']=='textarea' else 300
            if value and len(value)>maximum:raise HTTPException(422,f"{field['label']} is too long")
            if value and field['options'] and value not in field['options']:raise HTTPException(422,f"Select a valid {field['label']}")
            if value and field['type']=='email':
                from pydantic import TypeAdapter
                try:value=str(TypeAdapter(EmailStr).validate_python(value))
                except ValidationError:raise HTTPException(422,'Use a valid email address')
            if name=='phone' and value and (not re.fullmatch(r'\+?[\d ()-]+',value) or not 7<=len(re.sub(r'\D','',value))<=15):raise HTTPException(422,'Use a phone number with 7–15 digits')
        cleaned[name]=value
    if kind=='customer' and related(db,kind,record)[3] and 'address' in cleaned and not cleaned['address']:
        raise HTTPException(422,'A customer linked to FTTH orders must retain a service address')
    if kind=='ftth_order':
        try:
            merged=ServiceOrderCreate(**{**{f:getattr(record,f) for f in ServiceOrderCreate.model_fields},**cleaned})
        except ValidationError as error:raise HTTPException(422,str(error))
        cleaned={name:getattr(merged,name) for name in cleaned}
        if record.intake_source=='paste' and not all(cleaned.get(name,getattr(record,name)) for name in ('fn_number','work_order_id')):raise HTTPException(422,'Pasted orders must retain FN and work-order references')
    if kind=='incident' and record.status in {'resolved','closed','aborted'}:
        # Keep the existing FTTH closure-evidence guard for completed records.
        from app.models.ftth_operations import FtthIncidentLink
        from app.models.incidents import Ticket
        linked=db.query(FtthIncidentLink).filter_by(incident_id=record.incident_id).first() or db.query(Ticket).join(Service).filter(Ticket.incident_id==record.incident_id,Service.service_type.in_(['FTTH','ISP_FTTH'])).first()
        if linked and record.status=='aborted' and len((cleaned.get('notes',record.notes) or '').strip())<5:raise HTTPException(422,'Keep a valid FTTH abort reason')
        if linked and record.status in {'resolved','closed'} and (len((cleaned.get('resolution_method',record.resolution_method) or '').strip())<5 or len((cleaned.get('rfo_root_cause',record.rfo_root_cause) or '').strip())<3):raise HTTPException(422,'Keep valid FTTH resolution evidence and root cause')
    return {name:value for name,value in cleaned.items() if scalar(getattr(record,name))!=value}


@router.patch('/{kind}/{identifier}')
def correct(kind:Kind,identifier:UUID,payload:Patch,db:Session=Depends(get_db)):
    if len(payload.reason.strip())<5:raise HTTPException(422,'Explain the correction in at least five characters')
    # Serialize graph corrections; lock orders before service/customer rows, matching activation.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('noc:record-corrections',0))"))
    record=get_record(db,kind,identifier)
    customer,service,services,orders=related(db,kind,record)
    order_ids={o.order_id for o in orders}
    if kind=='ftth_order':order_ids.add(record.order_id)
    if order_ids:db.query(ServiceOrder).filter(ServiceOrder.order_id.in_(order_ids)).order_by(ServiceOrder.order_id).with_for_update().populate_existing().all()
    if services:db.query(Service).filter(Service.service_id.in_([s.service_id for s in services])).order_by(Service.service_id).with_for_update().populate_existing().all()
    if customer:db.query(Customer).filter_by(customer_id=customer.customer_id).with_for_update().populate_existing().all()
    record=db.query(MODELS[kind]).filter(getattr(MODELS[kind],KEYS[kind])==identifier).with_for_update().populate_existing().one()
    if revision(db,kind,record)!=payload.expected_revision:raise HTTPException(409,'This record or a linked record changed. Reload the editor and review before saving.')
    changes=validate_changes(db,kind,record,payload.changes)
    if not changes:return {**view(db,kind,record),'outcome':'unchanged'}
    affected={}
    previous_ticket_id=None
    def apply(entity_type,target,values):
        changed=[name for name,value in values.items() if scalar(getattr(target,name))!=value]
        if not changed:return
        for name in changed:setattr(target,name,values[name])
        affected[(entity_type,getattr(target,KEYS[entity_type]))]=changed
    try:
        if kind=='incident' and 'ticket_category' in changes:
            from app.services.ticketing import generate_tt_number
            previous_ticket_id=record.tt_number
            if previous_ticket_id and not db.get(IncidentTicketIdentifier,previous_ticket_id):
                db.add(IncidentTicketIdentifier(ticket_id=previous_ticket_id,incident_id=identifier))
            record.tt_number=generate_tt_number(db,changes['ticket_category'])
            db.add(IncidentTicketIdentifier(ticket_id=record.tt_number,incident_id=identifier))
        apply(kind,record,changes)
        customer,service,services,orders=related(db,kind,record)
        customer_map={'customer_name':'customer_name','service_address':'address','phone_number':'phone','email':'email'}
        if kind=='ftth_order' and customer:apply('customer',customer,{target:changes[source] for source,target in customer_map.items() if source in changes})
        if kind in {'customer','ftth_order'} and customer:
            contact_fields=set(changes) if kind=='customer' else {customer_map[f] for f in changes if f in customer_map}
            for linked in orders:apply('ftth_order',linked,{source:getattr(customer,target) for source,target in customer_map.items() if target in contact_fields})
        if kind=='ftth_order' and service and 'bandwidth' in changes:
            match=re.fullmatch(r'([\d.]+)(Mbps|Gbps)',record.bandwidth)
            speed=round(float(match[1])*(1000 if match[2]=='Gbps' else 1))
            if not 1<=speed<=10000000:raise HTTPException(422,'Activated service package must be between 1 and 10000000 Mbps')
            apply('service',service,{'bandwidth_mbps':speed})
        if kind=='service' and 'bandwidth_mbps' in changes:
            for linked in orders:
                if linked.activated_service_id==record.service_id:apply('ftth_order',linked,{'bandwidth':f'{record.bandwidth_mbps}Mbps'})
        actor=actor_context.get()
        for (entity_type,entity_id),names in affected.items():
            db.add(RecordCorrection(entity_type=entity_type,entity_id=entity_id,reason=payload.reason.strip(),changed_fields=names,actor_id=actor['id'],actor_verified=actor['verified'],request_id=actor['request_id'],previous_ticket_id=previous_ticket_id if entity_type=='incident' else None,current_ticket_id=record.tt_number if entity_type=='incident' and previous_ticket_id else None))
        if kind=='incident':
            invalidate_drafts(db,record,['engineer','escalation','customer'])
            timeline(db,record,'details_corrected',f"Corrected {', '.join(changes)}. Reason: {payload.reason.strip()}")
        elif customer:
            # Existing communication snapshots must be reviewed again after details change.
            from app.models.response import NotificationDraft
            ids=[s.service_id for s in services]
            for draft in db.query(NotificationDraft).filter(NotificationDraft.service_id.in_(ids),NotificationDraft.status.in_(['draft','reviewed'])).all():
                draft.status='discarded';draft.reviewed_at=datetime.now(timezone.utc);draft.reviewed_by=actor['id']
        db.commit();db.refresh(record)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'The corrected customer reference, FN or work-order ID conflicts with an existing record')
    except HTTPException:
        db.rollback();raise
    return {**view(db,kind,record),'outcome':'corrected'}
