from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, text, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from datetime import datetime

from app.core.db import Base

# ---------------------------------------------------------
# 1. Physical Routes & Backbone
# ---------------------------------------------------------
class FiberRoute(Base):
    __tablename__ = "fiber_routes"

    route_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    route_name = Column(String, nullable=False)
    service_area = Column(String, nullable=False)
    geometry = Column(Geometry(geometry_type='LINESTRING', srid=4326))
    length_km = Column(Numeric(10, 2))
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    cables = relationship("FiberCable", back_populates="route", cascade="all, delete")

class FiberCable(Base):
    __tablename__ = "fiber_cables"

    cable_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    route_id = Column(UUID(as_uuid=True), ForeignKey("fiber_routes.route_id", ondelete="CASCADE"), nullable=False)
    cable_name = Column(String, nullable=False)
    total_cores = Column(Integer, nullable=False)
    cable_type = Column(String, nullable=False)
    install_date = Column(Date)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    route = relationship("FiberRoute", back_populates="cables")
    cores = relationship("FiberCore", back_populates="cable", cascade="all, delete")

class FiberCore(Base):
    __tablename__ = "fiber_cores"

    core_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    cable_id = Column(UUID(as_uuid=True), ForeignKey("fiber_cables.cable_id", ondelete="CASCADE"), nullable=False)
    core_number = Column(Integer, nullable=False)
    usage_type = Column(String, nullable=False)
    allocation_status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    cable = relationship("FiberCable", back_populates="cores")
    # PFP connects directly to the FiberCore
    pfps = relationship("PFP", back_populates="core", cascade="all, delete")


# ---------------------------------------------------------
# 2. ODN Hardware Nodes (3-Stage Cascaded Split)
# ---------------------------------------------------------
class PFP(Base):
    """Stage 1: Primary Flexibility Point (Cabinet)"""
    __tablename__ = "pfp"
    
    pfp_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    
    # FIXED: PFP connects to the main backbone Core
    core_id = Column(UUID(as_uuid=True), ForeignKey("fiber_cores.core_id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String, nullable=False)
    split_ratio = Column(String, nullable=False, default='1:4')
    location = Column(Geometry(geometry_type='POINT', srid=4326))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    core = relationship("FiberCore", back_populates="pfps")
    pfss = relationship("PFS", back_populates="pfp", cascade="all, delete")
    dist_fibers_out = relationship("DistributionFiber", foreign_keys="[DistributionFiber.source_pfp_id]", back_populates="source_pfp")

class PFS(Base):
    """Stage 2: Primary Fiber Splitter"""
    __tablename__ = "pfs"
    
    pfs_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    
    # FIXED: PFS connects upstream to the PFP
    pfp_id = Column(UUID(as_uuid=True), ForeignKey("pfp.pfp_id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String, nullable=False)
    split_ratio = Column(String, nullable=False, default='1:8')
    location = Column(Geometry(geometry_type='POINT', srid=4326))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    pfp = relationship("PFP", back_populates="pfss")
    naps = relationship("NAP", back_populates="pfs", cascade="all, delete")
    dist_fibers_in = relationship("DistributionFiber", foreign_keys="[DistributionFiber.dest_pfs_id]", back_populates="dest_pfs")
    dist_fibers_out = relationship("DistributionFiber", foreign_keys="[DistributionFiber.source_pfs_id]", back_populates="source_pfs")

class NAP(Base):
    """Stage 3: Network Access Point (Terminal)"""
    __tablename__ = "nap"
    
    nap_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    
    # FIXED: NAP connects upstream to the PFS
    pfs_id = Column(UUID(as_uuid=True), ForeignKey("pfs.pfs_id", ondelete="CASCADE"), nullable=False)
    
    nap_code = Column(String, unique=True, nullable=False)
    total_ports = Column(Integer, nullable=False)
    location = Column(Geometry(geometry_type='POINT', srid=4326))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    pfs = relationship("PFS", back_populates="naps")
    drop_cables = relationship("DropCable", back_populates="nap", cascade="all, delete")
    dist_fibers_in = relationship("DistributionFiber", foreign_keys="[DistributionFiber.dest_nap_id]", back_populates="dest_nap")


# ---------------------------------------------------------
# 3. Connective Cables (Distribution & Drop)
# ---------------------------------------------------------
class DistributionFiber(Base):
    """The physical uplink cables mapping specific splitter legs to the next node"""
    __tablename__ = "distribution_fibers"
    
    dist_fiber_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    cable_name = Column(String, nullable=False)
    
    # Optional Foreign Keys based on which level of the tree it connects
    source_pfp_id = Column(UUID(as_uuid=True), ForeignKey("pfp.pfp_id"))
    dest_pfs_id = Column(UUID(as_uuid=True), ForeignKey("pfs.pfs_id"))
    source_pfs_id = Column(UUID(as_uuid=True), ForeignKey("pfs.pfs_id"))
    dest_nap_id = Column(UUID(as_uuid=True), ForeignKey("nap.nap_id"))
    
    source_port = Column(Integer, nullable=False) # Which splitter leg is feeding this?
    fiber_number = Column(Integer, nullable=False)
    status = Column(String, default="free")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    source_pfp = relationship("PFP", foreign_keys=[source_pfp_id], back_populates="dist_fibers_out")
    dest_pfs = relationship("PFS", foreign_keys=[dest_pfs_id], back_populates="dist_fibers_in")
    source_pfs = relationship("PFS", foreign_keys=[source_pfs_id], back_populates="dist_fibers_out")
    dest_nap = relationship("NAP", foreign_keys=[dest_nap_id], back_populates="dist_fibers_in")

class DropCable(Base):
    """The final cable terminating at the customer premise"""
    __tablename__ = "drop_cables"
    
    drop_cable_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    nap_id = Column(UUID(as_uuid=True), ForeignKey("nap.nap_id", ondelete="CASCADE"), nullable=False)
    drop_cable_code = Column(String, unique=True, nullable=False)
    length_m = Column(Numeric(10,2))
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    nap = relationship("NAP", back_populates="drop_cables")