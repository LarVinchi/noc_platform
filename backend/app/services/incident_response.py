from datetime import datetime, timedelta, timezone
from uuid import uuid4
from pydantic import EmailStr, TypeAdapter, ValidationError
from app.core.config import settings
from app.core.security import actor_context
from app.models.response import Engineer, ResponsePolicy, ResponseEvent, NotificationDraft
from app.services.operational_activity import record_event
from app.services.response_metrics import utc

ACTIVE = {"open", "investigating", "pending"}


def now_utc():
    return datetime.now(timezone.utc)


def usable_policy(db, *, severity=None, service_id=None, at=None):
    query = db.query(ResponsePolicy).filter(ResponsePolicy.effective_from <= (at or now_utc()))
    query = query.filter(ResponsePolicy.service_id == service_id) if service_id else query.filter(ResponsePolicy.severity == severity, ResponsePolicy.service_id.is_(None))
    if settings.ENVIRONMENT != "development":
        query = query.filter(ResponsePolicy.preview_only.is_(False))
    return query.order_by(ResponsePolicy.version.desc()).first()


def timeline(db, incident, event_type, message, *, key=None, outage_id=None, at=None):
    key = key or str(uuid4())
    if db.query(ResponseEvent).filter_by(event_key=key).first():
        return False
    db.add(ResponseEvent(event_key=key, incident_id=incident.incident_id, outage_id=outage_id,
                         event_type=event_type, message=message, actor_id=actor_context.get()["id"], occurred_at=at or now_utc()))
    record_event(db, title=f"{incident.tt_number or 'Incident'}: {event_type.replace('_', ' ')}",
                 description=message, incident_id=incident.incident_id)
    return True


def valid_recipients(values):
    result = []
    for value in values:
        if not value:
            continue
        try:
            email = str(TypeAdapter(EmailStr).validate_python(value))
            if email not in result:
                result.append(email)
        except ValidationError:
            pass
    return result


def draft(db, incident, key, audience, recipients, subject, body, service_id=None):
    if db.query(NotificationDraft).filter_by(event_key=key).first():
        return
    db.add(NotificationDraft(event_key=key, incident_id=incident.incident_id, service_id=service_id,
                             audience=audience, recipients=valid_recipients(recipients), subject=subject[:250], body=body, status="draft"))


def invalidate_drafts(db, incident, audiences, service_id=None):
    query = db.query(NotificationDraft).filter(NotificationDraft.incident_id==incident.incident_id,
        NotificationDraft.audience.in_(audiences),NotificationDraft.status.in_(['draft','reviewed']))
    if service_id is not None:
        query = query.filter_by(service_id=service_id)
    for record in query.all():
        record.status='discarded';record.reviewed_at=now_utc();record.reviewed_by=actor_context.get()['id']


def pin_policy(db, incident, *, at=None):
    if incident.response_policy_id:
        return
    db.flush()
    policy = usable_policy(db, severity=incident.severity, at=at or utc(incident.reported_at))
    if not policy:
        return
    incident.response_policy_id = policy.policy_id
    incident.ack_deadline_at = utc(incident.reported_at) + timedelta(minutes=policy.acknowledgment_minutes)
    incident.restore_deadline_at = utc(incident.reported_at) + timedelta(minutes=policy.restoration_minutes)
    timeline(db, incident, "policy_applied", f"{policy.name} v{policy.version}; acknowledgment {policy.acknowledgment_minutes}m, restoration goal {policy.restoration_minutes}m from report time.")
    if not incident.assigned_engineer_id and not (incident.responsible_person or '').strip() and policy.default_engineer_id:
        engineer = db.get(Engineer, policy.default_engineer_id)
        if engineer and engineer.enabled:
            assign_engineer(db, incident, engineer)


def assign_engineer(db, incident, engineer):
    if incident.assigned_engineer_id == engineer.engineer_id:
        return
    invalidate_drafts(db,incident,['engineer'])
    incident.assigned_engineer_id = engineer.engineer_id
    incident.responsible_person = engineer.name
    db.flush()
    key = f"assign:{incident.incident_id}:{uuid4()}"
    timeline(db, incident, "engineer_assigned", f"Assigned to {engineer.name} ({engineer.team}).", key=key)
    draft(db, incident, key, "engineer", [engineer.email], f"Action required: {incident.tt_number}",
          f"Incident {incident.tt_number}: {incident.short_description or incident.incident_type}.\nAssigned engineer: {engineer.name}.\nAcknowledge in the NOC platform and verify affected services.\nThis is a review draft; no message has been sent.")


def initialize_response(db, incident):
    pin_policy(db, incident)


def preview_policies(db):
    # Only called by an explicitly selected preview administration action.
    if settings.ENVIRONMENT != "development" or settings.AUTH_MODE != "preview":
        return False
    for severity, ack, restore in (("Critical", 15, 120), ("High", 30, 240), ("Medium", 60, 480), ("Low", 240, 1440)):
        if db.query(ResponsePolicy).filter_by(severity=severity).first():
            continue
        db.add(ResponsePolicy(name=f"Preview {severity} response", severity=severity, version=1,
                              acknowledgment_minutes=ack, restoration_minutes=restore, followup_minutes=60,
                              preview_only=True, escalation_recipients=[], effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc)))
    return True
