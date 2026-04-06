from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.api.routers import provisioning

# Import our custom routes
from app.api.customers import router as customers_router
from app.core.db import get_db

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

@app.get("/")
def root():
    return {"message": "NOC Platform API is running!"}

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
def expand_cable_topology(cable_id: str, db: Session = Depends(get_db)):
    nodes = []
    edges = []

    # --- STEP A: Fetch Core Allocations (Enterprise / Direct Services) ---
    cores = db.query(FiberCore).filter(FiberCore.cable_id == cable_id).all()
    core_ids = [core.core_id for core in cores]
    
    allocations = db.query(CoreAllocation).filter(
        CoreAllocation.core_id.in_(core_ids), 
        CoreAllocation.end_date == None
    ).all()

    for alloc in allocations:
        service = alloc.service
        if not service: continue
        customer = service.customer

        node_type = "dia_endpoint"
        display_type = "DIA Demarcation (Enterprise)"
        badge_text = f"Core {alloc.core.core_number} | {service.bandwidth_mbps or 'N/A'} Mbps"
        
        if service.service_type == "DARKFIBER":
            node_type = "dark_fiber_endpoint"
            display_type = "Dark Fiber Patch Panel"
            badge_text = f"Core {alloc.core.core_number}" # FIXED: Removed Mbps
        elif service.service_type == "LAYER2":
            node_type = "layer2_endpoint"
            display_type = "Layer 2 UNI (Network Interface)"

        node_id = f"srv-{service.service_id}"
        nodes.append({
            "id": node_id,
            "type": node_type,
            "position": {"x": 0, "y": 0}, # Handled by Dagre
            "data": {
                "label": customer.customer_name if customer else "Unknown",
                "type": display_type,
                "badge": badge_text 
            }
        })
        edges.append({
            "id": f"e-cbl-{cable_id}-{node_id}",
            "source": cable_id,
            "target": node_id,
            "animated": True,
            "style": {"stroke": "#f97316"} 
        })

    # --- STEP B: Fetch ODN Hierarchy (FTTH) ---
    pfps = db.query(PFP).all() 
    for pfp in pfps:
        pfp_id_str = str(pfp.pfp_id)
        nodes.append({
            "id": pfp_id_str,
            "type": "primary_splitter",
            "position": {"x": 0, "y": 0},
            "data": {
                "label": pfp.name,
                "type": "Primary Splitter Cabinet",
                "badge": f"{pfp.split_ratio} Split" # FIXED: Replaced 'Primary ODN'
            }
        })
        edges.append({
            "id": f"e-cbl-{pfp_id_str}",
            "source": cable_id,
            "target": pfp_id_str,
            "animated": True,
            "style": {"stroke": "#a855f7"} 
        })

        pfss = db.query(PFS).all() 
        for pfs in pfss:
            pfs_id_str = str(pfs.pfs_id)
            nodes.append({
                "id": pfs_id_str,
                "type": "secondary_splitter",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": pfs.name if hasattr(pfs, 'name') else "PFS Enclosure",
                    "type": "Secondary Splitter Enclosure",
                    "badge": f"{pfs.split_ratio} Split" if hasattr(pfs, 'split_ratio') else "1:8 Split"
                }
            })
            edges.append({
                "id": f"e-pfp-{pfs_id_str}",
                "source": pfp_id_str,
                "target": pfs_id_str,
                "animated": True,
                "style": {"stroke": "#a855f7"}
            })

            naps = db.query(NAP).all() 
            for nap in naps:
                nap_id_str = str(nap.nap_id)
                nodes.append({
                    "id": nap_id_str,
                    "type": "access_point",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "label": nap.nap_code,
                        "type": "Service Access Terminal",
                        "badge": f"{nap.total_ports} Ports"
                    }
                })
                edges.append({
                    "id": f"e-pfs-{nap_id_str}",
                    "source": pfs_id_str,
                    "target": nap_id_str,
                    "animated": True,
                    "style": {"stroke": "#a855f7"}
                })

                # --- STEP C: Fetch FTTH Customers ---
                drop_allocs = db.query(DropAllocation).join(DropCable).filter(DropCable.nap_id == nap.nap_id).all()
                for da in drop_allocs:
                    srv = da.service
                    cust = srv.customer if srv else None
                    cpe_id = f"cpe-{da.allocation_id}"
                    
                    nodes.append({
                        "id": cpe_id,
                        "type": "cpe_outlet",
                        "position": {"x": 0, "y": 0},
                        "data": {
                            "label": cust.customer_name if cust else "FTTH Sub",
                            "type": "Customer Premise (ONT/Router)",
                            "badge": f"Port {da.nap_port_number}"
                        }
                    })
                    edges.append({
                        "id": f"e-nap-{cpe_id}",
                        "source": nap_id_str,
                        "target": cpe_id,
                        "animated": True,
                        "style": {"stroke": "#f97316"}
                    })

    return {"nodes": nodes, "edges": edges}