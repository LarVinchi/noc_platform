from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models.provisioning import ServiceCategory, WorkflowStage, ISPType

# --- NEW: Schema for Installation Metrics ---
class InstallMetricsResponse(BaseModel):
    id: int
    flexscan_result_dbm: Optional[float] = None
    checklist_completed: bool
    photo_nap_url: Optional[str] = None
    photo_routing_url: Optional[str] = None
    photo_rosette_url: Optional[str] = None
    photo_flexscan_url: Optional[str] = None
    acceptance_doc_url: Optional[str] = None

    class Config:
        from_attributes = True

class ServiceOrderCreate(BaseModel):
    # Data the manager fills out to create the order
    service_category: ServiceCategory = ServiceCategory.FTTH
    customer_name: str
    service_address: str
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    isp: ISPType
    bandwidth: str
    fn_number: Optional[str] = None

class ServiceOrderAllocate(BaseModel):
    nap_id: UUID
    drop_cable_id: UUID
    port_number: int

class ServiceOrderResponse(ServiceOrderCreate):
    # Data we send back to the frontend
    order_id: UUID
    service_order_number: Optional[str]
    service_id: Optional[str]
    status: WorkflowStage
    created_at: datetime
    
    # Allocation Fields
    nap_id: Optional[UUID] = None
    drop_cable_id: Optional[UUID] = None
    nap_port: Optional[int] = None
    
    # --- NEW: Added Metrics Field ---
    metrics: Optional[InstallMetricsResponse] = None
    
    class Config:
        from_attributes = True