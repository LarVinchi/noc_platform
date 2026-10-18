import hashlib
import json
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import ValidationError
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.config import settings
from app.models.platform_health import PlatformHost, PlatformSample
from app.schemas.platform_health import AgentReport
from app.services.platform_health import summarize

router = APIRouter(prefix='/platform-health', tags=['Server health and deployments'])
MAX_REPORT = 256 * 1024


@router.post('/ingest')
async def ingest(request: Request, db: Session = Depends(get_db)):
    content = bytearray()
    async for block in request.stream():
        if len(content)+len(block) > MAX_REPORT:
            raise HTTPException(413, 'Host report exceeds 256 KiB')
        content.extend(block)
    try:
        report = AgentReport.model_validate_json(content)
    except ValidationError:
        raise HTTPException(422, 'Invalid host report; check the agent schema, counters and timestamps') from None
    if report.host_id != settings.PLATFORM_AGENT_HOST_ID:
        raise HTTPException(403, 'Agent credential is not assigned to this host')
    payload = report.model_dump(mode='json')
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    now = datetime.now(timezone.utc)
    db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'), {'key': 'platform-host:' + report.host_id})
    previous = db.get(PlatformSample, report.sample_id)
    if previous:
        if previous.host_id != report.host_id or previous.digest != digest:
            raise HTTPException(409, 'Sample ID already has different contents')
        return {'outcome': 'duplicate'}
    host = db.get(PlatformHost, report.host_id)
    if host is None:
        host = PlatformHost(host_id=report.host_id, observed_at=report.observed_at, received_at=now, payload=payload)
        db.add(host)
        db.flush()
    elif report.observed_at > host.observed_at:
        host.observed_at, host.received_at, host.payload = report.observed_at, now, payload
    metrics = report.metrics
    db.add(PlatformSample(sample_id=report.sample_id, host_id=report.host_id, observed_at=report.observed_at,
        digest=digest, cpu_percent=metrics.cpu_percent, memory_percent=metrics.memory_used_percent,
        storage_percent=max((row.used_percent for row in metrics.filesystems), default=None)))
    # Seven days of metric history; capped cleanup batches avoid long write transactions.
    expired = db.query(PlatformSample.sample_id).filter(PlatformSample.observed_at < now-timedelta(days=7)).limit(2000).subquery()
    db.query(PlatformSample).filter(PlatformSample.sample_id.in_(db.query(expired.c.sample_id))).delete(synchronize_session=False)
    db.commit()
    return {'outcome': 'recorded'}


@router.get('/hosts')
def hosts(db: Session = Depends(get_db)):
    return {'hosts': [{'host_id': host.host_id, 'received_at': host.received_at, 'report': host.payload,
                     'summary': summarize(host.payload, host.received_at, warning=settings.PLATFORM_WARNING_PERCENT,
                                          critical=settings.PLATFORM_CRITICAL_PERCENT)}
                     for host in db.query(PlatformHost).order_by(PlatformHost.host_id).limit(100)],
            'server_time': datetime.now(timezone.utc), 'retention_days': 7, 'agent_interval_seconds': 30}


@router.get('/hosts/{host_id}/history')
def history(host_id: str, hours: int = Query(24, ge=1, le=168), db: Session = Depends(get_db)):
    if db.get(PlatformHost, host_id) is None:
        raise HTTPException(404, 'Host not found')
    seconds = 60 if hours == 1 else 300 if hours <= 24 else 1800
    bucket = func.floor(func.extract('epoch', PlatformSample.observed_at) / seconds) * seconds
    rows = db.query(bucket.label('epoch'), func.avg(PlatformSample.cpu_percent), func.avg(PlatformSample.memory_percent),
                    func.max(PlatformSample.storage_percent), func.count()).filter(PlatformSample.host_id == host_id,
                    PlatformSample.observed_at >= datetime.now(timezone.utc)-timedelta(hours=hours)).group_by(bucket).order_by(bucket).limit(400).all()
    return {'bucket_seconds': seconds, 'points': [{'time': datetime.fromtimestamp(float(epoch), timezone.utc),
             'cpu_percent': cpu, 'memory_percent': memory, 'storage_percent': storage, 'samples': count}
             for epoch, cpu, memory, storage, count in rows]}
