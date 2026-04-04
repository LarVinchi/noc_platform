from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, text, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from datetime import datetime

from app.core.db import Base

class FiberRoute(Base):
    __tablename__ = "fiber_routes"

    route_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    route_name = Column(String, nullable=False)
    service_area = Column(String, nullable=False)
    # The magical PostGIS spatial column!
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
    pfs_nodes = relationship("PFS", back_populates="core")

# --- ODN TREE NODES ---

class PFS(Base):
    __tablename__ = "pfs"
    pfs_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    core_id = Column(UUID(as_uuid=True), ForeignKey("fiber_cores.core_id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    location = Column(Geometry(geometry_type='POINT', srid=4326))
    created_at = Column(DateTime, default=datetime.utcnow)

    core = relationship("FiberCore", back_populates="pfs_nodes")
    pfps = relationship("PFP", back_populates="pfs", cascade="all, delete")

class PFP(Base):
    __tablename__ = "pfp"
    pfp_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    pfs_id = Column(UUID(as_uuid=True), ForeignKey("pfs.pfs_id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    location = Column(Geometry(geometry_type='POINT', srid=4326))
    created_at = Column(DateTime, default=datetime.utcnow)

    pfs = relationship("PFS", back_populates="pfps")
    naps = relationship("NAP", back_populates="pfp", cascade="all, delete")

class NAP(Base):
    __tablename__ = "nap"
    nap_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    pfp_id = Column(UUID(as_uuid=True), ForeignKey("pfp.pfp_id", ondelete="CASCADE"), nullable=False)
    nap_code = Column(String, unique=True, nullable=False)
    total_ports = Column(Integer, nullable=False)
    location = Column(Geometry(geometry_type='POINT', srid=4326))
    created_at = Column(DateTime, default=datetime.utcnow)

    pfp = relationship("PFP", back_populates="naps")
    drop_cables = relationship("DropCable", back_populates="nap", cascade="all, delete")

class DropCable(Base):
    __tablename__ = "drop_cables"
    drop_cable_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    nap_id = Column(UUID(as_uuid=True), ForeignKey("nap.nap_id", ondelete="CASCADE"), nullable=False)
    drop_cable_code = Column(String, unique=True, nullable=False)
    length_m = Column(Numeric(10, 2))
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    nap = relationship("NAP", back_populates="drop_cables")