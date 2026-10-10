from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException,Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session,selectinload
from sqlalchemy.exc import IntegrityError
from app.core.db import get_db
from app.models.crm import Customer, Service
from app.models.infrastructure import FiberCore
from app.models.allocations import CoreAllocation
from app.services.operational_activity import record_event

router = APIRouter(prefix="/services", tags=["Service provisioning"])


@router.get('/')
def service_catalogue(customer_id:UUID|None=None,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),db:Session=Depends(get_db)):
    from app.models.provisioning import ServiceOrder
    query=db.query(Service)
    if customer_id:query=query.filter_by(customer_id=customer_id)
    total=query.count()
    records=query.options(selectinload(Service.customer)).order_by(Service.created_at.desc(),Service.service_id).offset(offset).limit(limit).all()
    linked_orders={record.service_id:[] for record in records}
    if records:
        for order in db.query(ServiceOrder).filter(ServiceOrder.activated_service_id.in_(list(linked_orders))).order_by(ServiceOrder.order_id).all():
            linked_orders[order.activated_service_id].append({'order_id':order.order_id,'fn_number':order.fn_number})
    return {'total':total,'offset':offset,'limit':limit,'items':[{
      'service_id':s.service_id,'customer_id':s.customer_id,'customer_name':s.customer.customer_name,
      'service_type':s.service_type,'bandwidth_mbps':s.bandwidth_mbps,'status':s.status,
      'ftth_orders':linked_orders[s.service_id]
    } for s in records]}


@router.get("/free-cores")
def free_cores(db: Session = Depends(get_db)):
    allocated = {row[0] for row in db.query(CoreAllocation.core_id).filter(CoreAllocation.end_date.is_(None)).all()}
    return [{"core_id": str(core.core_id), "number": core.core_number, "cable": core.cable.cable_name,
             "route": core.cable.route.route_name, "usage_type": core.usage_type}
            for core in db.query(FiberCore).filter_by(allocation_status="free").all()
            if core.core_id not in allocated and not core.pfps and core.cable.status == "active"]


class ServiceProvision(BaseModel):
    customer_id: UUID | None = None
    customer_name: str | None = Field(default=None, min_length=1, max_length=300)
    customer_code: str | None = Field(default=None, min_length=1, max_length=100)
    address: str | None = Field(default=None, max_length=2000)
    service_type: Literal["DIA", "DARKFIBER", "LAYER2"]
    bandwidth_mbps: int | None = Field(default=None, gt=0)
    core_id: UUID
    backup_core_id: UUID | None = None

    @model_validator(mode="after")
    def validate_service(self):
        if not self.customer_id and (not self.customer_name or not self.customer_code or not self.customer_name.strip() or not self.customer_code.strip()):
            raise ValueError("Select a customer or supply a name and customer code")
        if self.service_type != "DARKFIBER" and self.bandwidth_mbps is None:
            raise ValueError("Bandwidth is required for this service")
        if self.backup_core_id == self.core_id:
            raise ValueError("Primary and backup cores must differ")
        return self


@router.post("/")
def provision_service(payload: ServiceProvision, db: Session = Depends(get_db)):
    ids = [payload.core_id] + ([payload.backup_core_id] if payload.backup_core_id else [])
    cores = db.query(FiberCore).filter(FiberCore.core_id.in_(ids)).order_by(FiberCore.core_id).with_for_update().all()
    if len(cores) != len(ids):
        raise HTTPException(status_code=404, detail="Selected core not found")
    for core in cores:
        if core.allocation_status != "free" or core.pfps or core.cable.status != "active" or core.usage_type not in ("FREE", payload.service_type) or db.query(CoreAllocation).filter_by(core_id=core.core_id, end_date=None).first():
            raise HTTPException(status_code=409, detail="Selected core is occupied, feeds a splitter or is incompatible with this service")
    customer = db.get(Customer, payload.customer_id) if payload.customer_id else None
    if payload.customer_id and not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    try:
        if customer is None:
            customer = Customer(customer_name=payload.customer_name.strip(), service_id_code=payload.customer_code.strip(), customer_type="METROREACH", address=payload.address)
            db.add(customer); db.flush()
        service = Service(customer_id=customer.customer_id, service_type=payload.service_type,
                          bandwidth_mbps=None if payload.service_type == "DARKFIBER" else payload.bandwidth_mbps, status="active")
        db.add(service); db.flush()
        for core in cores:
            core.allocation_status = "allocated"
            core.usage_type = payload.service_type
            db.add(CoreAllocation(service_id=service.service_id, core_id=core.core_id,
                                  allocation_role="primary" if core.core_id == payload.core_id else "backup"))
        record_event(db, f"Service provisioned: {customer.customer_name}", f"{payload.service_type}; {len(cores)} core path(s) recorded", completed=True)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Customer code or core allocation conflicts with an existing record")
    return {"service_id": str(service.service_id), "customer_id": str(customer.customer_id)}
