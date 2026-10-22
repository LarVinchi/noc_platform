"""Shared NOC roles; optimistic revisions prevent lost updates to daily plans."""
import copy
import datetime as dt
from uuid import UUID, uuid4
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from app.core.db import get_db
from app.core.security import actor_context
from app.models.provisioning import ServiceOrder, ServiceCategory
from app.models.ftth_reporting import FtthDailyPlan, FtthPlanEvent, FtthReportDelivery
from app.services.ftth_planning import day, now, today, summary, view, week

router = APIRouter(prefix='/ftth', tags=['FTTH daily planning'])


class Customer(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    order_id: UUID
    status: Literal['Planned', 'In progress', 'Completed', 'Not completed', 'Excluded'] = 'Planned'
    comment: str = Field(default='', max_length=1500)


class Change(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    date: str | None = None
    revision: StrictInt | None = Field(default=None, ge=1)
    customers: list[Customer] | None = Field(default=None, max_length=1000)


async def body(request):
    raw = bytearray()
    async for block in request.stream():
        if len(raw) + len(block) > 2000000:
            raise HTTPException(413, 'Daily plan exceeds 2 MB')
        raw.extend(block)
    try:
        return Change.model_validate_json(raw)
    except ValueError:
        raise HTTPException(422, 'Invalid daily plan fields, statuses or revision') from None


def writer():
    if not {'NOC.Admin', 'NOC.Operator'}.intersection(actor_context.get().get('roles', [])):
        raise HTTPException(403, 'Operator role required')


def customers(db, values, previous, status, report_date):
    if values is None:
        raise HTTPException(422, 'Include the full customer list')
    ids = [str(v.order_id) for v in values]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, 'A customer order can appear only once per day')
    old = {c['order_id']: c for c in previous}
    if set(old) - set(ids):
        raise HTTPException(422, 'Keep saved rows; exclude with a reason instead of removing')
    new_ids = [v.order_id for v in values if str(v.order_id) not in old]
    orders = {str(o.order_id): o for o in db.query(ServiceOrder).filter(
        ServiceOrder.order_id.in_(new_ids), ServiceOrder.service_category == ServiceCategory.FTTH).all()} if new_ids else {}
    result = []
    for value in values:
        key = str(value.order_id)
        if value.status in ('Excluded', 'Not completed') and not value.comment:
            raise HTTPException(422, 'Explain every excluded or unfinished customer')
        if (status == 'planning' or report_date > today()) and value.status not in ('Planned', 'Excluded'):
            raise HTTPException(422, 'Start work on or after the report date before recording outcomes')
        if key in old:
            item = copy.deepcopy(old[key])
        else:
            order = orders.get(key)
            if not order:
                raise HTTPException(422, 'Choose an existing FTTH provisioning order')
            item = {'order_id': key, 'customer_name': order.customer_name, 'fn_number': order.fn_number,
                    'isp': order.isp.value, 'service_area': order.coverage_zone_name,
                    'added_after_start': status != 'planning'}
        if value.status == 'Completed' and not item['service_area']:
            current = db.get(ServiceOrder, value.order_id)
            item['service_area'] = current.coverage_zone_name if current else None
        if value.status == 'Completed' and (not item['service_area'] or item['service_area'].casefold() in ('outside rfs', 'outside_rfs', 'outside-rfs')):
            raise HTTPException(422, 'Record a service-area coverage zone in provisioning before marking this customer completed')
        item.update(status=value.status, comment=value.comment)
        result.append(item)
    return result


def event(db, plan, action):
    db.add(FtthPlanEvent(event_id=uuid4(), plan_id=plan.plan_id, revision=plan.revision, action=action,
        actor_id=actor_context.get()['id'], occurred_at=now(), payload=copy.deepcopy(view(plan))))


@router.get('/daily-plans')
def listing(db: Session = Depends(get_db)):
    values = db.query(FtthDailyPlan).order_by(FtthDailyPlan.report_date.desc()).limit(100).all()
    return {'items': [{'plan_id': p.plan_id, 'date': p.report_date, 'status': p.status,
        'revision': p.revision, 'updated_at': p.updated_at, 'summary': summary(p.payload, p.status)} for p in values], 'limit': 100}


@router.get('/daily-plans/{plan_id}')
def detail(plan_id: UUID, db: Session = Depends(get_db)):
    plan = db.get(FtthDailyPlan, plan_id)
    if not plan:
        raise HTTPException(404, 'Daily plan not found')
    return view(plan)


@router.get('/daily-plans/{plan_id}/history')
def history(plan_id: UUID, db: Session = Depends(get_db)):
    return {'items': [{'action': e.action, 'actor_id': e.actor_id, 'occurred_at': e.occurred_at,
        'report': e.payload} for e in db.query(FtthPlanEvent).filter_by(plan_id=plan_id).order_by(FtthPlanEvent.revision).all()]}


@router.post('/daily-plans', status_code=201)
async def create(request: Request, db: Session = Depends(get_db)):
    writer()
    value = await body(request)
    return await run_in_threadpool(create_plan, value, db)


def create_plan(value, db):
    date = day(value.date)
    if date > today() + dt.timedelta(days=366) or value.revision is not None:
        raise HTTPException(422, 'Choose a date within the next year; new plans have no revision')
    plan = FtthDailyPlan(plan_id=uuid4(), report_date=date, revision=1, status='planning',
        payload={'customers': customers(db, value.customers, [], 'planning', date), 'planned_ids': [], 'started_at': None, 'closed_at': None},
        created_by=actor_context.get()['id'], updated_by=actor_context.get()['id'], updated_at=now())
    db.add(plan)
    try:
        db.flush(); event(db, plan, 'create'); db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'A plan already exists for this date; open it instead') from None
    return view(plan)


@router.post('/daily-plans/{plan_id}/{action}')
async def change(plan_id: UUID, action: Literal['save', 'start', 'close'], request: Request, db: Session = Depends(get_db)):
    writer()
    value = await body(request)
    return await run_in_threadpool(change_plan, plan_id, action, value, db)


def change_plan(plan_id, action, value, db):
    plan = db.get(FtthDailyPlan, plan_id)
    if not plan:
        raise HTTPException(404, 'Daily plan not found')
    if plan.revision != value.revision or plan.status == 'closed':
        raise HTTPException(409, 'Report changed or is closed; reload before continuing')
    if value.date is not None or (action != 'save' and value.customers is not None):
        raise HTTPException(422, 'Dates are fixed; save customer changes before starting or closing')
    payload = copy.deepcopy(plan.payload)
    status = plan.status
    if action == 'save':
        payload['customers'] = customers(db, value.customers, payload['customers'], status, plan.report_date)
    else:
        if plan.report_date > today():
            raise HTTPException(422, 'Future work cannot start or close')
        if action == 'start':
            if status != 'planning':
                raise HTTPException(409, 'Work already started')
            payload['planned_ids'] = [c['order_id'] for c in payload['customers'] if c['status'] != 'Excluded']
            payload['started_at'] = now().isoformat(); status = 'active'
        else:
            if status != 'active' or summary(payload, status)['pending']:
                raise HTTPException(422, 'Start work and resolve all pending outcomes before closing')
            payload['closed_at'] = now().isoformat(); status = 'closed'
    changed = db.query(FtthDailyPlan).filter_by(plan_id=plan_id, revision=value.revision).update({
        'revision': value.revision + 1, 'status': status, 'payload': payload,
        'updated_by': actor_context.get()['id'], 'updated_at': now()}, synchronize_session=False)
    if changed != 1:
        db.rollback()
        raise HTTPException(409, 'Another operator saved this plan; reload before continuing')
    db.expire(plan); db.refresh(plan); event(db, plan, action); db.commit()
    return view(plan)


@router.get('/weekly-report')
def weekly(start: str, db: Session = Depends(get_db)):
    return week(db, day(start))


@router.get('/report-deliveries')
def deliveries(db: Session = Depends(get_db)):
    if 'NOC.Admin' not in actor_context.get().get('roles', []):
        raise HTTPException(403, 'Administrator role required for delivery history')
    values = db.query(FtthReportDelivery).order_by(FtthReportDelivery.updated_at.desc()).limit(100).all()
    return {'items': [{'delivery_id': v.delivery_id, 'recipient': v.recipient, 'status': v.status,
        'attempts': v.attempts, 'updated_at': v.updated_at, 'error_type': v.error_type,
        'week_start': v.payload['week_start']} for v in values], 'limit': 100}
