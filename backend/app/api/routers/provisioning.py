from fastapi import APIRouter, Depends, HTTPException # <-- Added HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID # <-- Ensure UUID is imported

from app.core.db import get_db
from app.models.provisioning import ServiceOrder, WorkflowStage
from app.schemas.provisioning import ServiceOrderCreate, ServiceOrderResponse, ServiceOrderAllocate

# Import infrastructure to validate allocations
from app.models.infrastructure import NAP, DropCable
from app.models.allocations import DropAllocation

router = APIRouter(prefix="/provisioning", tags=["Provisioning Workflow"])

def generate_ids(customer_name: str, bandwidth: str, db: Session) -> tuple:
    """Auto-generates Service ID based on your NOC's naming convention"""
    names = customer_name.strip().split()
    first_name = names[0][:4].upper()
    prefix = f"{first_name}C01"
    
    # NEW LOGIC: Count ONLY existing orders that share this exact prefix
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
    # 1. Find the Service Order
    order = db.query(ServiceOrder).filter(ServiceOrder.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Service Order not found")
        
    # 2. Check if it's in the right stage
    if order.status != WorkflowStage.REQUESTED:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot allocate order. Current status is {order.status}"
        )

    # 3. Verify the NAP exists and check its capacity
    nap = db.query(NAP).filter(NAP.nap_id == alloc_in.nap_id).first()
    if not nap:
        raise HTTPException(status_code=404, detail="NAP not found")
        
    if alloc_in.port_number > nap.total_ports:
        raise HTTPException(
            status_code=400, 
            detail=f"Port {alloc_in.port_number} exceeds NAP capacity of {nap.total_ports}."
        )

    # 4. Check if the port is already in use by another customer
    existing_alloc = db.query(DropAllocation).join(DropCable).filter(
        DropCable.nap_id == alloc_in.nap_id,
        DropAllocation.nap_port_number == alloc_in.port_number
    ).first()
    
    if existing_alloc:
        raise HTTPException(
            status_code=400, 
            detail=f"NAP Port {alloc_in.port_number} is already allocated to another service."
        )

    # 5. Success! Assign the IDs and update status
    order.nap_id = alloc_in.nap_id
    order.drop_cable_id = alloc_in.drop_cable_id
    order.nap_port = alloc_in.port_number
    order.status = WorkflowStage.DESIGNED

    db.commit()
    db.refresh(order)
    
    return order