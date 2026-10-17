"""Energy import revisions and isolated collector trial events."""
from sqlalchemy import Column, String, DateTime, Integer, UniqueConstraint, ForeignKey, text
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


class EnergySourceRevision(Base):
    __tablename__ = 'energy_source_revisions'
    revision_id = Column(UUID(as_uuid=True), primary_key=True)
    source_key = Column(String(64), nullable=False)
    remote_etag = Column(String(1024), nullable=False)
    import_id = Column(UUID(as_uuid=True), ForeignKey('energy_imports.import_id'), nullable=False)
    content_hash = Column(String(64), nullable=False)
    source_modified_at = Column(DateTime(timezone=True), nullable=False)
    captured_at = Column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    __table_args__ = (UniqueConstraint('source_key', 'remote_etag', name='uq_energy_source_version'),)


class EnergySyncState(Base):
    __tablename__ = 'energy_sync_state'
    name = Column(String(40), primary_key=True)
    source_key = Column(String(64), nullable=False)
    active_revision_id = Column(UUID(as_uuid=True), ForeignKey('energy_source_revisions.revision_id'))
    remote_etag = Column(String(1024))
    source_name = Column(String(200))
    source_modified_at = Column(DateTime(timezone=True))
    last_checked_at = Column(DateTime(timezone=True))
    last_success_at = Column(DateTime(timezone=True))
    last_import_at = Column(DateTime(timezone=True))
    next_attempt_at = Column(DateTime(timezone=True))
    requested_at = Column(DateTime(timezone=True))
    failure_count = Column(Integer, nullable=False, default=0)
    last_error_code = Column(String(80))
    last_error_message = Column(String(300))
