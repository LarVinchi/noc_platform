from datetime import datetime
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.activity import ActivityEntry
from app.models.incidents import Incident
from app.services.ticketing import generate_tt_number
from app.services.incident_response import initialize_response

router = APIRouter(prefix="/activities", tags=["Shift activity"])
Status = Literal["Open", "In Progress", "Pending", "Completed", "Partially Closed", "Aborted"]


class ActivityCreate(BaseModel):
    person: str = Field(min_length=1, max_length=200)
    shift: Literal["Morning", "Afternoon", "Night"]
    category: Literal["Activity / Task", "Incident", "Customer Escalation", "Maintenance", "Monitoring / Alert", "Reminder Email"]
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=10000)
    status: Status = "Open"
    severity: Literal["Critical", "High", "Medium", "Low"] | None = None
    affected_system: str | None = Field(default=None, max_length=300)
    vendor_reference: str | None = Field(default=None, max_length=300)
    handover: bool = False
    scheduled_at: datetime | None = None
    due_at: datetime | None = None
    incident_id: UUID | None = None

    @field_validator("person", "title", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("scheduled_at", "due_at")
    @classmethod
    def aware(cls, value):
        if value and value.tzinfo is None:
            raise ValueError("Include a time zone")
        return value


class ActivityResponse(ActivityCreate):
    model_config = ConfigDict(from_attributes=True)
    activity_id: UUID
    order_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ActivityUpdate(BaseModel):
    status: Status
    handover: bool | None = None


@router.get("/", response_model=list[ActivityResponse])
def list_activities(db: Session = Depends(get_db)):
    return db.query(ActivityEntry).order_by(ActivityEntry.created_at.desc()).all()


@router.post("/", response_model=ActivityResponse)
def create_activity(payload: ActivityCreate, db: Session = Depends(get_db)):
    if payload.incident_id and not db.get(Incident, payload.incident_id):
        raise HTTPException(status_code=404, detail="Linked incident not found")
    if payload.category in ("Incident", "Customer Escalation") and not payload.incident_id:
        incident = Incident(tt_number=generate_tt_number(db, "TECHNICAL"), ticket_category="TECHNICAL",
                            incident_type="Other", short_description=payload.title,
                            description=payload.description, severity=payload.severity,
                            opened_by=payload.person, status="open")
        db.add(incident)
        db.flush()
        initialize_response(db, incident)
        payload.incident_id = incident.incident_id
    entry = ActivityEntry(**payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/{activity_id}", response_model=ActivityResponse)
def update_activity(activity_id: UUID, payload: ActivityUpdate, db: Session = Depends(get_db)):
    entry = db.get(ActivityEntry, activity_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Activity not found")
    entry.status = payload.status
    if payload.handover is not None:
        entry.handover = payload.handover
    # Activity completion never closes an incident or claims service restoration.
    db.commit()
    db.refresh(entry)
    return entry
