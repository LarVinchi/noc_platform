from sqlalchemy import Column, String, Integer, DateTime, Enum, text
from sqlalchemy.dialects.postgresql import UUID
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
    DESIGNED = "DESIGNED"
    PFS_TESTING = "PFS_TESTING"
    NAP_TESTING = "NAP_TESTING"
    ROSETTE_TESTING = "ROSETTE_TESTING"
    DROP_INSTALLATION = "DROP_INSTALLATION"
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"

class ISPType(str, enum.Enum):
    MTNN = "MTNN"
    METROREACH = "METROREACH"
    MANGONET = "MANGONET"

class ServiceOrder(Base):
    __tablename__ = "service_orders"

    order_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    
    # --- NEW: Categorizes the service type (FTTH, DIA, etc.) ---
    service_category = Column(Enum(ServiceCategory), nullable=False, default=ServiceCategory.FTTH)
    
    # 1. Customer & ISP Details
    customer_name = Column(String, nullable=False)
    service_address = Column(String, nullable=False)
    phone_number = Column(String)
    email = Column(String)
    isp = Column(Enum(ISPType), nullable=False)
    bandwidth = Column(String, nullable=False) # e.g., "50M"
    fn_number = Column(String, nullable=True)  # Required only for MTNN
    
    # 2. Automated IDs
    service_order_number = Column(String, unique=True, nullable=True) # e.g., SHANC01-00001
    service_id = Column(String, unique=True, nullable=True) # e.g., SHANC01-FTTH-50M-00001
    
    # 3. Infrastructure Routing (Foreign Keys temporarily removed)
    pfp_id = Column(UUID(as_uuid=True), nullable=True)
    pfs_id = Column(UUID(as_uuid=True), nullable=True)
    pfs_port = Column(Integer, nullable=True)
    nap_id = Column(UUID(as_uuid=True), nullable=True)
    nap_port = Column(Integer, nullable=True)
    drop_cable_id = Column(UUID(as_uuid=True), nullable=True) # <-- ADDED THIS FOR ALLOCATION
    
    # 4. Workflow & Testing (Populated during install)
    status = Column(Enum(WorkflowStage), default=WorkflowStage.REQUESTED)
    pfs_power_level = Column(String, nullable=True) # e.g., "-18.5dBm"
    nap_power_level = Column(String, nullable=True)
    rosette_power_level = Column(String, nullable=True) # e.g., "-24.2dBm"
    tester_type = Column(String, default="TS100-70 PON Tester")
    
    # 5. Personnel & Documents (Foreign Keys temporarily removed)
    drop_tech_name = Column(String, nullable=True)
    cpe_tech_name = Column(String, nullable=True)
    noc_personnel_id = Column(UUID(as_uuid=True), nullable=True) 
    requested_by_id = Column(UUID(as_uuid=True), nullable=True) 
    approved_by_id = Column(UUID(as_uuid=True), nullable=True) 
    
    planned_install_date = Column(DateTime, nullable=True)
    completion_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)