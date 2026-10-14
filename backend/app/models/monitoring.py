from sqlalchemy import Column, String, DateTime, ForeignKey, text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.core.db import Base


class SensorMapping(Base):
    __tablename__ = "sensor_mappings"
    sensor_id = Column(String(100), primary_key=True)
    route_id = Column(UUID(as_uuid=True), ForeignKey("fiber_routes.route_id"))
    cable_id = Column(UUID(as_uuid=True), ForeignKey("fiber_cables.cable_id"))
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.service_id"))
    last_state = Column(String(20))
    last_observed_at = Column(DateTime(timezone=True))
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.incident_id"))
    __table_args__ = (CheckConstraint("num_nonnulls(route_id, cable_id, service_id) = 1", name="ck_sensor_one_target"),)


class MonitoringEvent(Base):
    __tablename__ = "monitoring_events"
    event_id = Column(String(150), primary_key=True)
    sensor_id = Column(String(100), nullable=False, index=True)
    state = Column(String(20), nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    disposition = Column(String(30), nullable=False)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.incident_id"))
