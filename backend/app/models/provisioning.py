from sqlalchemy import Column, String, Integer, DateTime, Enum, text, ForeignKey, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

# Ensure this matches your actual project's Base import path
from app.core.db import Base 

class ServiceCategory(str, enum.Enum):
    FTTH = "FTTH"
    DIA = "DIA"
    DARK_FIBER = "DARK_FIBER"
    LAYER_2 = "LAYER_2"

class WorkflowStage(str, enum.Enum):
    REQUESTED = "REQUESTED"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_ACCEPTANCE = "PENDING_ACCEPTANCE"
    MONITORED = "MONITORED"

class ISPType(str, enum.Enum):
    MTNN = "MTNN"
    METROREACH = "METROREACH"
    MANGONET = "MANGONET"

class ServiceOrder(Base):
    __tablename__ = "service_orders"

    # 1. Primary Identification
    order_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    service_category = Column(Enum(ServiceCategory), default=ServiceCategory.FTTH)
    isp = Column(Enum(ISPType), default=ISPType.METROREACH)
    status = Column(Enum(WorkflowStage), default=WorkflowStage.REQUESTED)
    
    # 2. Administrative Details
    customer_name = Column(String, index=True)
    service_address = Column(String)
    phone_number = Column(String, nullable=True)
    email = Column(String, nullable=True)
    bandwidth = Column(String)
    fn_number = Column(String, nullable=True)
    
    service_order_number = Column(String, unique=True, nullable=True) # e.g., SHANC01-00001
    service_id = Column(String, unique=True, nullable=True) # e.g., SHANC01-FTTH-50M-00001
    
    # 3. Infrastructure Routing
    coverage_zone_name = Column(String, nullable=True) # e.g., "Oniru Zone 9"
    pfp_id = Column(UUID(as_uuid=True), nullable=True)
    pfs_id = Column(UUID(as_uuid=True), nullable=True)
    pfs_split_level = Column(String, nullable=True) # e.g., "Splitter 4"
    pfs_port = Column(Integer, nullable=True)
    nap_id = Column(UUID(as_uuid=True), nullable=True)
    nap_port = Column(Integer, nullable=True)
    drop_cable_id = Column(UUID(as_uuid=True), nullable=True)
    
    # 4. Personnel & Dates
    drop_tech_name = Column(String, nullable=True)
    ont_tech_name = Column(String, nullable=True)
    planned_install_date = Column(DateTime, nullable=True)
    completion_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 5. Legacy/Inline Power Levels (Kept for your existing schemas)
    pfs_power_level = Column(String, nullable=True) # e.g., "-18.5dBm"
    nap_power_level = Column(String, nullable=True)
    rosette_power_level = Column(String, nullable=True)
    tester_type = Column(String, default="TS100-70 PON Tester")

    # Relationship to the new FTTH Document Metrics
    metrics = relationship("InstallMetrics", back_populates="service_order", uselist=False, cascade="all, delete-orphan")


class InstallMetrics(Base):
    __tablename__ = "install_metrics"

    id = Column(Integer, primary_key=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("service_orders.order_id", ondelete="CASCADE"))
    
    # FTTH Document Specific Fields
    flexscan_result_dbm = Column(Float, nullable=True)
    checklist_completed = Column(Boolean, default=False)
    
    # Photographic Evidence (URLs from S3 or local static directory)
    photo_nap_url = Column(String, nullable=True)
    photo_routing_url = Column(String, nullable=True)
    photo_rosette_url = Column(String, nullable=True)
    photo_flexscan_url = Column(String, nullable=True)
    
    # Auto-generated Document
    acceptance_doc_url = Column(String, nullable=True)

    service_order = relationship("ServiceOrder", back_populates="metrics")