from sqlalchemy import Column,String,Text,DateTime,ForeignKey,UniqueConstraint,text
from sqlalchemy.dialects.postgresql import UUID,JSONB
from app.core.db import Base


class MailTriageItem(Base):
    __tablename__='mail_triage_items'
    item_id=Column(UUID(as_uuid=True),primary_key=True)
    owner_id=Column(String(100),nullable=False,index=True)
    request_key=Column(UUID(as_uuid=True),nullable=False)
    request_hash=Column(String(64),nullable=False)
    source=Column(String(30),nullable=False,default='manual_preview')
    subject=Column(String(250),nullable=False)
    sender=Column(String(320),nullable=False)
    received_at=Column(DateTime(timezone=True))
    entered_at=Column(DateTime(timezone=True),nullable=False,server_default=text('now()'))
    excerpt=Column(String(400),nullable=False)
    classification=Column(JSONB,nullable=False)
    state=Column(String(30),nullable=False,default='needs_review')
    incident_id=Column(UUID(as_uuid=True),ForeignKey('incidents.incident_id'))
    order_id=Column(UUID(as_uuid=True),ForeignKey('service_orders.order_id'))
    action_note=Column(Text)
    reviewed_by=Column(String(100))
    reviewed_at=Column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('owner_id','request_key',name='uq_mail_preview_request'),)
