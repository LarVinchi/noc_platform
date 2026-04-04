from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Import our customer routes
from app.api.customers import router as customers_router

# CORRECTED IMPORTS BASED ON YOUR DIRECTORY STRUCTURE:
from app.core.db import get_db
from app.models.crm import Customer

app = FastAPI(
    title="NOC Platform API",
    description="Backend API for managing NOC operations, CRM, and Fiber tracking.",
    version="1.0.0"
)

# Set up CORS so your React frontend can talk to this API later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your frontend's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the routes
app.include_router(customers_router, prefix="/api/customers", tags=["Customers"])

@app.get("/")
def root():
    return {"message": "NOC Platform API is running!"}

# --- NEW TOPOLOGY ENDPOINT ---
@app.get("/api/topology/")
def get_network_topology(db: Session = Depends(get_db)):
    # 1. Fetch real customers from your PostgreSQL database
    customers = db.query(Customer).all()
    
    nodes = []
    edges = []
    
    # 2. Create the "Root" Core Network Nodes
    nodes.append({
        "id": "core-1", 
        "type": "core", 
        "position": {"x": 50, "y": 200}, # Left side
        "data": {"label": "DC-Main Router", "type": "CORE"}
    })
    
    nodes.append({
        "id": "cable-1", 
        "type": "splitter", 
        "position": {"x": 350, "y": 200}, # Middle
        "data": {"label": "48-Core Main Trunk", "type": "CABLE"}
    })
    
    edges.append({
        "id": "e-core-cable", 
        "source": "core-1", 
        "target": "cable-1", 
        "animated": True, 
        "style": {"stroke": "#06b6d4", "strokeWidth": 3}
    })

    # 3. Dynamically generate Nodes & Edges for every Customer in your DB!
    # We spread them out vertically on the right side of the screen
    start_y = 100
    for index, cust in enumerate(customers):
        cust_node_id = f"cust-{cust.customer_id}"
        
        # Add Customer Node
        nodes.append({
            "id": cust_node_id,
            "type": "customer",
            "position": {"x": 700, "y": start_y + (index * 150)}, # Right side, stacked vertically
            "data": {"label": cust.customer_name, "type": cust.customer_type}
        })
        
        # Add Edge connecting Trunk Cable to Customer
        edges.append({
            "id": f"e-cable-{cust_node_id}",
            "source": "cable-1",
            "target": cust_node_id,
            "animated": True,
            "style": {"stroke": "#84cc16", "strokeWidth": 3}
        })

    return {"nodes": nodes, "edges": edges}