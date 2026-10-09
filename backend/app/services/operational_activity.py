from datetime import datetime, timezone
from app.models.activity import ActivityEntry


def record_event(db, title, description, order_id=None, completed=False, incident_id=None):
    hour = (datetime.now(timezone.utc).hour + 1) % 24
    shift = "Morning" if 6 <= hour < 14 else "Afternoon" if 14 <= hour < 22 else "Night"
    db.add(ActivityEntry(person="System", shift=shift, category="Activity / Task",
                        title=title, description=description, status="Completed" if completed else "Open",
                        handover=not completed, order_id=order_id, incident_id=incident_id))
