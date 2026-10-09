import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from uuid import UUID 
from pydantic import BaseModel, ValidationError

from app.core.db import get_db
from app.models.provisioning import ServiceOrder, WorkflowStage, InstallMetrics
from app.schemas.provisioning import ServiceOrderCreate, ServiceOrderResponse, ServiceOrderAllocate
from app.schemas.provisioning import IntakePreviewRequest, IntakePreviewResponse, IntakeCreateRequest, IntakeCreateResponse
from app.services.ftth_intake import parse_ftth_request
from app.services.service_orders import create_order
from app.services.activation import activate_ftth
from app.services.operational_activity import record_event
from app.services.ftth_lifecycle import stage_event,guard_acceptance

# Import infrastructure to validate allocations
from app.models.infrastructure import NAP, DropCable
from app.models.allocations import DropAllocation

from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

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


@router.get("/", response_model=List[ServiceOrderResponse])
def get_all_service_orders(db: Session = Depends(get_db)):
    """Fetch all service orders, ordered by newest first."""
    orders = db.query(ServiceOrder).options(selectinload(ServiceOrder.nap), selectinload(ServiceOrder.drop_cable), selectinload(ServiceOrder.metrics)).order_by(ServiceOrder.created_at.desc()).all()
    return orders

@router.post("/", response_model=ServiceOrderResponse)
def create_service_order(order_in: ServiceOrderCreate, db: Session = Depends(get_db)):
    order, _created = create_order(order_in, db)
    return order


@router.post("/intake/preview", response_model=IntakePreviewResponse)
def preview_request(payload: IntakePreviewRequest):
    try:
        fields, warnings = parse_ftth_request(payload.raw_text)
        order = ServiceOrderCreate(**fields, isp=payload.isp)
    except (ValueError, ValidationError) as error:
        raise HTTPException(status_code=422, detail=str(error))
    return {"order": order, "warnings": warnings}


@router.post("/intake", response_model=IntakeCreateResponse)
def import_request(payload: IntakeCreateRequest, db: Session = Depends(get_db)):
    # A pasted request must retain usable external references even after edits.
    if not payload.order.fn_number or not payload.order.work_order_id:
        raise HTTPException(status_code=422, detail="FN number and work order ID are required for pasted requests.")
    order, created = create_order(payload.order, db, raw_text=payload.raw_text)
    return {"outcome": "created" if created else "already_logged", "order": order}


@router.patch("/{order_id}/allocate", response_model=ServiceOrderResponse)
def allocate_service_order(
    order_id: UUID, 
    alloc_in: ServiceOrderAllocate, 
    db: Session = Depends(get_db)
):
    order = db.query(ServiceOrder).filter(ServiceOrder.order_id == order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Service order not found")
    if order.status != WorkflowStage.REQUESTED:
        raise HTTPException(status_code=409, detail="Only new requests can be assigned")
    # Lock the shared NAP while checking/reserving its capacity.
    nap = db.query(NAP).filter(NAP.nap_id == alloc_in.nap_id).with_for_update().first()
    if not nap:
        raise HTTPException(status_code=404, detail="NAP not found")
    if alloc_in.port_number > nap.total_ports:
        raise HTTPException(status_code=422, detail="Port exceeds NAP capacity")
    allocated = db.query(DropAllocation).join(DropCable).filter(
        DropCable.nap_id == nap.nap_id, DropAllocation.nap_port_number == alloc_in.port_number,
        DropAllocation.is_active.is_(True)).first()
    reserved = db.query(ServiceOrder).filter(ServiceOrder.nap_id == nap.nap_id,
        ServiceOrder.nap_port == alloc_in.port_number, ServiceOrder.status != WorkflowStage.REQUESTED).first()
    if allocated or reserved:
        raise HTTPException(status_code=409, detail="This NAP port is already allocated or reserved")
    if alloc_in.drop_cable_id:
        drop = db.get(DropCable, alloc_in.drop_cable_id)
        if not drop or drop.nap_id != nap.nap_id or drop.status != 'active':
            raise HTTPException(status_code=422, detail="Select an active drop cable belonging to this NAP")
        if db.query(DropAllocation).filter_by(drop_cable_id=drop.drop_cable_id, is_active=True).first() or db.query(ServiceOrder).filter(
            ServiceOrder.drop_cable_id == drop.drop_cable_id, ServiceOrder.status != WorkflowStage.REQUESTED).first():
            raise HTTPException(status_code=409, detail="This drop cable is already in use")
    else:
        drop = DropCable(nap_id=nap.nap_id, drop_cable_code=alloc_in.new_drop_cable_code, status='active')
        db.add(drop)
    try:
        db.flush()
        order.nap_id, order.drop_cable_id, order.nap_port = nap.nap_id, drop.drop_cable_id, alloc_in.port_number
        order.pfs_id, order.pfp_id = nap.pfs_id, nap.pfs.pfp_id
        order.drop_tech_name = alloc_in.installer
        order.planned_install_date = alloc_in.planned_install_date.astimezone(timezone.utc).replace(tzinfo=None)
        stage_event_previous = order.status
        order.status = WorkflowStage.SCHEDULED
        stage_event(db,order,stage_event_previous,'Infrastructure allocated and installer scheduled')
        record_event(db, f"FTTH scheduled: {order.fn_number or order.service_order_number}",
                     f"{order.drop_tech_name}; {nap.nap_code} port {order.nap_port}; drop {drop.drop_cable_code}", order.order_id)
        db.commit()
        db.refresh(order)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Port/drop reservation conflicts with another order or an existing cable code")
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
    order = db.query(ServiceOrder).filter(ServiceOrder.order_id == order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Service Order not found")

    if order.status not in (WorkflowStage.SCHEDULED, WorkflowStage.IN_PROGRESS):
        raise HTTPException(status_code=409, detail="Assign and schedule this order before recording installation")
    if not checklist_completed or not all((photo_nap, photo_routing, photo_rosette, photo_flexscan)):
        raise HTTPException(status_code=422, detail="Complete the checklist and supply all four installation photos")
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
    
    # Update the completion date
    order.completion_date = datetime.utcnow()
    stage_event_previous = order.status
    order.status = WorkflowStage.PENDING_ACCEPTANCE
    stage_event(db,order,stage_event_previous,'Installation checklist, photos and optical result recorded')

    record_event(db, f"Installation awaiting review: {order.fn_number or order.service_order_number}",
                 "Installation evidence recorded; NOC review required.", order.order_id)
    db.commit() # Commit to generate the metrics object so the PDF generator can read it
    db.refresh(order)
    
    # 5. Generate the PDF Document
    try:
        # TODO: Replace with `current_user.signature_url` once Auth is fully implemented
        # Example signature path: "/static/uploads/signatures/noc_admin_sig.png"
        current_noc_signature = None 
        
        from app.services.pdf_generator import generate_acceptance_pdf
        pdf_url = generate_acceptance_pdf(order, noc_signature_url=current_noc_signature)
        order.metrics.acceptance_doc_url = pdf_url
        db.commit() 
        db.refresh(order)
    except Exception as e:
        print(f"PDF Generation failed: {e}")

    return order

@router.patch("/{order_id}/accept", response_model=ServiceOrderResponse)
def accept_installation(order_id: UUID, db: Session = Depends(get_db)):
    """NOC approves the installation and moves it to active monitoring."""
    order = db.query(ServiceOrder).filter(ServiceOrder.order_id == order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Service Order not found")
        
    if order.status != WorkflowStage.PENDING_ACCEPTANCE:
        raise HTTPException(status_code=400, detail=f"Cannot accept order in {order.status} stage.")

    if not order.metrics or not order.metrics.checklist_completed or not order.nap_id or not order.drop_cable_id:
        raise HTTPException(status_code=409, detail="Installation evidence and infrastructure assignment are required for acceptance")
    guard_acceptance(db,order)
    activate_ftth(order, db)
    order.status = WorkflowStage.MONITORED
    stage_event(db,order,WorkflowStage.PENDING_ACCEPTANCE,'NOC accepted installation; monitoring health remains unverified')
    record_event(db, f"FTTH accepted: {order.fn_number or order.service_order_number}",
                 "CRM service and drop allocation created. Monitoring verification is pending.", order.order_id, completed=True)
    db.commit()
    db.refresh(order)
    
    return order

class StatusUpdate(BaseModel):
    status: WorkflowStage

@router.patch("/{order_id}/status", response_model=ServiceOrderResponse)
def update_order_status(order_id: UUID, status_update: StatusUpdate, db: Session = Depends(get_db)):
    """Generic endpoint to update an order's status via drag-and-drop."""
    order = db.query(ServiceOrder).filter(ServiceOrder.order_id == order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Service Order not found")
        
    allowed = {
        WorkflowStage.SCHEDULED: {WorkflowStage.IN_PROGRESS},
        WorkflowStage.IN_PROGRESS: {WorkflowStage.SCHEDULED},
    }
    if status_update.status not in allowed.get(order.status, set()):
        raise HTTPException(status_code=409, detail="Use assignment, installation evidence and NOC approval to advance this order")
    previous = order.status
    order.status = status_update.status
    stage_event(db,order,previous,'Installation started' if order.status==WorkflowStage.IN_PROGRESS else 'Returned to scheduling; previous stage visit retained')
    record_event(db, f"FTTH stage: {order.fn_number or order.service_order_number}",
                 f"Moved to {order.status.value}", order.order_id)
    db.commit()
    db.refresh(order)
    return order
