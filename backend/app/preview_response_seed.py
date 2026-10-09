from sqlalchemy import text
from app.core.db import SessionLocal
from app.services.incident_response import preview_policies
from app.core.security import actor_context

if __name__ == '__main__':
    actor_context.set({'id':'preview-policy-seed','verified':False,'request_id':''})
    with SessionLocal() as db:
        db.execute(text('SELECT pg_advisory_xact_lock(72184097)'))
        preview_policies(db)
        db.commit()
