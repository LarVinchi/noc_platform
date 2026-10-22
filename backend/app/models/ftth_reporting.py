"""Reconciled cumulative snapshots, separate from installation-day activity."""
from sqlalchemy import Column, String, Date, DateTime, Integer, text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.db import Base


class FtthNetworkSnapshot(Base):
    __tablename__='ftth_network_snapshots'
    snapshot_id=Column(UUID(as_uuid=True),primary_key=True)
    report_date=Column(Date,nullable=False,index=True)
    source_note=Column(String(2000),nullable=False)
    payload=Column(JSONB,nullable=False)
    sha256=Column(String(64),nullable=False,unique=True)
    created_by=Column(String(100),nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,server_default=text('now()'))


class FtthDailyPlan(Base):
    __tablename__ = 'ftth_daily_plans'
    plan_id = Column(UUID(as_uuid=True), primary_key=True)
    report_date = Column(Date, nullable=False, unique=True)
    revision = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default='planning')
    payload = Column(JSONB, nullable=False)
    created_by = Column(String(100), nullable=False)
    updated_by = Column(String(100), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class FtthPlanEvent(Base):
    __tablename__ = 'ftth_plan_events'
    __table_args__ = (UniqueConstraint('plan_id', 'revision'),)
    event_id = Column(UUID(as_uuid=True), primary_key=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey('ftth_daily_plans.plan_id'), nullable=False)
    revision = Column(Integer, nullable=False)
    action = Column(String(20), nullable=False)
    actor_id = Column(String(100), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    payload = Column(JSONB, nullable=False)


class FtthReportDelivery(Base):
    __tablename__ = 'ftth_report_deliveries'
    delivery_id = Column(UUID(as_uuid=True), primary_key=True)
    # One immutable weekly snapshot per recipient; prevents timer retries from duplicating mail.
    delivery_key = Column(String(64), nullable=False, unique=True)
    recipient = Column(String(254), nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(String(20), nullable=False, default='queued')
    attempts = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    error_type = Column(String(100), nullable=True)
