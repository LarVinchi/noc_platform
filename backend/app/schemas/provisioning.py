from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models.provisioning import ServiceCategory, WorkflowStage, ISPType

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

class ServiceOrderResponse(ServiceOrderCreate):
    # Data we send back to the frontend
    order_id: UUID
    service_order_number: Optional[str]
    service_id: Optional[str]
    status: WorkflowStage
    created_at: datetime
    
    # --- NEW: Added Allocation Fields so the frontend can see them ---
    nap_id: Optional[UUID] = None
    drop_cable_id: Optional[UUID] = None
    nap_port: Optional[int] = None
    
    class Config:
        from_attributes = True

class ServiceOrderAllocate(BaseModel):
    nap_id: UUID
    drop_cable_id: UUID
    port_number: int