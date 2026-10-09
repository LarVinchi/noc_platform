from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.core.db import Base


class Engineer(Base):
    __tablename__ = "engineers"
    engineer_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(String(200), nullable=False)
    email = Column(String(320), nullable=False, unique=True)
    team = Column(String(100), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)


class ResponsePolicy(Base):
    __tablename__ = "response_policies"
    policy_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(String(200), nullable=False)
    severity = Column(String(20))
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.service_id"))
    version = Column(Integer, nullable=False)
    acknowledgment_minutes = Column(Integer, nullable=False)
    restoration_minutes = Column(Integer, nullable=False)
    followup_minutes = Column(Integer, nullable=False, default=60)
    default_engineer_id = Column(UUID(as_uuid=True), ForeignKey("engineers.engineer_id"))
    escalation_recipients = Column(JSONB, nullable=False, default=list)
    preview_only = Column(Boolean, nullable=False, default=True)
    effective_from = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (CheckConstraint("num_nonnulls(severity, service_id) = 1", name="ck_response_policy_scope"),)


class ServiceOutage(Base):
    __tablename__ = "service_outages"
    outage_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.incident_id"), nullable=False, index=True)
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.service_id"), nullable=False, index=True)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("response_policies.policy_id"))
    started_at = Column(DateTime(timezone=True), nullable=False)
    restored_at = Column(DateTime(timezone=True))
    ack_deadline_at = Column(DateTime(timezone=True))
    restore_deadline_at = Column(DateTime(timezone=True))
    confirmed_by = Column(String(100), nullable=False)
    restored_by = Column(String(100))
    confirmation_note = Column(Text, nullable=False)
    restoration_note = Column(Text)
    excluded = Column(Boolean, nullable=False, default=False)
    exclusion_reason = Column(String(500))
    service = relationship("Service")
    incident = relationship("Incident")


class ResponseEvent(Base):
    __tablename__ = "response_events"
    event_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    event_key = Column(String(250), nullable=False, unique=True)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.incident_id"), nullable=False, index=True)
    outage_id = Column(UUID(as_uuid=True), ForeignKey("service_outages.outage_id"))
    event_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    actor_id = Column(String(100), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False)


class NotificationDraft(Base):
    __tablename__ = "notification_drafts"
    draft_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    event_key = Column(String(250), nullable=False, unique=True)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.incident_id"), nullable=False, index=True)
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.service_id"))
    audience = Column(String(30), nullable=False)
    recipients = Column(JSONB, nullable=False, default=list)
    subject = Column(String(250), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    reviewed_at = Column(DateTime(timezone=True))
    reviewed_by = Column(String(100))


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    worker_name = Column(String(100), primary_key=True)
    updated_at = Column(DateTime(timezone=True), nullable=False)
