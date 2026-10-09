from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from uuid import UUID

from app.core.db import get_db
from app.models.infrastructure import NAP, PFS, DropCable
from app.models.allocations import DropAllocation
from app.models.provisioning import ServiceOrder, WorkflowStage

router = APIRouter(prefix="/inventory", tags=["Inventory"])


class NAPCreate(BaseModel):
    nap_code: str = Field(min_length=1, max_length=100)
    pfs_id: UUID
    total_ports: int = Field(ge=1, le=128)

    @field_validator("nap_code")
    @classmethod
    def normalize_code(cls, value):
        value = value.strip().upper()
        if not value:
            raise ValueError("NAP code is required")
        return value


@router.get("/assignment-options")
def assignment_options(db: Session = Depends(get_db)):
    result = []
    for nap in db.query(NAP).order_by(NAP.nap_code).all():
        allocated = {row[0] for row in db.query(DropAllocation.nap_port_number).join(DropCable)
                     .filter(DropCable.nap_id == nap.nap_id, DropAllocation.is_active.is_(True)).all()}
        reserved = {row[0] for row in db.query(ServiceOrder.nap_port)
                    .filter(ServiceOrder.nap_id == nap.nap_id, ServiceOrder.status != WorkflowStage.REQUESTED).all()}
        used_drops = {row[0] for row in db.query(DropAllocation.drop_cable_id)
                      .filter(DropAllocation.is_active.is_(True)).all()}
        used_drops.update(row[0] for row in db.query(ServiceOrder.drop_cable_id)
                          .filter(ServiceOrder.status != WorkflowStage.REQUESTED).all())
        result.append({"nap_id": str(nap.nap_id), "nap_code": nap.nap_code,
                       "pfs": nap.pfs.name, "pfp": nap.pfs.pfp.name,
                       "available_ports": [p for p in range(1, nap.total_ports + 1) if p not in allocated | reserved],
                       "drop_cables": [{"drop_cable_id": str(d.drop_cable_id), "code": d.drop_cable_code}
                                       for d in nap.drop_cables if d.drop_cable_id not in used_drops and d.status == "active"]})
    return {"naps": result, "splitters": [{"pfs_id": str(p.pfs_id), "name": p.name, "pfp": p.pfp.name}
                                          for p in db.query(PFS).order_by(PFS.name).all()]}


@router.post("/naps")
def create_nap(payload: NAPCreate, db: Session = Depends(get_db)):
    if not db.get(PFS, payload.pfs_id):
        raise HTTPException(status_code=404, detail="Upstream splitter not found")
    nap = NAP(**payload.model_dump())
    db.add(nap)
    try:
        db.commit()
        db.refresh(nap)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This NAP code already exists")
    return {"nap_id": str(nap.nap_id), "nap_code": nap.nap_code}
