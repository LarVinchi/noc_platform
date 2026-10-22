import datetime as dt
import pytest
from tests.integration.test_ftth_planning import planning  # noqa: F401
from tests.integration.test_knowledge_workflow import api  # noqa: F401
from app import ftth_report_worker as worker
from app.models.ftth_reporting import FtthReportDelivery


@pytest.fixture
def deliveries(planning):
    client, actor, db, ids = planning
    FtthReportDelivery.__table__.create(db.bind)
    return client, actor, db


def test_schedule_lagos_cutoff_and_previous_week():
    monday = dt.datetime(2026, 10, 19, 10, 44, tzinfo=dt.timezone.utc)
    assert worker.due_week(monday) is None
    assert worker.due_week(monday + dt.timedelta(minutes=1)) == dt.date(2026, 10, 12)
    assert worker.due_week(monday + dt.timedelta(days=2)) == dt.date(2026, 10, 12)


def test_snapshot_idempotency_delivery_history_and_ambiguous_transport(deliveries, monkeypatch):
    client, actor, db = deliveries
    moment = dt.datetime(2026, 10, 19, 11, tzinfo=dt.timezone.utc)
    assert worker.queue(db, moment, ['reports@example.invalid']) == 1
    assert worker.queue(db, moment, ['reports@example.invalid']) == 0
    record = db.query(FtthReportDelivery).one()
    assert len(record.payload['missing_dates']) == 7 and not record.payload['complete']
    captured = record.payload.copy()
    monkeypatch.setattr(worker, 'message', lambda record, sender: {'synthetic': True})
    sent = []
    assert worker.deliver(db, 'sender@example.invalid', sent.append)['sent'] == 1
    assert worker.deliver(db, 'sender@example.invalid', sent.append)['sent'] == 0
    assert len(sent) == 1 and record.payload == captured
    assert client.get('/api/ftth/report-deliveries').json()['items'][0]['status'] == 'sent'
    actor['roles'] = ['NOC.Operator']
    assert client.get('/api/ftth/report-deliveries').status_code == 403
    worker.queue(db, moment + dt.timedelta(days=7), ['reports@example.invalid'])
    def fail(_):
        raise TimeoutError('Never expose SMTP response text')
    assert worker.deliver(db, 'sender@example.invalid', fail)['uncertain'] == 1
    assert worker.deliver(db, 'sender@example.invalid', fail)['uncertain'] == 0


def test_worker_disabled_by_default_and_validates_configuration(monkeypatch):
    for key in ('FTTH_WEEKLY_EMAIL_ENABLED', 'FTTH_WEEKLY_RECIPIENTS', 'FTTH_SMTP_FROM', 'FTTH_SMTP_HOST'):
        monkeypatch.delenv(key, raising=False)
    assert not worker.configuration()['enabled']
    monkeypatch.setenv('FTTH_WEEKLY_EMAIL_ENABLED', 'true')
    with pytest.raises(ValueError):
        worker.configuration()


def test_real_mime_csv_pdf_are_generated_without_transport(deliveries):
    _, _, db = deliveries
    worker.queue(db, dt.datetime(2026, 10, 19, 11, tzinfo=dt.timezone.utc), ['reports@example.invalid'])
    msg = worker.message(db.query(FtthReportDelivery).one(), 'sender@example.invalid')
    attachments = list(msg.iter_attachments())
    assert [p.get_content_type() for p in attachments] == ['text/csv', 'application/pdf']
    assert attachments[1].get_payload(decode=True).startswith(b'%PDF')
    assert 'Partial' in msg['Subject']
    assert worker.safe_cell(' =HYPERLINK("example")').startswith("'")
