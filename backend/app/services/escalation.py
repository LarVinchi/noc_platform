"""Transactional scheduler. Drafts/events are idempotent and nothing is delivered."""
from datetime import timedelta
from sqlalchemy import and_, or_, exists, func, cast, String
from sqlalchemy.orm import selectinload
from app.models.crm import Service
from app.models.incidents import Incident
from app.models.response import Engineer, ResponsePolicy, ServiceOutage
from app.services.incident_response import ACTIVE, draft, timeline, now_utc
from app.services.response_metrics import utc, deadline_state


def run_escalations(db, now=None):
    now = now or now_utc()
    count = 0
    # Serialize schedulers across replicas without blocking the API.
    from sqlalchemy import text
    if not db.execute(text("SELECT pg_try_advisory_xact_lock(72184096)")).scalar():
        return 0
    incidents = db.query(Incident).filter(Incident.status.in_(ACTIVE), Incident.response_policy_id.isnot(None),
        Incident.escalation_level<3, Incident.is_planned.isnot(True),
        or_(and_(Incident.acknowledged_at.is_(None), Incident.ack_deadline_at<now),Incident.restore_deadline_at<now)
    ).order_by(Incident.reported_at).with_for_update(skip_locked=True).all()
    for incident in incidents:
        if incident.is_planned:
            continue
        policy = db.get(ResponsePolicy, incident.response_policy_id)
        if not policy:
            continue
        from app.core.config import settings
        if policy.preview_only and settings.ENVIRONMENT != 'development':
            continue
        engineer = db.get(Engineer, incident.assigned_engineer_id) if incident.assigned_engineer_id else None
        recipients = (policy.escalation_recipients or []) + ([engineer.email] if engineer and engineer.enabled else [])
        rules = []
        if incident.acknowledged_at is None and incident.ack_deadline_at and now > utc(incident.ack_deadline_at):
            rules.append((1, "Acknowledgment is overdue"))
        if incident.restore_deadline_at and now > utc(incident.restore_deadline_at):
            rules.append((2, "Incident restoration goal is overdue"))
            if now > utc(incident.restore_deadline_at) + timedelta(minutes=policy.followup_minutes):
                rules.append((3, "Incident remains unresolved after the follow-up deadline"))
        for level, reason in rules:
            key = f"incident:{incident.incident_id}:escalation:{level}"
            if timeline(db, incident, "escalated", f"Level {level}: {reason}. Policy {policy.name} v{policy.version}.", key=key, at=now):
                incident.escalation_level = max(incident.escalation_level, level)
                draft(db, incident, key, "escalation", recipients, f"L{level} escalation: {incident.tt_number}",
                      f"{reason}.\nIncident: {incident.tt_number} — {incident.short_description or incident.incident_type}.\nOwner: {incident.responsible_person or 'Unassigned'}.\nReview the NOC response queue. This draft has not been sent.")
                count += 1
        db.flush()
    from app.models.response import ResponseEvent
    missing_ack_event = ~exists().where(ResponseEvent.event_key == func.concat('outage:',cast(ServiceOutage.outage_id,String),':ack:breach'))
    missing_restore_event = ~exists().where(ResponseEvent.event_key == func.concat('outage:',cast(ServiceOutage.outage_id,String),':restoration:breach'))
    due_outages = db.query(ServiceOutage).join(Incident,Incident.incident_id==ServiceOutage.incident_id).options(
        selectinload(ServiceOutage.service).selectinload(Service.customer),selectinload(ServiceOutage.incident)
    ).filter(ServiceOutage.policy_id.isnot(None),ServiceOutage.excluded.is_(False),or_(
        and_(ServiceOutage.ack_deadline_at<now,or_(Incident.acknowledged_at.is_(None),Incident.acknowledged_at>ServiceOutage.ack_deadline_at),missing_ack_event),
        and_(ServiceOutage.restore_deadline_at<now,or_(ServiceOutage.restored_at.is_(None),ServiceOutage.restored_at>ServiceOutage.restore_deadline_at),missing_restore_event)
    )).all()
    for candidate in due_outages:
        # Match API lock order: incident before outage. Refresh candidates after
        # locking so restoration/review changes cannot produce a stale draft.
        incident = db.query(Incident).filter_by(incident_id=candidate.incident_id).with_for_update(skip_locked=True).populate_existing().first()
        if incident is None:
            continue
        outage = db.query(ServiceOutage).filter_by(outage_id=candidate.outage_id).with_for_update(skip_locked=True).populate_existing().first()
        if outage is None:
            continue
        policy = db.get(ResponsePolicy, outage.policy_id)
        from app.core.config import settings
        if policy.preview_only and settings.ENVIRONMENT != 'development':
            continue
        for kind, deadline, completed in (("ack", outage.ack_deadline_at, incident.acknowledged_at), ("restoration", outage.restore_deadline_at, outage.restored_at)):
            if deadline_state(deadline, completed, now) != 'breached':
                continue
            key = f"outage:{outage.outage_id}:{kind}:breach"
            if timeline(db, incident, "service_target_breached", f"{outage.service.customer.customer_name}: confirmed outage {kind} target breached ({policy.name} v{policy.version}).", key=key, outage_id=outage.outage_id, at=now):
                restoration = f'Restoration verified at {utc(outage.restored_at).isoformat()}.' if outage.restored_at else 'Restoration has not yet been verified.'
                draft(db, incident, key, "customer", [outage.service.customer.email], f"Service incident update: {incident.tt_number}",
                      f"A confirmed outage on your {outage.service.service_type} service is associated with {incident.tt_number}.\nThe recorded {kind} response target has been exceeded.\n{restoration}\nReview evidence and wording before delivery; do not promise an unconfirmed restoration time.", service_id=outage.service_id)
                count += 1
        db.flush()
    return count
