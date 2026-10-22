"""Derived evidence and origin metadata only; no OneDrive original-file blobs."""
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.db import Base


class LinkedCollection(Base):
    __tablename__='linked_collections'
    collection_id=Column(UUID(as_uuid=True),primary_key=True)
    title=Column(String(200),nullable=False)
    owner_id=Column(String(100),nullable=False)
    enabled=Column(Boolean,nullable=False,default=True)
    freshness_seconds=Column(Integer,nullable=False,default=86400)
    derived_limit_bytes=Column(Integer,nullable=False,default=25000000)
    last_observed_at=Column(DateTime(timezone=True))


class LinkedRevision(Base):
    __tablename__='linked_revisions'
    version_id=Column(UUID(as_uuid=True),ForeignKey('document_versions.version_id'),primary_key=True)
    collection_id=Column(UUID(as_uuid=True),ForeignKey('linked_collections.collection_id'),nullable=False,index=True)
    source_path=Column(String(1000),nullable=False)
    original_url=Column(String(2000))
    extraction_sha256=Column(String(64),nullable=False)
    chunks=Column(JSONB,nullable=False)
    derived_bytes=Column(Integer,nullable=False)
    observed_at=Column(DateTime(timezone=True),nullable=False)
    available=Column(Boolean,nullable=False)


class LinkedScan(Base):
    __tablename__='linked_scans'
    run_id=Column(UUID(as_uuid=True),primary_key=True)
    collection_id=Column(UUID(as_uuid=True),ForeignKey('linked_collections.collection_id'),nullable=False)
    payload_sha256=Column(String(64),nullable=False)
    observed_at=Column(DateTime(timezone=True),nullable=False)
    summary=Column(JSONB,nullable=False)
