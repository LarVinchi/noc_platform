import datetime as dt
from uuid import uuid4
import pytest
from tests.integration.test_knowledge_workflow import api  # noqa: F401
from app.api.routers import ftth_planning
from app.models.ftth_reporting import FtthDailyPlan, FtthPlanEvent
from app.models.provisioning import ServiceOrder, ServiceCategory, ISPType
from app.services.ftth_planning import today


@pytest.fixture
def planning(api):
    client, actor, _, db = api
    # Existing service-order FKs reference the registered NOC inventory tables, not fabricated IDs.
    ServiceOrder.__table__.create(db.bind)
    FtthDailyPlan.__table__.create(db.bind); FtthPlanEvent.__table__.create(db.bind)
    ids = [uuid4(), uuid4()]
    for n, key in enumerate(ids):
        db.add(ServiceOrder(order_id=key, service_category=ServiceCategory.FTTH, isp=ISPType.TELEWYZ,
            customer_name=f'Synthetic {n}', fn_number=f'FN-{n}', coverage_zone_name='Synthetic RFS zone'))
    db.commit()
    client.app.include_router(ftth_planning.router, prefix='/api')
    return client, actor, db, [str(k) for k in ids]


def create(client, ids, date=None):
    response = client.post('/api/ftth/daily-plans', json={'date': date or today().isoformat(),
        'customers': [{'order_id': ids[0]}]})
    assert response.status_code == 201, response.text
    return response.json()


def action(client, plan, name, rows=None):
    return client.post(f"/api/ftth/daily-plans/{plan['plan_id']}/{name}", json={
        'revision': plan['revision'], **({'customers': rows} if rows is not None else {})})


def test_frozen_plan_extra_work_closure_and_history(planning):
    client, actor, db, ids = planning
    p = create(client, ids)
    p = action(client, p, 'start').json()
    assert p['planned_ids'] == [ids[0]]
    r = action(client, p, 'save', [{'order_id': ids[0], 'status': 'Not completed', 'comment': 'Customer unavailable'},
        {'order_id': ids[1], 'status': 'Completed'}])
    assert r.status_code == 200, r.text
    p = r.json()
    assert p['summary']['planned'] == 1 and p['summary']['not_covered'] == 1
    assert p['summary']['additional_completed'] == 1 and p['summary']['completion_rate'] == 0
    p = action(client, p, 'close').json()
    assert p['status'] == 'closed'
    assert action(client, p, 'save', []).status_code == 409
    history = client.get(f"/api/ftth/daily-plans/{p['plan_id']}/history").json()['items']
    assert [e['action'] for e in history] == ['create', 'start', 'save', 'close']
    assert history[1]['report']['summary']['planned'] == 1
    assert db.query(ServiceOrder).first().completion_date is None  # Daily reporting never activates a service.


def test_revisions_required_and_pending_blocks_closure(planning):
    client, _, _, ids = planning
    p = create(client, ids); active = action(client, p, 'start').json()
    assert action(client, p, 'save', []).status_code == 409
    assert action(client, active, 'close').status_code == 422
    assert action(client, active, 'save', [{'order_id': ids[0], 'status': 'Not completed'}]).status_code == 422
    assert action(client, active, 'save', []).status_code == 422
    assert action(client, active, 'save', [{'order_id': ids[0]}, {'order_id': ids[0]}]).status_code == 422
    assert client.post(f"/api/ftth/daily-plans/{p['plan_id']}/start", json={'revision': True}).status_code == 422


def test_dates_permissions_and_duplicate_day(planning):
    client, actor, _, ids = planning
    future = (today() + dt.timedelta(days=1)).isoformat()
    p = create(client, ids, future)
    assert action(client, p, 'start').status_code == 422
    assert client.post('/api/ftth/daily-plans', json={'date': future, 'customers': []}).status_code == 409
    actor['roles'] = ['NOC.Viewer']
    assert client.get('/api/ftth/daily-plans').status_code == 200
    assert action(client, p, 'save', []).status_code == 403
    actor['roles'] = ['NOC.Operator']
    assert action(client, p, 'save', [{'order_id': ids[0], 'status': 'Completed'}]).status_code == 422
    assert client.post('/api/ftth/daily-plans', json={'date': '2026-1-1', 'customers': []}).status_code == 422


def test_week_explicitly_reports_missing_unclosed_dates(planning):
    client, _, _, ids = planning
    monday = today() - dt.timedelta(days=today().weekday() + 7)
    p = create(client, ids, monday.isoformat()); p = action(client, p, 'start').json()
    p = action(client, p, 'save', [{'order_id': ids[0], 'status': 'Completed'}]).json()
    r = client.get('/api/ftth/weekly-report', params={'start': monday.isoformat()}).json()
    assert r['totals']['completed'] == 1 and len(r['missing_dates']) == 6
    assert r['unclosed_dates'] == [monday.isoformat()] and not r['complete']
    action(client, p, 'close')
    r = client.get('/api/ftth/weekly-report', params={'start': monday.isoformat()}).json()
    assert r['unclosed_dates'] == [] and not r['complete']
    assert client.get('/api/ftth/weekly-report', params={'start': (monday + dt.timedelta(days=1)).isoformat()}).status_code == 422
    assert client.get('/api/ftth/weekly-report', params={'start': '9999-12-27'}).status_code == 422
