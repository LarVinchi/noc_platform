from sqlalchemy import Column,String,Boolean,DateTime,ForeignKey,text
from sqlalchemy.dialects.postgresql import UUID,JSONB
from app.core.db import Base


class RecordCorrection(Base):
    __tablename__='record_corrections'
    correction_id=Column(UUID(as_uuid=True),primary_key=True,server_default=text('gen_random_uuid()'))
    entity_type=Column(String(20),nullable=False)
    entity_id=Column(UUID(as_uuid=True),nullable=False)
    reason=Column(String(1000),nullable=False)
    changed_fields=Column(JSONB,nullable=False)
    actor_id=Column(String(100),nullable=False)
    actor_verified=Column(Boolean,nullable=False)
    request_id=Column(String(100),nullable=False)
    previous_ticket_id=Column(String(100),nullable=True)
    current_ticket_id=Column(String(100),nullable=True)
    created_at=Column(DateTime(timezone=True),nullable=False,server_default=text('now()'))


class IncidentTicketIdentifier(Base):
    __tablename__='incident_ticket_identifiers'
    ticket_id=Column(String(100),primary_key=True)
    incident_id=Column(UUID(as_uuid=True),ForeignKey('incidents.incident_id'),nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,server_default=text('now()'))
