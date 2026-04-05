from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.db import Base

class WorkflowStage(str, enum.Enum):
    REQUESTED = "REQUESTED"
    PFS_TESTING = "PFS_TESTING"
    NAP_TESTING = "NAP_TESTING"
    ROSETTE_TESTING = "ROSETTE_TESTING"
    DROP_INSTALLATION = "DROP_INSTALLATION"
    ACTIVE = "ACTIVE"

class ISPType(str, enum.Enum):
    MTNN = "MTNN"
    METROREACH = "METROREACH"
    MANGONET = "MANGONET"

class FTTHServiceOrder(Base):
    __tablename__ = "ftth_service_orders"

    order_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    
    # 1. Customer & ISP Details
    customer_name = Column(String, nullable=False)
    service_address = Column(String, nullable=False)
    phone_number = Column(String)
    email = Column(String)
    isp = Column(Enum(ISPType), nullable=False)
    bandwidth = Column(String, nullable=False) # e.g., "50M"
    fn_number = Column(String, nullable=True) # Required only for MTNN
    
    # 2. Automated IDs
    service_order_number = Column(String, unique=True, nullable=True) # e.g., SHANC01-00001
    service_id = Column(String, unique=True, nullable=True) # e.g., SHANC01-FTTH-50M-00001
    
    # 3. Infrastructure Routing (Foreign Keys to your infra tables)
    pfp_id = Column(UUID(as_uuid=True), ForeignKey("pfp.pfp_id"), nullable=True)
    pfs_id = Column(UUID(as_uuid=True), ForeignKey("pfs.pfs_id"), nullable=True)
    pfs_port = Column(Integer, nullable=True)
    nap_id = Column(UUID(as_uuid=True), ForeignKey("nap.nap_id"), nullable=True)
    nap_port = Column(Integer, nullable=True)

    # 4. Workflow & Testing (Populated during install)
    status = Column(Enum(WorkflowStage), default=WorkflowStage.REQUESTED)
    pfs_power_level = Column(String, nullable=True) # e.g., "-18.5dBm"
    nap_power_level = Column(String, nullable=True)
    rosette_power_level = Column(String, nullable=True) # e.g., "-24.2dBm"
    tester_type = Column(String, default="TS100-70 PON Tester")
    
    # 5. Personnel & Documents
    drop_tech_name = Column(String, nullable=True)
    cpe_tech_name = Column(String, nullable=True)
    noc_personnel_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True) # Tracks who signed it off
    
    planned_install_date = Column(DateTime, nullable=True)
    completion_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)