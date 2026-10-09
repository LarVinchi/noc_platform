"""Transactional FTTH order creation with repeat-safe external identities."""
from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.models.provisioning import ServiceOrder, ServiceOrderSequence, WorkflowStage
from app.services.ftth_lifecycle import stage_event


def normalized(value):
    return " ".join(str(getattr(value, "value", value) or "").split()).casefold()


def generate_ids(customer_name, bandwidth, db):
    prefix = customer_name.strip().split()[0][:4].upper() + "C01"
    statement = insert(ServiceOrderSequence).values(prefix=prefix, last_sequence=1)
    sequence = db.execute(statement.on_conflict_do_update(
        index_elements=[ServiceOrderSequence.prefix],
        set_={"last_sequence": ServiceOrderSequence.last_sequence + 1},
    ).returning(ServiceOrderSequence.last_sequence)).scalar_one()
    suffix = f"{sequence:05d}"
    return f"{prefix}-{suffix}", f"{prefix}-FTTH-{bandwidth}-{suffix}"


def find_existing(order_in, db):
    references = []
    if order_in.fn_number:
        references.append(ServiceOrder.fn_number == order_in.fn_number)
    if order_in.work_order_id:
        references.append(ServiceOrder.work_order_id == order_in.work_order_id)
    if not references:
        return []
    return db.query(ServiceOrder).filter(ServiceOrder.isp == order_in.isp, or_(*references)).all()


def check_existing(matches, order_in):
    if len(matches) != 1:
        raise HTTPException(status_code=409, detail="FN and work-order references point to different orders. Reconcile the existing records.")
    existing = matches[0]
    # Do not silently overwrite an order with changed customer/contact details.
    for field in ("fn_number", "work_order_id", "customer_name", "service_address",
                  "bandwidth", "phone_number", "email", "service_category"):
        if normalized(getattr(existing, field)) != normalized(getattr(order_in, field)):
            raise HTTPException(status_code=409, detail="This FN or work order is already logged with different details. Review the existing order before changing it.")
    return existing


def create_order(order_in, db, raw_text=None):
    matches = find_existing(order_in, db)
    if matches:
        return check_existing(matches, order_in), False
    try:
        so_number, service_id = generate_ids(order_in.customer_name, order_in.bandwidth, db)
        order = ServiceOrder(
            **order_in.model_dump(), service_order_number=so_number,
            service_id=service_id, status=WorkflowStage.REQUESTED,
            intake_source="paste" if raw_text is not None else "manual",
            raw_request_text=raw_text,
        )
        db.add(order)
        db.flush()
        stage_event(db,order,None,'FTTH request recorded')
        db.commit()
        db.refresh(order)
        return order, True
    except IntegrityError:
        db.rollback()
        matches = find_existing(order_in, db)
        if matches:
            return check_existing(matches, order_in), False
        raise HTTPException(status_code=409, detail="Order creation conflicts with an existing record. Review the identifiers and retry.")
