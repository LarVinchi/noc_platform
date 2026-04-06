import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID 

from app.core.db import get_db
from app.models.provisioning import ServiceOrder, WorkflowStage, InstallMetrics
from app.schemas.provisioning import ServiceOrderCreate, ServiceOrderResponse, ServiceOrderAllocate

# Import infrastructure to validate allocations
from app.models.infrastructure import NAP, DropCable
from app.models.allocations import DropAllocation

router = APIRouter(prefix="/provisioning", tags=["Provisioning Workflow"])

# --- Helper logic to save uploaded images ---
UPLOAD_DIR = "static/uploads/installations"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def save_upload_file(upload_file: UploadFile, order_id: UUID, prefix: str) -> Optional[str]:
    if not upload_file:
        return None
    # e.g., static/uploads/installations/123e4567-e89b-12d3-a456-426614174000_nap_photo.jpg
    file_path = f"{UPLOAD_DIR}/{order_id}_{prefix}_{upload_file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return f"/{file_path}"


def generate_ids(customer_name: str, bandwidth: str, db: Session) -> tuple:
    """Auto-generates Service ID based on your NOC's naming convention"""
    names = customer_name.strip().split()
    first_name = names[0][:4].upper()
    prefix = f"{first_name}C01"
    
    count = db.query(ServiceOrder).filter(
        ServiceOrder.service_order_number.like(f"{prefix}-%")
    ).count() + 1
    
    seq_str = f"{count:05d}"
    so_number = f"{prefix}-{seq_str}"
    clean_bandwidth = bandwidth if bandwidth and bandwidth != "string" else "UNKNOWN"
    service_id = f"{prefix}-FTTH-{clean_bandwidth}-{seq_str}"
    
    return so_number, service_id

@router.post("/", response_model=ServiceOrderResponse)
def create_service_order(order_in: ServiceOrderCreate, db: Session = Depends(get_db)):
    so_number, service_id = generate_ids(order_in.customer_name, order_in.bandwidth, db)
    
    new_order = ServiceOrder(
        **order_in.model_dump(),
        service_order_number=so_number,
        service_id=service_id,
        status=WorkflowStage.REQUESTED
    )
    
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return new_order

@router.patch("/{order_id}/allocate", response_model=ServiceOrderResponse)
def allocate_service_order(
    order_id: UUID, 
    alloc_in: ServiceOrderAllocate, 
    db: Session = Depends(get_db)
):
    order = db.query(ServiceOrder).filter(ServiceOrder.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Service Order not found")
        
    if order.status != WorkflowStage.REQUESTED:
        raise HTTPException(status_code=400, detail=f"Cannot allocate order. Current status is {order.status}")

    nap = db.query(NAP).filter(NAP.nap_id == alloc_in.nap_id).first()
    if not nap:
        raise HTTPException(status_code=404, detail="NAP not found")
        
    if alloc_in.port_number > nap.total_ports:
        raise HTTPException(status_code=400, detail=f"Port {alloc_in.port_number} exceeds NAP capacity of {nap.total_ports}.")

    existing_alloc = db.query(DropAllocation).join(DropCable).filter(
        DropCable.nap_id == alloc_in.nap_id,
        DropAllocation.nap_port_number == alloc_in.port_number
    ).first()
    
    if existing_alloc:
        raise HTTPException(status_code=400, detail=f"NAP Port {alloc_in.port_number} is already allocated.")

    order.nap_id = alloc_in.nap_id
    order.drop_cable_id = alloc_in.drop_cable_id
    order.nap_port = alloc_in.port_number
    order.status = WorkflowStage.DESIGNED

    db.commit()
    db.refresh(order)
    return order


# --- NEW ENDPOINT: Complete Installation ---
@router.post("/{order_id}/complete", response_model=ServiceOrderResponse)
async def complete_installation(
    order_id: UUID,
    flexscan_result_dbm: float = Form(...),
    checklist_completed: bool = Form(...),
    photo_nap: UploadFile = File(None),
    photo_routing: UploadFile = File(None),
    photo_rosette: UploadFile = File(None),
    photo_flexscan: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # 1. Find the Service Order
    order = db.query(ServiceOrder).filter(ServiceOrder.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Service Order not found")

    # 2. Check existing metrics to avoid duplicates
    if order.metrics:
        raise HTTPException(status_code=400, detail="Installation metrics already exist for this order.")

    # 3. Save Uploaded Files locally
    nap_url = save_upload_file(photo_nap, order_id, "nap")
    routing_url = save_upload_file(photo_routing, order_id, "routing")
    rosette_url = save_upload_file(photo_rosette, order_id, "rosette")
    flexscan_url = save_upload_file(photo_flexscan, order_id, "flexscan")

    # 4. Create the Metrics Record
    metrics = InstallMetrics(
        order_id=order_id,
        flexscan_result_dbm=flexscan_result_dbm,
        checklist_completed=checklist_completed,
        photo_nap_url=nap_url,
        photo_routing_url=routing_url,
        photo_rosette_url=rosette_url,
        photo_flexscan_url=flexscan_url
    )
    
    db.add(metrics)

    # 5. Advance the workflow state
    order.status = WorkflowStage.PENDING_ACCEPTANCE

    db.commit()
    db.refresh(order)
    
    return order