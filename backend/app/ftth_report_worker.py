"""One-shot weekly report job. Disabled unless explicitly configured; never runs in the API process."""
import argparse
import csv
import datetime as dt
import hashlib
import html
import io
import json
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import format_datetime
from uuid import uuid4
from sqlalchemy.exc import IntegrityError
from app.core.db import SessionLocal
from app.core.security import actor_context
from app.models.ftth_reporting import FtthReportDelivery
from app.services.ftth_planning import LAGOS, now, week


def configuration():
    enabled = os.getenv('FTTH_WEEKLY_EMAIL_ENABLED', '').lower() == 'true'
    recipients = list(dict.fromkeys(x.strip().lower() for x in os.getenv('FTTH_WEEKLY_RECIPIENTS', '').split(',') if x.strip()))
    sender = os.getenv('FTTH_SMTP_FROM', '')
    address = re.compile(r'^[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
    if enabled and (not recipients or len(recipients) > 30 or not all(address.fullmatch(x) for x in recipients + [sender])
                    or not os.getenv('FTTH_SMTP_HOST')):
        raise ValueError('Configure an approved SMTP host, sender and 1–30 recipient addresses')
    if enabled and bool(os.getenv('FTTH_SMTP_USERNAME')) != bool(os.getenv('FTTH_SMTP_PASSWORD')):
        raise ValueError('Configure both SMTP credentials or use an approved unauthenticated TLS relay')
    return {'enabled': enabled, 'recipients': recipients, 'sender': sender}


def due_week(moment):
    local = moment.astimezone(LAGOS)
    # Previous Monday–Sunday, due every Monday 11:45 WAT. Later checks catch up within the week.
    if local.weekday() == 0 and (local.hour, local.minute) < (11, 45):
        return None
    return local.date() - dt.timedelta(days=local.weekday() + 7)


def queue(db, moment, recipients):
    start = due_week(moment)
    if start is None:
        return 0
    snapshot = week(db, start)
    snapshot['captured_at'] = moment.isoformat()
    count = 0
    for recipient in recipients:
        key = hashlib.sha256(f'ftth-weekly:{start.isoformat()}:{recipient}'.encode()).hexdigest()
        if db.query(FtthReportDelivery).filter_by(delivery_key=key).first():
            continue
        record = FtthReportDelivery(delivery_id=uuid4(), delivery_key=key, recipient=recipient,
            payload=snapshot, status='queued', attempts=0, updated_at=moment)
        try:
            with db.begin_nested():
                db.add(record); db.flush()
            count += 1
        except IntegrityError:
            pass  # Another timer already captured this period for this recipient.
    db.commit()
    return count


def safe_cell(value):
    value = str(value or '')
    return "'" + value if re.match(r'^\s*[=+@-]|^[\t\r]', value) else value


def message(record, sender):
    payload = record.payload
    totals = payload['totals']
    lines = [f"AFL weekly field work | {payload['week_start']} to {payload['week_end']}",
        'Complete closed week' if payload['complete'] else 'PARTIAL REPORT — missing or unclosed daily records',
        f"Planned entries: {totals['planned']}; completed entries: {totals['completed']}; pending: {totals['pending']}",
        'Missing dates: ' + (', '.join(payload['missing_dates']) or 'None'),
        'Unclosed dates: ' + (', '.join(payload['unclosed_dates']) or 'None'), payload['counting_basis'],
        'Captured at: ' + payload['captured_at']]
    markup = '<html><body style="font-family:Helvetica;color:#36396e"><h1>AFL weekly field work</h1>' + ''.join(
        '<p>' + html.escape(line) + '</p>' for line in lines) + '</body></html>'
    msg = EmailMessage()
    msg['Subject'] = f"AFL weekly FTTH | {payload['week_start']} | {'Closed' if payload['complete'] else 'Partial'}"
    msg['From'] = sender; msg['To'] = record.recipient
    msg['Message-ID'] = f'<ftth-{record.delivery_key}@noc.afl.invalid>'
    msg['Date'] = format_datetime(now())
    msg.set_content('\n'.join(lines)); msg.add_alternative(markup, subtype='html')
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(['Date', 'Report status', 'FN', 'Customer', 'Provider', 'Area', 'Outcome', 'Reason'])
    for report in payload['reports']:
        for customer in report['customers']:
            writer.writerow([safe_cell(v) for v in [report['date'], report['status'], customer['fn_number'],
                customer['customer_name'], customer['isp'], customer['service_area'], customer['status'], customer['comment']]])
    msg.add_attachment(('\ufeff' + output.getvalue()).encode(), maintype='text', subtype='csv', filename=f"AFL-weekly-{payload['week_start']}.csv")
    from xhtml2pdf import pisa
    pdf = io.BytesIO()
    if pisa.CreatePDF(markup, dest=pdf).err:
        raise RuntimeError('Report PDF generation failed')
    msg.add_attachment(pdf.getvalue(), maintype='application', subtype='pdf', filename=f"AFL-weekly-{payload['week_start']}.pdf")
    return msg


def smtp_send(msg):
    # STARTTLS is required; no plaintext fallback and no browser-facing credentials.
    with smtplib.SMTP(os.environ['FTTH_SMTP_HOST'], int(os.getenv('FTTH_SMTP_PORT', '587')), timeout=30) as smtp:
        smtp.ehlo(); smtp.starttls(context=ssl.create_default_context()); smtp.ehlo()
        if os.getenv('FTTH_SMTP_USERNAME'):
            smtp.login(os.environ['FTTH_SMTP_USERNAME'], os.environ['FTTH_SMTP_PASSWORD'])
        smtp.send_message(msg)


def deliver(db, sender, transport=smtp_send):
    # A crash during SMTP may mean the message was delivered. Flag it for review instead of resending blindly.
    db.query(FtthReportDelivery).filter(FtthReportDelivery.status == 'sending',
        FtthReportDelivery.updated_at < now() - dt.timedelta(minutes=15)).update({
        'status': 'uncertain', 'error_type': 'InterruptedDelivery', 'updated_at': now()}, synchronize_session=False)
    db.commit()
    values = db.query(FtthReportDelivery).filter_by(status='queued').order_by(FtthReportDelivery.updated_at).limit(30).all()
    results = {'sent': 0, 'failed': 0, 'uncertain': 0}
    for record in values:
        try:
            msg = message(record, sender)
        except Exception as error:
            record.status = 'failed'; record.error_type = type(error).__name__; record.updated_at = now()
            db.commit(); results['failed'] += 1; continue
        claimed = db.query(FtthReportDelivery).filter_by(delivery_id=record.delivery_id, status='queued').update({
            'status': 'sending', 'attempts': FtthReportDelivery.attempts + 1, 'updated_at': now()}, synchronize_session=False)
        db.commit()
        if not claimed:
            continue
        try:
            transport(msg)
            record.status = 'sent'; record.error_type = None; results['sent'] += 1
        except Exception as error:
            record.status = 'uncertain'; record.error_type = type(error).__name__; results['uncertain'] += 1
        record.updated_at = now(); db.commit()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--send', action='store_true', help='Queue and send using explicitly enabled server configuration')
    args = parser.parse_args()
    config = configuration()
    actor_context.set({'id': 'ftth-weekly-worker', 'verified': False, 'request_id': ''})
    if not config['enabled']:
        print('Weekly FTTH mail is disabled. No reports queued or sent.'); return
    with SessionLocal() as db:
        start = due_week(now())
        if not args.send:
            print(json.dumps({'dry_run': True, 'period_start': str(start) if start else None,
                'recipient_count': len(config['recipients']), 'due': start is not None}))
            return
        queued = queue(db, now(), config['recipients'])
        print(json.dumps({'queued': queued, **deliver(db, config['sender'])}))


if __name__ == '__main__':
    main()
