from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import our customer routes
from app.api.customers import router as customers_router

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