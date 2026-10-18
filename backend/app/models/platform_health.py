from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.db import Base


class PlatformHost(Base):
    __tablename__ = 'platform_hosts'
    host_id = Column(String(64), primary_key=True)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False)
    payload = Column(JSONB, nullable=False)


class PlatformSample(Base):
    __tablename__ = 'platform_samples'
    sample_id = Column(UUID(as_uuid=True), primary_key=True)
    host_id = Column(String(64), ForeignKey('platform_hosts.host_id'), nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    digest = Column(String(64), nullable=False)
    cpu_percent = Column(Float)
    memory_percent = Column(Float, nullable=False)
    storage_percent = Column(Float)
    __table_args__ = (Index('ix_platform_samples_host_time', 'host_id', 'observed_at'),)
