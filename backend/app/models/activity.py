from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.db import Base


class ActivityEntry(Base):
    __tablename__ = "activity_entries"
    activity_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    person = Column(String, nullable=False, index=True)
    shift = Column(String, nullable=False)
    category = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False, default="")
    status = Column(String, nullable=False, default="Open")
    severity = Column(String, nullable=True)
    affected_system = Column(String, nullable=True)
    vendor_reference = Column(String, nullable=True)
    handover = Column(Boolean, nullable=False, default=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    due_at = Column(DateTime(timezone=True), nullable=True)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.incident_id"), nullable=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("service_orders.order_id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    incident = relationship("Incident")

    @property
    def ticket_category(self):
        return self.incident.ticket_category if self.incident else None

    @property
    def ticket_id(self):
        return self.incident.tt_number if self.incident else None
