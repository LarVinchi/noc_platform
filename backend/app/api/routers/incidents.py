from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.incidents import Incident
from app.schemas.incidents import IncidentCreate, IncidentUpdate, IncidentResponse
from app.services.ticketing import generate_tt_number

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
        **incident_in.model_dump(exclude={"reported_at"}),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


@router.get("/", response_model=List[IncidentResponse])
def list_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    ticket_category: Optional[str] = None,
    search: Optional[str] = Query(None, description="Matches TT number or short description"),
    db: Session = Depends(get_db),
):
    """List/filter incidents — powers the Incident Management table view."""
    q = db.query(Incident)
    if status:
        q = q.filter(Incident.status == status)
    if severity:
        q = q.filter(Incident.severity == severity)
    if ticket_category:
        q = q.filter(Incident.ticket_category == ticket_category)
    if search:
        like = f"%{search}%"
        q = q.filter(
            (Incident.tt_number.ilike(like)) | (Incident.short_description.ilike(like))
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
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    for field, value in update_in.model_dump(exclude_unset=True).items():
        setattr(incident, field, value)

    db.commit()
    db.refresh(incident)
    return incident