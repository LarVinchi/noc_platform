from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime, timezone
from app.core.db import Base


class NetworkMapImport(Base):
    __tablename__ = "network_map_imports"
    import_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    sha256 = Column(String, nullable=False, unique=True)
    geojson = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class MapRouteLink(Base):
    __tablename__ = "map_route_links"
    import_id = Column(UUID(as_uuid=True), ForeignKey("network_map_imports.import_id", ondelete="CASCADE"), primary_key=True)
    feature_index = Column(Integer, primary_key=True)
    route_id = Column(UUID(as_uuid=True), ForeignKey("fiber_routes.route_id"), nullable=False)
