"""Energy import revisions and isolated collector trial events."""
from sqlalchemy import Column, String, DateTime, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.db import Base


class EnergyImport(Base):
    __tablename__ = 'energy_imports'
    import_id = Column(UUID(as_uuid=True), primary_key=True)
    content_hash = Column(String(64), nullable=False, unique=True)
    source_name = Column(String(200), nullable=False)
    records = Column(JSONB, nullable=False)
    record_count = Column(Integer, nullable=False)
    entered_by = Column(String(100), nullable=False)
    entered_at = Column(DateTime(timezone=True), nullable=False, server_default=text('now()'))


class EnergyTrialEvent(Base):
    __tablename__ = 'energy_trial_events'
    event_id = Column(UUID(as_uuid=True), primary_key=True)
    request_key = Column(UUID(as_uuid=True), nullable=False, unique=True)
    request_hash = Column(String(64), nullable=False)
    site = Column(String(20), nullable=False)
    revision = Column(Integer, nullable=False)
    effective_at = Column(DateTime(timezone=True), nullable=False)
    observation = Column(JSONB, nullable=False)
    entered_by = Column(String(100), nullable=False)
    entered_at = Column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    __table_args__ = (UniqueConstraint('site', 'revision', name='uq_energy_trial_revision'),)
