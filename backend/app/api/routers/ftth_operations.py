from datetime import timedelta
from statistics import mean,median
from typing import Literal
from uuid import UUID,uuid4
import hashlib,json
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field,AwareDatetime
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import actor_context
from app.models.provisioning import ServiceOrder,ServiceCategory,WorkflowStage
from app.models.ftth_operations import FtthStageEvent,FtthIncidentLink
from app.models.incidents import Incident,Ticket
from app.models.crm import Service
from app.services.incident_response import ACTIVE,initialize_response,now_utc,timeline
from app.services.response_metrics import utc
from app.services.ticketing import generate_tt_number

router=APIRouter(prefix='/ftth',tags=['FTTH lifecycle and fault history'])


def row(value):
    return {column.name:getattr(value,column.name) for column in value.__table__.columns}


def order_record(db,identifier,lock=False):
    query=db.query(ServiceOrder).filter_by(order_id=identifier,service_category=ServiceCategory.FTTH)
    value=(query.with_for_update() if lock else query).populate_existing().first()
    if not value:
        raise HTTPException(404,'FTTH order not found')
    return value


def associated_ids(db,orders,extra_services=()):
    ids=[value.order_id for value in orders]; services=[value.activated_service_id for value in orders if value.activated_service_id]
    services=list(set(services)|set(extra_services))
    explicit=db.query(FtthIncidentLink.incident_id).filter(FtthIncidentLink.order_id.in_(ids)).all() if ids else []
    tickets=db.query(Ticket.incident_id).filter(Ticket.service_id.in_(services)).all() if services else []
    return {value[0] for value in explicit+tickets}


def incident_row(value,kind=None):
    fields=('incident_id','tt_number','status','severity','short_description','reported_at','resolved_at','assigned_engineer_id','responsible_person','resolution_method','rfo_root_cause','notes','ticket_category')
    return {field:getattr(value,field) for field in fields}|{'kind':kind}


@router.get('/orders/{identifier}')
def history(identifier: UUID,db: Session=Depends(get_db)):
    order=order_record(db,identifier)
    events=db.query(FtthStageEvent).filter_by(order_id=identifier).order_by(FtthStageEvent.occurred_at,FtthStageEvent.event_id).all()
    links=db.query(FtthIncidentLink).filter_by(order_id=identifier).all()
    kinds={value.incident_id:value.kind for value in links}
    incidents=db.query(Incident).filter(Incident.incident_id.in_(associated_ids(db,[order]))).order_by(Incident.reported_at.desc()).all()
    return {'order':{field:getattr(order,field) for field in ('order_id','fn_number','work_order_id','customer_name','isp','status','activated_service_id','created_at','completion_date')},
            'events':[row(value) for value in events], 'incidents':[incident_row(value,kinds.get(value.incident_id,'service_ticket')) for value in incidents],
            'history_complete':bool(events and events[0].from_stage is None and events[0].to_stage=='REQUESTED')}


class LinkInput(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True,extra='forbid')
    request_key: UUID
    kind: Literal['installation_blocker','service_fault']
    incident_id: UUID|None=None
    title: str=Field(min_length=5,max_length=200)
    note: str=Field(min_length=5,max_length=2000)
    severity: Literal['Critical','High','Medium','Low']='High'


@router.post('/orders/{identifier}/incidents')
def link_incident(identifier: UUID,data: LinkInput,db: Session=Depends(get_db)):
    order=order_record(db,identifier,lock=True)
    digest=hashlib.sha256(json.dumps(data.model_dump(mode='json',exclude={'request_key'}),sort_keys=True).encode()).hexdigest()
    retry=db.query(FtthIncidentLink).filter_by(order_id=identifier,request_key=data.request_key).first()
    if retry:
        if retry.request_hash!=digest:
            raise HTTPException(409,'This request key was already used with different details')
        return {'outcome':'already_linked','incident':incident_row(db.get(Incident,retry.incident_id),retry.kind)}
    service_id=order.activated_service_id
    if data.kind=='installation_blocker' and service_id:
        raise HTTPException(409,'Activated customers need a service fault, not an installation blocker')
    if data.kind=='service_fault':
        service=db.get(Service,service_id) if service_id else None
        if not service or service.status!='active':
            raise HTTPException(409,'A service fault requires an activated, active customer service')
    if data.incident_id:
        incident=db.query(Incident).filter_by(incident_id=data.incident_id).with_for_update().first()
        if not incident or incident.status not in ACTIVE:
            raise HTTPException(422,'Select an active incident; recurring faults need a new record')
        existing=db.query(FtthIncidentLink).filter_by(order_id=identifier,incident_id=incident.incident_id,kind=data.kind).first()
        if existing:
            return {'outcome':'already_linked','incident':incident_row(incident,data.kind)}
    else:
        incident=Incident(tt_number=generate_tt_number(db,'TRANSMISSION'),ticket_category='TRANSMISSION',incident_type='Service Unavailability' if data.kind=='service_fault' else 'Other',
            short_description=data.title,description=data.note,severity=data.severity,status='open',reported_at=now_utc().replace(tzinfo=None),
            opened_by=actor_context.get()['id'],nap_id=order.nap_id,drop_cable_id=order.drop_cable_id)
        db.add(incident);db.flush();initialize_response(db,incident)
    link=FtthIncidentLink(link_id=uuid4(),order_id=identifier,incident_id=incident.incident_id,service_id=service_id if data.kind=='service_fault' else None,
        kind=data.kind,request_key=data.request_key,request_hash=digest,note=data.note,linked_by=actor_context.get()['id'])
    db.add(link)
    if data.kind=='service_fault' and not db.query(Ticket).filter_by(incident_id=incident.incident_id,service_id=service_id).first():
        db.add(Ticket(incident_id=incident.incident_id,service_id=service_id,priority=data.severity.lower(),status='open'))
    timeline(db,incident,'ftth_linked',f'{data.kind.replace("_"," ")}: {order.fn_number or order.service_order_number}. {data.note}',key=f'ftth-link:{link.link_id}')
    db.commit();db.refresh(incident)
    return {'outcome':'created' if not data.incident_id else 'linked','incident':incident_row(incident,data.kind)}


@router.get('/reports')
def reports(start: AwareDatetime|None=None,end: AwareDatetime|None=None,isp: Literal['MTNN','METROREACH','MANGONET','TELEWYZ']|None=None,db: Session=Depends(get_db)):
    end=end or now_utc();start=start or end-timedelta(days=30)
    if end>now_utc() or start>=end or end-start>timedelta(days=366):
        raise HTTPException(422,'Choose a past reporting window of up to 366 days')
    query=db.query(ServiceOrder).filter_by(service_category=ServiceCategory.FTTH)
    if isp:query=query.filter(ServiceOrder.isp==isp)
    orders=query.all();ids=[value.order_id for value in orders]
    events=db.query(FtthStageEvent).filter(FtthStageEvent.order_id.in_(ids)).order_by(FtthStageEvent.occurred_at,FtthStageEvent.event_id).all() if ids else []
    grouped={}
    for event in events:grouped.setdefault(event.order_id,[]).append(event)
    accepted={};durations={};open_ages=[]
    for order in orders:
        previous=None; as_of=None
        for event in grouped.get(order.order_id,[]):
            if event.to_stage=='MONITORED':accepted.setdefault(order.order_id,utc(event.occurred_at))
            if utc(event.occurred_at)<=end:as_of=event
            if previous and event.from_stage==previous.to_stage and start<=utc(event.occurred_at)<end:
                minutes=(utc(event.occurred_at)-utc(previous.occurred_at)).total_seconds()/60
                durations.setdefault(previous.to_stage,[]).append(minutes)
            previous=event
        if as_of and as_of.to_stage!='MONITORED':
            open_ages.append({'order_id':order.order_id,'stage':as_of.to_stage,'minutes':(end-utc(as_of.occurred_at)).total_seconds()/60})
    ftth_services=[value[0] for value in db.query(Service.service_id).filter(Service.service_type.in_(['FTTH','ISP_FTTH'])).all()] if not isp else []
    incidents=db.query(Incident).filter(Incident.incident_id.in_(associated_ids(db,orders,ftth_services))).all()
    resolved=[value for value in incidents if value.status in {'resolved','closed'} and value.resolved_at and start<=utc(value.resolved_at)<end and value.reported_at and utc(value.resolved_at)>=utc(value.reported_at)]
    category={}
    for value in resolved:category.setdefault(value.ticket_category or 'Unset',[]).append((utc(value.resolved_at)-utc(value.reported_at)).total_seconds()/60)
    completed=[value for value in orders if value.completion_date]
    return {'start':start,'end':end,'isp':isp,'lifetime':{'requests':len(orders),'completed':len(completed),'accepted':sum(value.status==WorkflowStage.MONITORED for value in orders)},
        'period':{'requests':sum(start<=utc(value.created_at)<end for value in orders),'completed':sum(start<=utc(value.completion_date)<end for value in completed),'accepted':sum(start<=at<end for at in accepted.values()),'new_incidents':sum(start<=utc(value.reported_at)<end for value in incidents if value.reported_at),'resolved_incidents':len(resolved)},
        'backlog':{stage.value:sum(value.status==stage for value in orders) for stage in WorkflowStage if stage!=WorkflowStage.MONITORED},
        'unknown_acceptance_dates':sum(value.status==WorkflowStage.MONITORED and value.order_id not in accepted for value in orders),
        'partial_histories':sum(not grouped.get(value.order_id) or grouped[value.order_id][0].from_stage is not None for value in orders),
        'stage_durations':[{'stage':key,'samples':len(values),'mean_minutes':mean(values),'median_minutes':median(values)} for key,values in durations.items()],
        'open_stage_ages':open_ages,'active_incidents':sum(value.status in ACTIVE for value in incidents),
        'incident_mttr':[{'category':key,'samples':len(values),'mean_minutes':mean(values)} for key,values in category.items()],
        'unattributed_services':len(set(ftth_services)-{value.activated_service_id for value in orders}),
        'availability':'Unverified','handover_delivery':'Not tracked'}
