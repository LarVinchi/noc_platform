from datetime import datetime, timezone, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, AwareDatetime, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload
from app.core.db import get_db
from app.core.config import settings
from app.models.monitoring import SensorMapping, MonitoringEvent
from app.models.infrastructure import FiberRoute, FiberCable
from app.models.crm import Service
from app.models.incidents import Incident, Ticket
from app.services.ticketing import generate_tt_number
from app.services.impact import impact_for_route
from app.services.operational_activity import record_event
from app.services.incident_response import initialize_response

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


class MappingInput(BaseModel):
    sensor_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")
    route_id: UUID | None = None
    cable_id: UUID | None = None
    service_id: UUID | None = None

    @model_validator(mode="after")
    def one_target(self):
        if sum(value is not None for value in (self.route_id, self.cable_id, self.service_id)) != 1:
            raise ValueError("Select exactly one route, cable or service")
        return self


class EventInput(BaseModel):
    event_id: str = Field(min_length=1, max_length=150, pattern=r"^[A-Za-z0-9_.:-]+$")
    sensor_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")
    state: Literal["down", "up", "warning", "paused", "unknown"]
    observed_at: AwareDatetime

    @model_validator(mode="after")
    def future_guard(self):
        if self.observed_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("Observation time is too far in the future")
        return self


def serialize(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


@router.get("/mappings")
def mappings(db: Session = Depends(get_db)):
    return [serialize(row) for row in db.query(SensorMapping).order_by(SensorMapping.sensor_id).all()]


@router.get("/targets")
def targets(db: Session = Depends(get_db)):
    return {"routes": [{"id": str(row.route_id), "name": row.route_name} for row in db.query(FiberRoute).order_by(FiberRoute.route_name).all()],
            "cables": [{"id": str(row.cable_id), "name": row.cable_name} for row in db.query(FiberCable).order_by(FiberCable.cable_name).all()],
            "services": [{"id": str(row.service_id), "name": f"{row.customer.customer_name} · {row.service_type} · {str(row.service_id)[:8]}"}
                         for row in db.query(Service).options(selectinload(Service.customer)).order_by(Service.created_at.desc()).all()]}


@router.post("/mappings")
def create_mapping(data: MappingInput, db: Session = Depends(get_db)):
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": "sensor:" + data.sensor_id})
    if db.get(SensorMapping, data.sensor_id):
        raise HTTPException(409, "Sensor already mapped; remapping requires a reviewed migration")
    for identifier, model in ((data.route_id, FiberRoute), (data.cable_id, FiberCable), (data.service_id, Service)):
        if identifier is not None and db.get(model, identifier) is None:
            raise HTTPException(404, "Inventory target not found")
    row = SensorMapping(**data.model_dump())
    db.add(row); db.commit(); db.refresh(row)
    return serialize(row)


@router.get("/events")
def events(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    return [serialize(row) for row in db.query(MonitoringEvent).order_by(MonitoringEvent.received_at.desc()).limit(limit).all()]


def ingest(data, db):
    # Lock event first, then sensor, including absent mappings. Both locks release
    # on commit/rollback and prevent duplicate IDs and simultaneous alarm races.
    for key in ("event:" + data.event_id, "sensor:" + data.sensor_id):
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key})
    previous = db.get(MonitoringEvent, data.event_id)
    if previous:
        if (previous.sensor_id, previous.state, previous.observed_at) != (data.sensor_id, data.state, data.observed_at):
            raise HTTPException(409, "Event ID already used with different details")
        return {"outcome": "duplicate", "event": serialize(previous)}
    mapping = db.get(SensorMapping, data.sensor_id)
    event = MonitoringEvent(**data.model_dump(), disposition="unmapped")
    db.add(event)
    if mapping:
        if mapping.last_observed_at and data.observed_at <= mapping.last_observed_at:
            event.disposition = "stale"
        else:
            event.disposition = "applied"
            incident = db.get(Incident, mapping.incident_id) if mapping.incident_id else None
            if data.state == "down" and (incident is None or incident.status in {"resolved", "closed"}):
                incident = Incident(tt_number=generate_tt_number(db, "TRANSMISSION"), ticket_category="TRANSMISSION",
                    incident_type="Monitoring Alert",
                    status="open", severity="High", reported_at=data.observed_at.astimezone(timezone.utc).replace(tzinfo=None),
                    short_description=f"PRTG sensor {data.sensor_id} reports down",
                    description="Monitoring alarm; fault cause and customer outage require NOC verification.",
                    opened_by="PRTG integration", route_id=mapping.route_id, cable_id=mapping.cable_id)
                db.add(incident); db.flush()
                initialize_response(db, incident)
                mapping.incident_id = incident.incident_id
                service_ids = [mapping.service_id] if mapping.service_id else [row['service_id'] for row in
                    impact_for_route(db, route_id=mapping.route_id, cable_id=mapping.cable_id)['services']]
                for service_id in service_ids:
                    db.add(Ticket(incident_id=incident.incident_id, service_id=service_id, priority="high"))
                record_event(db, title=f"Monitoring incident {incident.tt_number}", description=f"Sensor {data.sensor_id} reports down. Verify affected services.", incident_id=incident.incident_id)
            if data.state == "up" and mapping.last_state == "down" and incident:
                record_event(db, title=f"Monitoring alarm cleared: {incident.tt_number}",
                    description=f"Sensor {data.sensor_id} reports up. Confirm service restoration before closing the incident.", incident_id=incident.incident_id)
            mapping.last_state = data.state
            mapping.last_observed_at = data.observed_at
            event.incident_id = mapping.incident_id
    db.commit(); db.refresh(event)
    return {"outcome": "recorded", "event": serialize(event)}


@router.post("/events")
def receive_event(data: EventInput, db: Session = Depends(get_db)):
    return ingest(data, db)


@router.post("/simulate")
def simulate_event(data: EventInput, db: Session = Depends(get_db)):
    if settings.ENVIRONMENT != "development" or settings.AUTH_MODE != "preview":
        raise HTTPException(404, "Preview simulation unavailable")
    return ingest(data, db)
