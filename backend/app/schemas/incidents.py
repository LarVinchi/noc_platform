from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class IncidentCreate(BaseModel):
    # Required at logging time
    incident_type: str
    ticket_category: str  # FIBER / POWER / TECHNICAL / MAINTENANCE / OTHER -> drives the TT number

    # Everything else mirrors the historical incident log and is optional,
    # since not every incident has every field filled in at creation time.
    short_description: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    notes: Optional[str] = None
    reported_at: Optional[datetime] = None
    reason_for_delay: Optional[str] = None
    rfo_root_cause: Optional[str] = None
    rfo_root_cause_detail: Optional[str] = None
    impact: Optional[str] = None
    impact_details: Optional[str] = None
    is_planned: Optional[bool] = None
    network_route: Optional[str] = None
    network_node: Optional[str] = None
    resolution_team: Optional[str] = None
    responsible_person: Optional[str] = None
    opened_by: Optional[str] = None

    # Optional links into existing infrastructure
    route_id: Optional[UUID] = None
    cable_id: Optional[UUID] = None
    core_id: Optional[UUID] = None
    pfs_id: Optional[UUID] = None
    pfp_id: Optional[UUID] = None
    nap_id: Optional[UUID] = None
    drop_cable_id: Optional[UUID] = None


class IncidentUpdate(BaseModel):
    """Used to update status/resolution once an incident is being worked or closed."""
    status: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_team: Optional[str] = None
    resolution_method: Optional[str] = None
    rfo_root_cause: Optional[str] = None
    rfo_root_cause_detail: Optional[str] = None
    closed_by: Optional[str] = None
    notes: Optional[str] = None


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    incident_id: UUID
    tt_number: Optional[str] = None
    ticket_category: Optional[str] = None
    incident_type: str
    short_description: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    notes: Optional[str] = None
    status: str
    reported_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    reason_for_delay: Optional[str] = None
    rfo_root_cause: Optional[str] = None
    rfo_root_cause_detail: Optional[str] = None
    impact: Optional[str] = None
    impact_details: Optional[str] = None
    is_planned: Optional[bool] = None
    network_route: Optional[str] = None
    network_node: Optional[str] = None
    resolution_team: Optional[str] = None
    resolution_method: Optional[str] = None
    responsible_person: Optional[str] = None
    opened_by: Optional[str] = None
    closed_by: Optional[str] = None
