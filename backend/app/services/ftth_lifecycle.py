from uuid import uuid4
from fastapi import HTTPException
from app.core.security import actor_context
from app.models.provisioning import ServiceCategory
from app.models.ftth_operations import FtthStageEvent,FtthIncidentLink
from app.models.incidents import Incident
from app.services.incident_response import ACTIVE,now_utc


def stage_event(db,order,previous,note):
    if order.service_category!=ServiceCategory.FTTH:
        return
    db.add(FtthStageEvent(event_id=uuid4(),order_id=order.order_id,from_stage=getattr(previous,'value',previous),
        to_stage=order.status.value,actor_id=actor_context.get()['id'],occurred_at=now_utc(),note=note))


def guard_acceptance(db,order):
    if db.query(FtthIncidentLink).join(Incident,Incident.incident_id==FtthIncidentLink.incident_id).filter(
        FtthIncidentLink.order_id==order.order_id,FtthIncidentLink.kind=='installation_blocker',Incident.status.in_(ACTIVE)).first():
        raise HTTPException(409,'Resolve the linked installation blockers before NOC acceptance')
