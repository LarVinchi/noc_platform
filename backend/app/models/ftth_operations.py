from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.db import Base


class FtthStageEvent(Base):
    __tablename__ = 'ftth_stage_events'
    event_id = Column(UUID(as_uuid=True),primary_key=True)
    order_id = Column(UUID(as_uuid=True),ForeignKey('service_orders.order_id'),nullable=False,index=True)
    from_stage = Column(String(30))
    to_stage = Column(String(30),nullable=False)
    actor_id = Column(String(100),nullable=False)
    occurred_at = Column(DateTime(timezone=True),nullable=False)
    note = Column(Text,nullable=False)


class FtthIncidentLink(Base):
    __tablename__ = 'ftth_incident_links'
    link_id = Column(UUID(as_uuid=True),primary_key=True)
    order_id = Column(UUID(as_uuid=True),ForeignKey('service_orders.order_id'),nullable=False,index=True)
    incident_id = Column(UUID(as_uuid=True),ForeignKey('incidents.incident_id'),nullable=False,index=True)
    service_id = Column(UUID(as_uuid=True),ForeignKey('services.service_id'))
    kind = Column(String(30),nullable=False)
    request_key = Column(UUID(as_uuid=True),nullable=False)
    request_hash = Column(String(64),nullable=False)
    note = Column(Text,nullable=False)
    linked_by = Column(String(100),nullable=False)
    linked_at = Column(DateTime(timezone=True),nullable=False,server_default=text('now()'))
    __table_args__ = (UniqueConstraint('order_id','request_key',name='uq_ftth_request'),UniqueConstraint('order_id','incident_id','kind',name='uq_ftth_incident_link'))
