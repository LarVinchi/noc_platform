import copy
import hashlib
import json
import zipfile
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.infrastructure import FiberRoute, FiberCable, NAP
from app.models.network_map import NetworkMapImport, MapRouteLink
from app.models.monitoring import SensorMapping
from app.services.kmz_parser import parse_kmz
from app.services.make_sample_kmz import build_kml
from app.services.impact import service_paths, impact_for_route

router = APIRouter(prefix="/topology", tags=["Geographic topology"])


@router.get("/maps/demo")
def demo():
    return parse_kmz(build_kml().encode(), "Lekki demo.kml")


@router.get("/maps")
def imports(db: Session = Depends(get_db)):
    return [{"import_id": str(row.import_id), "name": row.name, "filename": row.filename}
            for row in db.query(NetworkMapImport).order_by(NetworkMapImport.created_at.desc()).all()]


@router.post("/maps")
async def import_map(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not (file.filename or "").lower().endswith((".kmz", ".kml")):
        raise HTTPException(status_code=422, detail="Select a KMZ or KML file")
    raw = await file.read(25 * 1024 * 1024 + 1)
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Map upload limit is 25 MB")
    digest = hashlib.sha256(raw).hexdigest()
    existing = db.query(NetworkMapImport).filter_by(sha256=digest).first()
    if existing:
        return {"import_id": str(existing.import_id), "outcome": "existing"}
    try:
        geo = parse_kmz(raw, file.filename)
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        raise HTTPException(status_code=422, detail=str(error))
    row = NetworkMapImport(name=geo["name"], filename=file.filename, sha256=digest, geojson=geo)
    db.add(row)
    try:
        db.commit(); db.refresh(row)
    except IntegrityError:
        db.rollback()
        row = db.query(NetworkMapImport).filter_by(sha256=digest).one()
    return {"import_id": str(row.import_id), "outcome": "imported"}


@router.get("/maps/{import_id}")
def get_map(import_id: UUID, db: Session = Depends(get_db)):
    row = db.get(NetworkMapImport, import_id)
    if not row:
        raise HTTPException(status_code=404, detail="Map import not found")
    geo = copy.deepcopy(row.geojson)
    links = {link.feature_index: str(link.route_id) for link in db.query(MapRouteLink).filter_by(import_id=import_id).all()}
    for index, feature in enumerate(geo["features"]):
        feature["properties"].update(feature_index=index, inventory_route_id=links.get(index))
    return geo


class RouteLink(BaseModel):
    route_id: UUID
    feature_index: int = Field(ge=0)


@router.post("/maps/{import_id}/link")
def link_route(import_id: UUID, payload: RouteLink, db: Session = Depends(get_db)):
    row = db.query(NetworkMapImport).filter_by(import_id=import_id).with_for_update().first()
    route = db.query(FiberRoute).filter_by(route_id=payload.route_id).with_for_update().first()
    if not row or not route:
        raise HTTPException(status_code=404, detail="Map or inventory route not found")
    if payload.feature_index >= len(row.geojson["features"]):
        raise HTTPException(status_code=422, detail="Map feature does not exist")
    feature = row.geojson["features"][payload.feature_index]
    if feature["geometry"]["type"] != "LineString":
        raise HTTPException(status_code=422, detail="Link a route line to inventory")
    # Explicit operator mapping; never guess inventory identities from filenames.
    link = db.get(MapRouteLink, (import_id, payload.feature_index))
    if link and link.route_id != payload.route_id:
        raise HTTPException(status_code=409, detail="This feature already links to a different inventory route")
    if not link:
        if db.query(MapRouteLink).filter_by(route_id=payload.route_id).first():
            raise HTTPException(status_code=409, detail="This inventory route already has a mapped line. Reconcile its geometry before linking another line")
        db.add(MapRouteLink(import_id=import_id, feature_index=payload.feature_index, route_id=payload.route_id))
    route.geometry = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(feature["geometry"])), 4326)
    route.length_km = feature["properties"]["length_m"] / 1000
    db.commit()
    return {"route_id": str(route.route_id)}


@router.get("/impact/{route_id}")
def impact(route_id: UUID, db: Session = Depends(get_db)):
    if not db.get(FiberRoute, route_id):
        raise HTTPException(status_code=404, detail="Inventory route not found")
    return impact_for_route(db, route_id)


@router.get("/geography")
def geography(db: Session = Depends(get_db)):
    features, routes, anchors = [], [], {}
    alarms = {}
    cable_routes = {row.cable_id: str(row.route_id) for row in db.query(FiberCable).all()}
    for sensor in db.query(SensorMapping).filter(SensorMapping.last_state == 'down').all():
        route_key = str(sensor.route_id) if sensor.route_id else cable_routes.get(sensor.cable_id)
        if route_key:
            alarms.setdefault(route_key, []).append({"sensor_id": sensor.sensor_id,
                "observed_at": sensor.last_observed_at.isoformat(), "incident_id": str(sensor.incident_id) if sensor.incident_id else None})
    for row, raw in db.query(FiberRoute, func.ST_AsGeoJSON(FiberRoute.geometry)).all():
        routes.append({"route_id": str(row.route_id), "name": row.route_name, "status": row.status})
        if raw:
            geometry = json.loads(raw)
            anchors[str(row.route_id)] = geometry["coordinates"][-1]
            features.append({"type": "Feature", "geometry": geometry, "properties": {
                "name": row.route_name, "inventory_route_id": str(row.route_id), "kind": "route",
                "status": "planned" if row.status == "planned" else "unknown", "lifecycle": row.status,
                "monitoring_alarms": alarms.get(str(row.route_id), [])}})
    locations = {str(row.nap_id): json.loads(raw)["coordinates"] for row, raw in db.query(NAP, func.ST_AsGeoJSON(NAP.location)).all() if raw}
    for service in service_paths(db):
        path = service["paths"][0]
        location = locations.get(path.get("nap_id")) or anchors.get(path["route_id"])
        if location:
            features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": location},
                             "properties": {"name": service["customer"], "kind": "node", "node_type": "customer",
                                            "service_id": service["service_id"], "inventory_route_id": path["route_id"],
                                            "status": "unknown", "location_source": "Serving NAP" if path.get("nap_id") in locations else "Route endpoint anchor"}})
    return {"type": "FeatureCollection", "features": features, "routes": routes, "name": "Inventory & customer services"}


@router.get("/cable-impact/{cable_id}")
def cable_impact(cable_id: UUID, db: Session = Depends(get_db)):
    if not db.get(FiberCable, cable_id):
        raise HTTPException(status_code=404, detail="Cable not found")
    return impact_for_route(db, cable_id=cable_id)
