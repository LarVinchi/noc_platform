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

@app.get("/api/topology/")
def get_network_topology(db: Session = Depends(get_db)):
    
    # Common styles for our edge labels to fit the dark theme
    label_style = {"fill": "#ffffff", "fontWeight": "bold", "fontSize": 12}
    label_bg_style = {"fill": "#1f2937", "stroke": "#374151", "strokeWidth": 1, "rx": 4, "ry": 4}

    nodes = [
        # Backbone Layer
        {"id": "route-n1", "type": "core", "position": {"x": 50, "y": 250}, "data": {"label": "North-Zone-Backbone", "type": "ROUTE"}},
        {"id": "cable-n1", "type": "cable", "position": {"x": 350, "y": 250}, "data": {"label": "CABLE-N1 (48-Core)", "type": "CABLE"}},
        
        # FTTH ODN Tree
        {"id": "pfs-1", "type": "splitter", "position": {"x": 650, "y": 100}, "data": {"label": "PFS-YABA-01", "type": "PFS"}},
        {"id": "pfp-1", "type": "splitter", "position": {"x": 950, "y": 100}, "data": {"label": "PFP-YABA-MAIN", "type": "PFP"}},
        {"id": "nap-1", "type": "splitter", "position": {"x": 1250, "y": 100}, "data": {"label": "NAP-YABA-001 (8 Ports)", "type": "NAP"}},
        
        # Customers
        {"id": "cust-glotech", "type": "customer", "position": {"x": 1600, "y": 100}, "data": {"label": "Glo-Tech Hub", "type": "FTTH"}},
        {"id": "cust-cupcake", "type": "customer", "position": {"x": 700, "y": 250}, "data": {"label": "Cupcake", "type": "DIA"}},
        {"id": "cust-swiftnet", "type": "customer", "position": {"x": 700, "y": 400}, "data": {"label": "SwiftNet Solutions", "type": "DARKFIBER"}},
    ]
    
    edges = [
        # Backbone routing
        {"id": "e-rt-cb", "source": "route-n1", "target": "cable-n1", "animated": True, "style": {"stroke": "#06b6d4"}},
        
        # FTTH Path (Core 1)
        {
            "id": "e-cb-pfs", "source": "cable-n1", "target": "pfs-1", "animated": True, 
            "style": {"stroke": "#a855f7"}, 
            "label": "Core 1", "labelStyle": label_style, "labelBgStyle": label_bg_style
        },
        {"id": "e-pfs-pfp", "source": "pfs-1", "target": "pfp-1", "animated": True, "style": {"stroke": "#a855f7"}},
        {"id": "e-pfp-nap", "source": "pfp-1", "target": "nap-1", "animated": True, "style": {"stroke": "#a855f7"}},
        
        # --- THE FIX: Displaying the NAP Port + Drop Cable ---
        {
            "id": "e-nap-glo", "source": "nap-1", "target": "cust-glotech", "animated": True, 
            "style": {"stroke": "#a855f7"}, 
            "label": "Port 1 (DROP-GT-001)", "labelStyle": label_style, "labelBgStyle": label_bg_style
        },
        
        # Direct DIA / Dark Fiber Paths (Cores 6 & 9)
        {
            "id": "e-cb-cup", "source": "cable-n1", "target": "cust-cupcake", "animated": True, 
            "style": {"stroke": "#f97316"}, 
            "label": "Core 6 (DIA)", "labelStyle": label_style, "labelBgStyle": label_bg_style
        },
        {
            "id": "e-cb-swift", "source": "cable-n1", "target": "cust-swiftnet", "animated": False, 
            "style": {"stroke": "#57534e", "strokeWidth": 4}, 
            "label": "Core 9 (Dark Fiber)", "labelStyle": label_style, "labelBgStyle": label_bg_style
        },
    ]

    return {"nodes": nodes, "edges": edges}