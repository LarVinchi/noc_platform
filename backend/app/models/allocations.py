from sqlalchemy import Column, String, Integer, Date, DateTime, ForeignKey, text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, date

from app.core.db import Base

class CoreAllocation(Base):
    __tablename__ = "core_allocations"

    allocation_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.service_id", ondelete="CASCADE"), nullable=False)
    core_id = Column(UUID(as_uuid=True), ForeignKey("fiber_cores.core_id", ondelete="CASCADE"), nullable=False)
    allocation_role = Column(String, default="primary")
    start_date = Column(Date, default=date.today)
    end_date = Column(Date, nullable=True) # If NULL, the allocation is currently active

    # Relationships
    service = relationship("Service", backref="core_allocations")
    core = relationship("FiberCore", backref="allocations")

class DropAllocation(Base):
    __tablename__ = "drop_allocations"

    allocation_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.service_id", ondelete="CASCADE"), nullable=False)
    drop_cable_id = Column(UUID(as_uuid=True), ForeignKey("drop_cables.drop_cable_id", ondelete="CASCADE"), nullable=False)
    nap_port_number = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    service = relationship("Service", backref="drop_allocations")
    drop_cable = relationship("DropCable", backref="allocations")