from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.db import Base


class Document(Base):
    __tablename__ = 'documents'
    document_id = Column(UUID(as_uuid=True), primary_key=True)
    title = Column(String(200), nullable=False)
    document_type = Column(String(40), nullable=False)
    owner_id = Column(String(100), nullable=False)
    visibility = Column(String(20), nullable=False, default='private')
    order_id = Column(UUID(as_uuid=True), ForeignKey('service_orders.order_id'))
    service_id = Column(UUID(as_uuid=True), ForeignKey('services.service_id'))
    customer_id = Column(UUID(as_uuid=True), ForeignKey('customers.customer_id'))
    incident_id = Column(UUID(as_uuid=True), ForeignKey('incidents.incident_id'))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    __table_args__ = (CheckConstraint("visibility IN ('private','noc')", name='ck_document_visibility'),)


class DocumentVersion(Base):
    __tablename__ = 'document_versions'
    version_id = Column(UUID(as_uuid=True), primary_key=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.document_id'), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    storage_key = Column(String(200), nullable=False, unique=True)
    original_filename = Column(String(240), nullable=False)
    media_type = Column(String(100), nullable=False)
    byte_size = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    uploaded_by = Column(String(100), nullable=False)
    change_note = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    __table_args__ = (UniqueConstraint('document_id','revision',name='uq_document_revision'),)
