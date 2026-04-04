from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime

# Import the Base class we created in db.py
from app.core.db import Base

class Customer(Base):
    __tablename__ = "customers"

    # Columns
    customer_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    customer_type = Column(String, nullable=False) # 'METROREACH' or 'ISP'
    customer_name = Column(String, nullable=False)
    service_id_code = Column(String, unique=True, nullable=False)
    email = Column(String)
    phone = Column(String)
    address = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships (Allows us to easily fetch all services for a customer)
    services = relationship("Service", back_populates="customer", cascade="all, delete")

class Service(Base):
    __tablename__ = "services"

    # Columns
    service_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False)
    service_type = Column(String, nullable=False) # 'DIA', 'DARKFIBER', 'FTTH', 'ISP_FTTH', 'LAYER2'
    bandwidth_mbps = Column(Integer, nullable=True)
    status = Column(String, default="active", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    customer = relationship("Customer", back_populates="services")
    logical_config = relationship("LogicalConfiguration", back_populates="service", uselist=False, cascade="all, delete")

class LogicalConfiguration(Base):
    __tablename__ = "logical_configurations"

    # Columns
    config_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.service_id", ondelete="CASCADE"), nullable=False)
    vlan_id = Column(Integer)
    wan_ip_block = Column(String)
    lan_ip_block = Column(String)
    mac_address = Column(String)
    routing_protocol = Column(String, default="NONE")
    bgp_asn = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    service = relationship("Service", back_populates="logical_config")