from uuid import UUID,uuid4
from typing import Literal
import hashlib,json
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,ConfigDict,EmailStr,Field,AwareDatetime,model_validator
from sqlalchemy import text,case
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.config import settings
from app.core.security import actor_context
from app.models.mail import MailTriageItem
from app.models.incidents import Incident
from app.models.provisioning import ServiceOrder,ServiceCategory
from app.services.mail_triage import classify
from app.services.incident_response import now_utc

router=APIRouter(prefix='/mail',tags=['Mail triage preview'])


def admin():return 'NOC.Admin' in actor_context.get()['roles']


def scoped(db):
    query=db.query(MailTriageItem)
    return query if admin() else query.filter_by(owner_id=actor_context.get()['id'])


def row(value):
    return {column.name:getattr(value,column.name) for column in value.__table__.columns if column.name not in {'request_key','request_hash'}}


def preview_only():
    if settings.ENVIRONMENT!='development' or settings.AUTH_MODE!='preview':
        raise HTTPException(409,'Manual mail preview is only available in local development; live mailbox ingestion is not connected')


class PreviewInput(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True,extra='forbid')
    request_key: UUID
    subject: str=Field(min_length=1,max_length=250)
    sender: EmailStr
    body: str=Field(min_length=1,max_length=20000)
    received_at: AwareDatetime|None=None

    @model_validator(mode='after')
    def not_future(self):
        if self.received_at and self.received_at>now_utc():
            raise ValueError('Received time cannot be in the future')
        return self


@router.get('/connection')
def connection():
    return {'connected':False,'mode':'manual_preview' if settings.ENVIRONMENT=='development' and settings.AUTH_MODE=='preview' else 'unavailable',
            'mailbox':None,'last_sync_at':None,'rag_connected':False,'retention_automation':False,
            'requirements':['Approved NOC mailbox identity and scoped Microsoft 365 read permissions','Connector with subscription renewal/polling and reconciliation','Agreed retention and tested classification','Colleague RAG integration and approved knowledge sources']}


@router.get('/items')
def items(state: Literal['needs_review','acknowledged','dismissed']|None=None,offset: int=Query(0,ge=0),limit: int=Query(50,ge=1,le=100),db: Session=Depends(get_db)):
    query=scoped(db)
    counts={value:query.filter_by(state=value).count() for value in ('needs_review','acknowledged','dismissed')}
    if state:query=query.filter_by(state=state)
    priority=case((MailTriageItem.classification['priority'].astext=='high',0),(MailTriageItem.classification['priority'].astext=='normal',1),else_=2)
    return {'items':[row(value) for value in query.order_by(priority,MailTriageItem.entered_at.desc(),MailTriageItem.item_id).offset(offset).limit(limit).all()],
            'total':query.count(),'counts':counts,'offset':offset,'limit':limit}


@router.post('/preview')
def preview(data: PreviewInput,db: Session=Depends(get_db)):
    preview_only()
    owner=actor_context.get()['id']
    digest=hashlib.sha256(json.dumps(data.model_dump(mode='json',exclude={'request_key'}),sort_keys=True).encode()).hexdigest()
    db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'),{'key':f'mail-preview:{owner}:{data.request_key}'})
    previous=db.query(MailTriageItem).filter_by(owner_id=owner,request_key=data.request_key).first()
    if previous:
        if previous.request_hash!=digest:raise HTTPException(409,'This preview request was already logged with different details')
        return {'outcome':'already_logged','item':row(previous)}
    classification=classify(data.subject,data.body)
    value=MailTriageItem(item_id=uuid4(),owner_id=owner,request_key=data.request_key,request_hash=digest,subject=data.subject,sender=str(data.sender),
        received_at=data.received_at,excerpt='' if classification['category']=='routine' else ' '.join(data.body.split())[:400],classification=classification,state='needs_review',source='manual_preview')
    db.add(value);db.commit();db.refresh(value)
    return {'outcome':'created','item':row(value)}


class ReviewInput(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True,extra='forbid')
    state: Literal['needs_review','acknowledged','dismissed']
    note: str=Field(min_length=5,max_length=2000)
    incident_id: UUID|None=None
    order_id: UUID|None=None


@router.patch('/items/{identifier}')
def review(identifier: UUID,data: ReviewInput,db: Session=Depends(get_db)):
    value=scoped(db).filter_by(item_id=identifier).with_for_update().populate_existing().first()
    if not value:raise HTTPException(404,'Mail review item not found')
    if data.incident_id and not db.get(Incident,data.incident_id):raise HTTPException(422,'Linked incident not found')
    order=db.get(ServiceOrder,data.order_id) if data.order_id else None
    if data.order_id and (not order or order.service_category!=ServiceCategory.FTTH):raise HTTPException(422,'Linked FTTH order not found')
    value.state=data.state;value.action_note=data.note
    if 'incident_id' in data.model_fields_set:value.incident_id=data.incident_id
    if 'order_id' in data.model_fields_set:value.order_id=data.order_id
    value.reviewed_by=actor_context.get()['id'];value.reviewed_at=now_utc()
    db.commit();db.refresh(value)
    return row(value)
