from datetime import timedelta
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, model_validator
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session, selectinload
from app.core.config import settings
from app.core.db import get_db
from app.core.security import actor_context
from app.models.crm import Service
from app.models.incidents import Incident, Ticket
from app.models.response import Engineer, ResponsePolicy, ServiceOutage, ResponseEvent, NotificationDraft, WorkerHeartbeat
from app.services.incident_response import ACTIVE, assign_engineer, draft, invalidate_drafts, now_utc, pin_policy, preview_policies, timeline, usable_policy
from app.services.response_metrics import deadline_state, union_seconds, utc

router = APIRouter(prefix='/operations', tags=['Response, escalation and service targets'])


def row(record):
    return {column.name: getattr(record, column.name) for column in record.__table__.columns}


def incident_row(incident, now=None):
    return {**row(incident), 'ack_target_state': deadline_state(incident.ack_deadline_at, incident.acknowledged_at, now or now_utc(), bool(incident.is_planned)),
            'restore_target_state': deadline_state(incident.restore_deadline_at, incident.resolved_at, now or now_utc(), bool(incident.is_planned))}


def outage_row(outage, now=None):
    return {**row(outage), 'customer': outage.service.customer.customer_name, 'service_type': outage.service.service_type,
            'ack_target_state': deadline_state(outage.ack_deadline_at, outage.incident.acknowledged_at, now or now_utc(), outage.excluded),
            'restore_target_state': deadline_state(outage.restore_deadline_at, outage.restored_at, now or now_utc(), outage.excluded),
            'restoration_minutes': (utc(outage.restored_at) - utc(outage.started_at)).total_seconds()/60 if outage.restored_at else None}


def locked_incident(db, identifier):
    record = db.query(Incident).filter_by(incident_id=identifier).with_for_update().first()
    if record is None:
        raise HTTPException(404, 'Incident not found')
    return record


class WriteModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')


class EngineerInput(WriteModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    team: str = Field(min_length=1, max_length=100)


class EngineerStatus(WriteModel):
    enabled: bool


class PolicyInput(WriteModel):
    name: str = Field(min_length=1, max_length=200)
    severity: Literal['Critical', 'High', 'Medium', 'Low'] | None = None
    service_id: UUID | None = None
    acknowledgment_minutes: int = Field(gt=0, le=43200)
    restoration_minutes: int = Field(gt=0, le=43200)
    followup_minutes: int = Field(default=60, gt=0, le=10080)
    default_engineer_id: UUID | None = None
    escalation_recipients: list[EmailStr] = Field(default_factory=list, max_length=20)
    preview_only: bool = True
    effective_from: AwareDatetime | None = None

    @model_validator(mode='after')
    def validate_scope(self):
        if (self.severity is None) == (self.service_id is None):
            raise ValueError('Choose a severity or a service, not both')
        if self.restoration_minutes < self.acknowledgment_minutes:
            raise ValueError('Restoration target must not precede acknowledgment target')
        return self


class Assignment(WriteModel):
    engineer_id: UUID


class OutageInput(WriteModel):
    service_id: UUID
    started_at: AwareDatetime
    note: str = Field(min_length=5, max_length=2000)
    excluded: bool = False
    exclusion_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode='after')
    def validate_time(self):
        if self.started_at > now_utc():
            raise ValueError('A confirmed outage cannot start in the future')
        if self.excluded and not self.exclusion_reason:
            raise ValueError('An exclusion requires an explicit reason')
        return self


class RestoreInput(WriteModel):
    restored_at: AwareDatetime | None = None
    note: str = Field(min_length=5, max_length=2000)


class DraftInput(WriteModel):
    status: Literal['draft', 'reviewed', 'discarded']
    recipients: list[EmailStr] | None = Field(default=None, max_length=20)
    subject: str | None = Field(default=None, min_length=1, max_length=250)
    body: str | None = Field(default=None, min_length=1, max_length=10000)


@router.get('/engineers')
def engineers(db: Session = Depends(get_db)):
    return [row(value) for value in db.query(Engineer).order_by(Engineer.name).all()]


@router.get('/services')
def provisioned_services(db: Session = Depends(get_db)):
    return [{'id':str(value.service_id), 'name':f'{value.customer.customer_name} · {value.service_type} · {str(value.service_id)[:8]}'}
            for value in db.query(Service).options(selectinload(Service.customer)).filter_by(status='active').order_by(Service.created_at.desc()).limit(1000).all()]


@router.post('/engineers')
def create_engineer(data: EngineerInput, db: Session = Depends(get_db)):
    email = str(data.email).lower()
    db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'), {'key': 'engineer:' + email})
    if db.query(Engineer).filter(func.lower(Engineer.email) == email).first():
        raise HTTPException(409, 'Engineer email already registered')
    record = Engineer(name=data.name, email=email, team=data.team, enabled=True)
    db.add(record); db.commit(); db.refresh(record)
    return row(record)


@router.patch('/engineers/{identifier}')
def enable_engineer(identifier: UUID, data: EngineerStatus, db: Session = Depends(get_db)):
    record = db.get(Engineer, identifier)
    if not record:
        raise HTTPException(404, 'Engineer not found')
    record.enabled = data.enabled; db.commit(); db.refresh(record)
    return row(record)


@router.get('/policies')
def policies(db: Session = Depends(get_db)):
    return [row(value) for value in db.query(ResponsePolicy).order_by(ResponsePolicy.effective_from.desc(), ResponsePolicy.version.desc()).all()]


@router.post('/policies')
def create_policy(data: PolicyInput, db: Session = Depends(get_db)):
    if data.service_id and not db.get(Service, data.service_id):
        raise HTTPException(404, 'Service not found')
    if data.default_engineer_id:
        engineer = db.get(Engineer, data.default_engineer_id)
        if not engineer or not engineer.enabled:
            raise HTTPException(422, 'Select an enabled engineer')
    key = f'policy:{data.service_id or data.severity}'
    db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'), {'key': key})
    query = db.query(func.max(ResponsePolicy.version))
    query = query.filter(ResponsePolicy.service_id == data.service_id) if data.service_id else query.filter(ResponsePolicy.severity == data.severity)
    version = (query.scalar() or 0) + 1
    record = ResponsePolicy(**{**data.model_dump(), 'effective_from': data.effective_from or now_utc().replace(microsecond=0), 'version': version})
    db.add(record); db.commit(); db.refresh(record)
    return row(record)


@router.post('/policies/preview')
def initialize_preview_policies(db: Session = Depends(get_db)):
    db.execute(text('SELECT pg_advisory_xact_lock(72184097)'))
    if not preview_policies(db):
        raise HTTPException(404, 'Preview policies are unavailable in this environment')
    db.commit()
    return {'status': 'preview policies ready'}


@router.get('/summary')
def summary(db: Session = Depends(get_db)):
    now = now_utc()
    active = [incident_row(value, now) for value in db.query(Incident).filter(Incident.status.in_(ACTIVE)).order_by(Incident.reported_at).all()]
    heartbeat = db.get(WorkerHeartbeat, 'response-escalation')
    return {'incidents': active, 'unassigned': sum(value['assigned_engineer_id'] is None for value in active),
            'ack_overdue': sum(value['ack_target_state'] == 'breached' and value['acknowledged_at'] is None for value in active),
            'restore_overdue': sum(value['restore_target_state'] == 'breached' for value in active),
            'pending_drafts': db.query(NotificationDraft).filter_by(status='draft').count(),
            'worker': {'last_cycle_at': heartbeat.updated_at if heartbeat else None, 'healthy': bool(heartbeat and (now-utc(heartbeat.updated_at)).total_seconds()<120)}, 'as_of': now}


@router.get('/incidents/{identifier}')
def details(identifier: UUID, db: Session = Depends(get_db)):
    incident = db.get(Incident, identifier)
    if incident is None:
        raise HTTPException(404, 'Incident not found')
    outages = db.query(ServiceOutage).options(selectinload(ServiceOutage.service).selectinload(Service.customer), selectinload(ServiceOutage.incident)).filter_by(incident_id=identifier).order_by(ServiceOutage.started_at).all()
    return {'incident': incident_row(incident), 'policy': row(db.get(ResponsePolicy, incident.response_policy_id)) if incident.response_policy_id else None,
            'outages': [outage_row(value) for value in outages],
            'candidate_services': [str(value[0]) for value in db.query(Ticket.service_id).filter(Ticket.incident_id==identifier, Ticket.service_id.isnot(None)).distinct().all()],
            'timeline': [row(value) for value in db.query(ResponseEvent).filter_by(incident_id=identifier).order_by(ResponseEvent.occurred_at.desc()).limit(200).all()]}


@router.post('/incidents/{identifier}/assign')
def assign(identifier: UUID, data: Assignment, db: Session = Depends(get_db)):
    incident = locked_incident(db, identifier)
    if incident.status not in ACTIVE:
        raise HTTPException(409, 'Assign only active incidents')
    engineer = db.get(Engineer, data.engineer_id)
    if not engineer or not engineer.enabled:
        raise HTTPException(422, 'Select an enabled engineer')
    assign_engineer(db, incident, engineer); db.commit(); db.refresh(incident)
    return incident_row(incident)


@router.post('/incidents/{identifier}/acknowledge')
def acknowledge(identifier: UUID, db: Session = Depends(get_db)):
    incident = locked_incident(db, identifier)
    if incident.acknowledged_at:
        return incident_row(incident)
    if incident.status not in ACTIVE or not incident.assigned_engineer_id:
        raise HTTPException(409, 'Assign an engineer to this active incident before acknowledging')
    incident.acknowledged_at = now_utc(); incident.acknowledged_by = actor_context.get()['id']
    if incident.status == 'open':
        incident.status = 'investigating'
    timeline(db, incident, 'acknowledged', 'NOC acknowledged engineer ownership and started the response.', key=f'ack:{identifier}')
    db.commit(); db.refresh(incident)
    return incident_row(incident)


@router.post('/incidents/{identifier}/policy')
def apply_current_policy(identifier: UUID, db: Session = Depends(get_db)):
    incident = locked_incident(db, identifier)
    if incident.status not in ACTIVE:
        raise HTTPException(409, 'Apply policies only to active incidents')
    pin_policy(db, incident, at=now_utc())
    if not incident.response_policy_id:
        raise HTTPException(409, 'No effective policy for this severity; configure one first')
    db.commit(); db.refresh(incident)
    return incident_row(incident)


@router.post('/incidents/{identifier}/outages')
def confirm_outage(identifier: UUID, data: OutageInput, db: Session = Depends(get_db)):
    incident = locked_incident(db, identifier)
    if incident.status not in ACTIVE:
        raise HTTPException(409, 'Confirm outages on an active incident')
    service = db.get(Service, data.service_id)
    if not service or service.status != 'active':
        raise HTTPException(422, 'Select an active provisioned service')
    previous = db.query(ServiceOutage).filter_by(incident_id=identifier, service_id=data.service_id, restored_at=None).first()
    if previous:
        if utc(previous.started_at) != utc(data.started_at) or previous.confirmation_note != data.note or previous.excluded != data.excluded or previous.exclusion_reason != data.exclusion_reason:
            raise HTTPException(409, 'An open outage is already recorded with different details')
        return outage_row(previous)
    policy = usable_policy(db, service_id=data.service_id, at=data.started_at)
    outage = ServiceOutage(incident_id=identifier, service_id=data.service_id, policy_id=policy.policy_id if policy else None,
                           started_at=data.started_at, confirmation_note=data.note, confirmed_by=actor_context.get()['id'], excluded=data.excluded, exclusion_reason=data.exclusion_reason,
                           ack_deadline_at=data.started_at+timedelta(minutes=policy.acknowledgment_minutes) if policy else None,
                           restore_deadline_at=data.started_at+timedelta(minutes=policy.restoration_minutes) if policy else None)
    db.add(outage); db.flush()
    if not db.query(Ticket).filter_by(incident_id=identifier, service_id=data.service_id).first():
        db.add(Ticket(incident_id=identifier, service_id=data.service_id))
    key = f'outage:{outage.outage_id}:confirmed'
    timeline(db, incident, 'outage_confirmed', f'{service.customer.customer_name}: {service.service_type} outage confirmed. {data.note}', key=key, outage_id=outage.outage_id)
    draft(db, incident, key, 'customer', [service.customer.email], f'Service outage: {incident.tt_number}',
          f'Dear {service.customer.customer_name},\nThe NOC has confirmed an outage affecting your {service.service_type} service.\nReference: {incident.tt_number}.\nThe incident is being tracked. Restoration time is not yet confirmed.\nReview recipient and wording before sending.', service_id=service.service_id)
    db.commit(); db.refresh(outage)
    return outage_row(outage)


@router.post('/outages/{identifier}/restore')
def restore(identifier: UUID, data: RestoreInput, db: Session = Depends(get_db)):
    existing = db.get(ServiceOutage, identifier)
    if not existing:
        raise HTTPException(404, 'Outage not found')
    incident = locked_incident(db, existing.incident_id)
    outage = db.query(ServiceOutage).filter_by(outage_id=identifier).with_for_update().populate_existing().one()
    if outage.restored_at:
        return outage_row(outage)
    at = data.restored_at or now_utc()
    if at > now_utc() or utc(at) < utc(outage.started_at):
        raise HTTPException(422, 'Restoration must be between outage start and the current time')
    outage.restored_at = at; outage.restored_by = actor_context.get()['id']; outage.restoration_note = data.note
    key = f'outage:{identifier}:restored'
    timeline(db, incident, 'service_restored', f'{outage.service.customer.customer_name}: restoration verified. {data.note}', key=key, outage_id=identifier)
    invalidate_drafts(db,incident,['customer'],outage.service_id)
    other_open = db.query(ServiceOutage).filter(ServiceOutage.service_id==outage.service_id,ServiceOutage.outage_id!=identifier,ServiceOutage.restored_at.is_(None)).count()
    subject = f"{'Partial restoration update' if other_open else 'Service restoration update'}: {incident.tt_number}"
    caveat = f'{other_open} other confirmed outage record(s) remain open for this service. Reconcile those records before claiming full service restoration.' if other_open else 'Review the restoration evidence and this message before delivery.'
    draft(db, incident, key, 'customer', [outage.service.customer.email], subject,
          f'Dear {outage.service.customer.customer_name},\nRestoration for the outage tracked under {incident.tt_number} was verified at {utc(at).isoformat()}.\n{caveat}', service_id=outage.service_id)
    db.commit(); db.refresh(outage)
    return outage_row(outage)


@router.get('/drafts')
def drafts(incident_id: UUID | None = None, db: Session = Depends(get_db)):
    query = db.query(NotificationDraft)
    if incident_id:
        query = query.filter_by(incident_id=incident_id)
    return [row(value) for value in query.order_by(NotificationDraft.created_at.desc()).limit(200).all()]


@router.patch('/drafts/{identifier}')
def review_draft(identifier: UUID, data: DraftInput, db: Session = Depends(get_db)):
    existing=db.get(NotificationDraft,identifier)
    if existing:
        locked_incident(db,existing.incident_id)
    record = db.query(NotificationDraft).filter_by(draft_id=identifier).with_for_update().populate_existing().first()
    if not record:
        raise HTTPException(404, 'Draft not found')
    if record.status=='discarded' and data.status!='discarded':
        raise HTTPException(409,'Discarded or superseded drafts cannot be re-reviewed; use the current incident update')
    for field in ('recipients','subject','body'):
        value = getattr(data, field)
        if value is not None:
            setattr(record, field, value)
    if data.status == 'reviewed' and not record.recipients:
        raise HTTPException(422, 'Add a valid recipient before marking the draft reviewed')
    record.status = data.status
    record.reviewed_at = now_utc() if data.status != 'draft' else None
    record.reviewed_by = actor_context.get()['id'] if data.status != 'draft' else None
    db.commit(); db.refresh(record)
    return row(record)


@router.get('/reports')
def reports(start: AwareDatetime | None = None, end: AwareDatetime | None = None, db: Session = Depends(get_db)):
    end = end or now_utc(); start = start or end-timedelta(days=30)
    if end > now_utc() or start >= end or end-start > timedelta(days=366):
        raise HTTPException(422, 'Choose a past reporting window of up to 366 days')
    outages = db.query(ServiceOutage).options(selectinload(ServiceOutage.service).selectinload(Service.customer), selectinload(ServiceOutage.incident)).filter(ServiceOutage.started_at<end, or_(ServiceOutage.restored_at.is_(None), ServiceOutage.restored_at>=start)).all()
    measured = [value for value in outages if not value.excluded]
    restored = [value for value in measured if value.restored_at and start <= utc(value.restored_at) <= end]
    by_service = {}
    for outage in measured:
        by_service.setdefault(str(outage.service_id), []).append(outage)
    service_rows = []
    for identifier, values in by_service.items():
        service_rows.append({'service_id': identifier, 'customer': values[0].service.customer.customer_name,
                             'recorded_downtime_minutes': union_seconds([(value.started_at,value.restored_at) for value in values],start,end)/60,
                             'outage_count': len(values)})
    return {'start':start, 'end':end, 'restored_outage_count':len(restored),
            'mttr_minutes': sum((utc(value.restored_at)-utc(value.started_at)).total_seconds()/60 for value in restored)/len(restored) if restored else None,
            'open_outage_count':sum(value.restored_at is None or utc(value.restored_at)>end for value in measured),
            'excluded_count':len(outages)-len(measured), 'service_count':len(by_service),
            'services':service_rows, 'outages':[outage_row(value,end) for value in sorted(outages,key=lambda value:utc(value.started_at),reverse=True)[:200]],
            'outage_count':len(outages), 'monitoring_coverage':'unverified', 'availability_percent':None}
