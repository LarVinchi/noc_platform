from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.db import Base


class KnowledgeApproval(Base):
    __tablename__ = 'knowledge_approvals'
    version_id = Column(UUID(as_uuid=True), ForeignKey('document_versions.version_id'), primary_key=True)
    approved = Column(Boolean, nullable=False)
    reviewed_by = Column(String(100), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=False)
    note = Column(Text, nullable=False)


class KnowledgeEvent(Base):
    __tablename__ = 'knowledge_events'
    event_id = Column(UUID(as_uuid=True), primary_key=True)
    actor_id = Column(String(100), nullable=False)
    kind = Column(String(40), nullable=False)
    source_versions = Column(JSONB, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
