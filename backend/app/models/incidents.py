from sqlalchemy import Column, String, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.db import Base

class Incident(Base):
    __tablename__ = "incidents"

    incident_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    incident_type = Column(String, nullable=False) # fiber_cut, equipment, etc.
    description = Column(String)
    reported_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="open")

    # The incident can be tied to ANY level of the physical infrastructure
    route_id = Column(UUID(as_uuid=True), ForeignKey("fiber_routes.route_id"))
    cable_id = Column(UUID(as_uuid=True), ForeignKey("fiber_cables.cable_id"))
    core_id = Column(UUID(as_uuid=True), ForeignKey("fiber_cores.core_id"))
    pfs_id = Column(UUID(as_uuid=True), ForeignKey("pfs.pfs_id"))
    pfp_id = Column(UUID(as_uuid=True), ForeignKey("pfp.pfp_id"))
    nap_id = Column(UUID(as_uuid=True), ForeignKey("nap.nap_id"))
    drop_cable_id = Column(UUID(as_uuid=True), ForeignKey("drop_cables.drop_cable_id"))

    # Relationships
    tickets = relationship("Ticket", back_populates="incident", cascade="all, delete")

class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.incident_id"), nullable=False)
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.service_id"), nullable=True)
    assigned_to = Column(String)
    priority = Column(String, default="medium")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String, default="open")

    # Relationships
    incident = relationship("Incident", back_populates="tickets")
    service = relationship("Service") # Allows finding affected customers directly