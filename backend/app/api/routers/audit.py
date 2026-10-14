from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.db import get_db

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/")
def list_audit(before: int | None = None, entity_id: str | None = Query(None, max_length=200),
               limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT * FROM audit_events WHERE (:before IS NULL OR audit_id < :before)
        AND (:entity_id IS NULL OR entity_id = :entity_id)
        ORDER BY audit_id DESC LIMIT :limit
    """), {"before": before, "entity_id": entity_id, "limit": limit}).mappings().all()
    return {"items": [dict(row) for row in rows],
            "next_before": rows[-1]["audit_id"] if len(rows) == limit else None}
