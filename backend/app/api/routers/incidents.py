from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.incidents import Incident
from app.schemas.incidents import IncidentCreate, IncidentUpdate, IncidentResponse
from app.services.ticketing import generate_tt_number
from app.services.incident_response import initialize_response, assign_engineer, invalidate_drafts, timeline, now_utc
from app.services.response_metrics import utc
from app.models.response import Engineer, ServiceOutage
from app.models.ftth_operations import FtthIncidentLink
from app.models.crm import Service
from app.models.incidents import Ticket
from app.core.security import actor_context
from app.models.corrections import IncidentTicketIdentifier

router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.post("/", response_model=IncidentResponse)
def create_incident(incident_in: IncidentCreate, db: Session = Depends(get_db)):
    """
    Logs a new incident and auto-generates its TT number
    (e.g. PW_IM_04092026_0515) — this is what replaces manual
    Excel entry on the frontend Incident Management page.
    """
    tt_number = generate_tt_number(db, incident_in.ticket_category)

    incident = Incident(
        tt_number=tt_number,
        status="open",
        reported_at=incident_in.reported_at or datetime.utcnow(),
        **incident_in.model_dump(exclude={"reported_at", "assigned_engineer_id"}),
    )
    db.add(incident)
    db.flush()
    db.add(IncidentTicketIdentifier(ticket_id=tt_number,incident_id=incident.incident_id))
    if incident_in.assigned_engineer_id:
        engineer = db.get(Engineer, incident_in.assigned_engineer_id)
        if not engineer or not engineer.enabled:
            raise HTTPException(422, detail="Select an enabled engineer")
        assign_engineer(db, incident, engineer)
    initialize_response(db, incident)
    db.commit()
    db.refresh(incident)
    return incident


@router.get("/", response_model=List[IncidentResponse])
def list_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    ticket_category: Optional[str] = None,
    search: Optional[str] = Query(None, description="Matches current/previous Ticket ID or short description"),
    db: Session = Depends(get_db),
):
    """List/filter incidents — powers the Incident Management table view."""
    q = db.query(Incident)
    if status:
        q = q.filter(Incident.status == status)
    if severity:
        q = q.filter(Incident.severity == severity)
    if ticket_category:
        category = ticket_category.strip().upper()
        q = q.filter(Incident.ticket_category == ("TRANSMISSION" if category == "TECHNICAL" else category))
    if search:
        like = f"%{search}%"
        q = q.filter(
            (Incident.tt_number.ilike(like)) | (Incident.short_description.ilike(like)) |
            Incident.incident_id.in_(db.query(IncidentTicketIdentifier.incident_id).filter(IncidentTicketIdentifier.ticket_id.ilike(like)))
        )
    return q.order_by(Incident.reported_at.desc()).all()


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: UUID, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.patch("/{incident_id}", response_model=IncidentResponse)
def update_incident(incident_id: UUID, update_in: IncidentUpdate, db: Session = Depends(get_db)):
    """Update status/resolution fields as an incident is worked and closed."""
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).with_for_update().first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    changes = update_in.model_dump(exclude_unset=True)
    final_status = changes.get('status', incident.status)
    ftth_linked = db.query(FtthIncidentLink).filter_by(incident_id=incident_id).first()
    if not ftth_linked:
        ftth_linked = db.query(Ticket).join(Service,Service.service_id==Ticket.service_id).filter(
            Ticket.incident_id==incident_id,Service.service_type.in_(['FTTH','ISP_FTTH'])).first()
    if ftth_linked and final_status in {'resolved','closed'}:
        method=changes.get('resolution_method',incident.resolution_method) or ''
        cause=changes.get('rfo_root_cause',incident.rfo_root_cause) or ''
        if len(method.strip())<5 or len(cause.strip())<3:
            raise HTTPException(422,detail='FTTH resolution requires the action/evidence (at least 5 characters) and root cause (at least 3 characters)')
    if ftth_linked and final_status=='aborted' and len((changes.get('notes',incident.notes) or '').strip())<5:
        raise HTTPException(422,detail='Aborting a linked FTTH incident requires an explicit reason')
    if final_status in {'resolved','closed','aborted'} and db.query(ServiceOutage).filter_by(incident_id=incident_id, restored_at=None).first():
        raise HTTPException(409, detail='Verify restoration for every confirmed service outage before resolving, closing or aborting the incident')
    if final_status in {'resolved','closed'}:
        at = changes.get('resolved_at') or incident.resolved_at or now_utc()
        if utc(at) < utc(incident.reported_at) or utc(at) > now_utc():
            raise HTTPException(422, detail='Resolution time must be between report time and the current time')
        changes['resolved_at'] = utc(at).replace(tzinfo=None)
    elif changes.get('resolved_at') is not None:
        raise HTTPException(422, detail='Only resolved or closed incidents can have a resolution timestamp')
    if incident.status in {'resolved','closed','aborted'} and final_status in {'open','investigating','pending'}:
        raise HTTPException(409, detail='Log a new incident for a recurring fault; completed incident history is preserved')
    if final_status != incident.status:
        if ftth_linked and final_status in {'resolved','closed','aborted'}:
            changes['closed_by']=actor_context.get()['id']
        timeline(db, incident, 'status_changed', f'Incident status {incident.status} → {final_status}.')
        if final_status in {'resolved','closed','aborted'}:
            invalidate_drafts(db,incident,['engineer','escalation'])
    for field, value in changes.items():
        setattr(incident, field, value)

    db.commit()
    db.refresh(incident)
    return incident
