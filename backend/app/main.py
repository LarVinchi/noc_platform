import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, selectinload
from uuid import UUID
from app.services.topology import build_cable_topology
from app.api.routers import provisioning, incidents

# Import our custom routes
from app.api.customers import router as customers_router
from app.core.db import get_db
from sqlalchemy import text

# CRM & Allocation Models
from app.models.crm import Customer, Service
from app.models.allocations import CoreAllocation, DropAllocation

# Infrastructure Models
from app.models.infrastructure import (
    FiberRoute, FiberCable, FiberCore, 
    PFP, PFS, NAP, DropCable, DistributionFiber
)

app = FastAPI(
    title="NOC Platform API",
    description="Backend API for managing NOC operations, CRM, and Fiber tracking.",
    version="1.0.0"
)

# Ensure the static directories exist so FastAPI doesn't crash on startup
os.makedirs("static/documents/acceptances", exist_ok=True)
os.makedirs("static/uploads/installations", exist_ok=True)
# Mount the static directory so the frontend can download the PDFs and view images
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# REGISTER ROUTERS
# ==========================================
app.include_router(customers_router, prefix="/api/customers", tags=["Customers"])
app.include_router(provisioning.router, prefix="/api") # <-- Your new Provisioning Router!
app.include_router(incidents.router, prefix="/api")

@app.get("/")
def root():
    return {"message": "NOC Platform API is running!"}


@app.get("/health/ready")
def readiness(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ready"}

# ==========================================
# 1. BASE TOPOLOGY ENDPOINT (Backbone)
# ==========================================
@app.get("/api/topology/")
def get_network_topology(db: Session = Depends(get_db)):
    routes = db.query(FiberRoute).filter(FiberRoute.status == 'active').all()
    cables = db.query(FiberCable).filter(FiberCable.status == 'active').all()

    nodes = []
    edges = []

    for route in routes:
        nodes.append({
            "id": str(route.route_id),
            "type": "core",
            "position": {"x": 0, "y": 0}, # Dagre handles layout on frontend!
            "data": {
                "label": route.route_name,
                "type": "ROUTE",
                "badge": route.service_area
            }
        })

    for cable in cables:
        cable_node_id = str(cable.cable_id)
        route_id_str = str(cable.route_id)
        
        nodes.append({
            "id": cable_node_id,
            "type": "cable",
            "position": {"x": 0, "y": 0}, 
            "data": {
                "label": cable.cable_name,
                "type": "CABLE",
                "badge": f"{cable.total_cores}-Core"
            }
        })

        edges.append({
            "id": f"e-rt-{cable_node_id}",
            "source": route_id_str,
            "target": cable_node_id,
            "animated": True,
            "style": {"stroke": "#06b6d4", "strokeWidth": 2}
        })

    return {"nodes": nodes, "edges": edges}


# ==========================================
# 2. DRILL-DOWN EXPAND ENDPOINT (ODN & CRM)
# ==========================================
@app.get("/api/topology/expand/{cable_id}")
def expand_cable_topology(cable_id: UUID, db: Session = Depends(get_db)):
    # Eager-load actual descendants; avoid global ODN queries and per-node queries.
    cable = db.query(FiberCable).options(
        selectinload(FiberCable.cores).selectinload(FiberCore.allocations)
            .selectinload(CoreAllocation.service).selectinload(Service.customer),
        selectinload(FiberCable.cores).selectinload(FiberCore.pfps)
            .selectinload(PFP.pfss).selectinload(PFS.naps)
            .selectinload(NAP.drop_cables).selectinload(DropCable.allocations)
            .selectinload(DropAllocation.service).selectinload(Service.customer),
    ).filter(FiberCable.cable_id == cable_id).first()
    if cable is None:
        raise HTTPException(status_code=404, detail="Cable not found")
    return build_cable_topology(cable)
