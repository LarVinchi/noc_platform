"""Daily work evidence is independent of provisioning acceptance and network snapshots."""
import datetime as dt
from fastapi import HTTPException
from app.models.ftth_reporting import FtthDailyPlan

LAGOS = dt.timezone(dt.timedelta(hours=1))
STATUSES = ('Planned', 'In progress', 'Completed', 'Not completed', 'Excluded')


def now():
    return dt.datetime.now(dt.timezone.utc)


def today():
    return now().astimezone(LAGOS).date()


def day(value):
    try:
        result = dt.date.fromisoformat(value)
        if result.isoformat() != value:
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise HTTPException(422, 'Use an exact YYYY-MM-DD date') from None


def summary(payload, status):
    customers = payload['customers']
    planned = set(payload['planned_ids']) if status != 'planning' else {
        c['order_id'] for c in customers if c['status'] != 'Excluded'}
    completed = {c['order_id'] for c in customers if c['status'] == 'Completed'}
    covered = len(planned & completed)
    return {'planned': len(planned), 'completed': len(completed), 'planned_completed': covered,
            'not_covered': len(planned) - covered, 'additional_completed': len(completed - planned),
            'pending': sum(c['status'] in ('Planned', 'In progress') for c in customers),
            'not_completed': sum(c['status'] == 'Not completed' for c in customers),
            'excluded': sum(c['status'] == 'Excluded' for c in customers),
            'completion_rate': round(100 * covered / len(planned), 2) if planned else None}


def view(plan):
    return {'plan_id': str(plan.plan_id), 'date': plan.report_date.isoformat(), 'revision': plan.revision,
            'status': plan.status, 'created_by': plan.created_by, 'updated_by': plan.updated_by,
            'updated_at': plan.updated_at.isoformat(), **plan.payload,
            'summary': summary(plan.payload, plan.status)}


def week(db, start):
    if start.weekday() != 0 or start > today() + dt.timedelta(days=366):
        raise HTTPException(422, 'Choose a Monday in Lagos within the next year')
    end = start + dt.timedelta(days=6)
    plans = db.query(FtthDailyPlan).filter(FtthDailyPlan.report_date >= start,
        FtthDailyPlan.report_date <= end).order_by(FtthDailyPlan.report_date).all()
    lookup = {p.report_date: p for p in plans}
    days = [start + dt.timedelta(days=n) for n in range(7)]
    items = [view(p) for p in plans]
    missing = [d.isoformat() for d in days if d not in lookup]
    unclosed = [p.report_date.isoformat() for p in plans if p.status != 'closed']
    keys = ('planned', 'completed', 'planned_completed', 'not_covered', 'additional_completed',
            'pending', 'not_completed', 'excluded')
    totals = {k: sum(p['summary'][k] for p in items) for k in keys}
    totals['completion_rate'] = round(100 * totals['planned_completed'] / totals['planned'], 2) if totals['planned'] else None
    return {'week_start': start.isoformat(), 'week_end': end.isoformat(), 'timezone': 'Africa/Lagos',
            'missing_dates': missing, 'unclosed_dates': unclosed, 'elapsed': end < today(),
            'complete': not missing and not unclosed and end < today(), 'totals': totals, 'reports': items,
            'counting_basis': 'Daily work entries; a customer worked on multiple days can appear more than once. Not cumulative connections.'}
