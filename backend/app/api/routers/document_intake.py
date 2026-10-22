"""Bounded, authenticated import of metadata and extraction; never file originals."""
import datetime as dt
import hashlib
import json
from pathlib import PurePosixPath
from uuid import UUID, uuid4, uuid5
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.core.config import settings
from app.core.db import get_db
from app.core.security import actor_context
from app.models.documents import Document, DocumentVersion
from app.models.linked_documents import LinkedCollection, LinkedRevision, LinkedScan
from app.models.knowledge import KnowledgeEvent
from app.api.routers.documents import is_admin
from app.services.linked_documents import digest, utc, usable

router=APIRouter(prefix='/document-intake',tags=['Linked document intake'])


def admin():
    if not settings.LINKED_DOCUMENTS_ENABLED:
        raise HTTPException(503,'Linked document intake is disabled')
    if not is_admin(): raise HTTPException(403,'Administrator role required')


class Contract(BaseModel):
    model_config=ConfigDict(extra='forbid')


class CollectionInput(Contract):
    title:str=Field(min_length=3,max_length=200)
    freshness_seconds:int=Field(default=86400,ge=300,le=604800)
    derived_limit_bytes:int=Field(default=25000000,ge=100000,le=100000000)


@router.post('/collections')
def create_collection(data:CollectionInput,db:Session=Depends(get_db)):
    admin()
    if not data.title.strip(): raise HTTPException(422,'Collection title required')
    if db.query(LinkedCollection).count()>=100: raise HTTPException(409,'Collection limit reached')
    row=LinkedCollection(collection_id=uuid4(),owner_id=actor_context.get()['id'],enabled=True,**data.model_dump())
    db.add(row)
    db.add(KnowledgeEvent(event_id=uuid4(),actor_id=actor_context.get()['id'],kind='linked_collection_created',
        source_versions=[{'collection_id':str(row.collection_id)}],occurred_at=dt.datetime.now(dt.timezone.utc)))
    db.commit()
    return {'collection_id':row.collection_id,'title':row.title}


class CollectionState(Contract):
    enabled:bool


@router.patch('/collections/{collection_id}')
def collection_state(collection_id:UUID,data:CollectionState,db:Session=Depends(get_db)):
    admin()
    row=db.query(LinkedCollection).filter_by(collection_id=collection_id).with_for_update().first()
    if not row: raise HTTPException(404,'Collection not found')
    row.enabled=data.enabled
    db.add(KnowledgeEvent(event_id=uuid4(),actor_id=actor_context.get()['id'],kind='linked_collection_state',
        source_versions=[{'collection_id':str(collection_id),'enabled':data.enabled}],occurred_at=dt.datetime.now(dt.timezone.utc)))
    db.commit()
    return {'enabled':row.enabled}


class Evidence(Contract):
    locator:str=Field(min_length=1,max_length=300)
    text:str=Field(min_length=1,max_length=2800)


class Item(Contract):
    path:str=Field(min_length=1,max_length=1000)
    sha256:str|None=Field(default=None,pattern='^[0-9a-f]{64}$')
    size:int|None=Field(default=None,ge=0,le=100000000)
    status:str=Field(max_length=60)
    chunks:list[Evidence]=Field(default_factory=list,max_length=100)
    extraction_sha256:str=Field(pattern='^[0-9a-f]{64}$')
    original_url:str|None=Field(default=None,max_length=2000)

    @model_validator(mode='after')
    def valid(self):
        p=PurePosixPath(self.path)
        if p.is_absolute() or str(p)!=self.path or any(part in ('..','.') for part in p.parts) or '\\' in self.path or ':' in self.path or any(ord(c)<32 for c in self.path):
            raise ValueError('Invalid relative source path')
        if self.original_url:
            url=urlsplit(self.original_url)
            if url.scheme!='https' or url.username or url.password or url.port not in (None,443) or not url.hostname or url.hostname not in settings.LINKED_ONEDRIVE_ALLOWED_HOSTS or url.query or url.fragment:
                raise ValueError('Use an organization SharePoint web URL without sharing tokens')
        chunks=[c.model_dump() for c in self.chunks]
        if any(not c.text.strip() or c.text!=c.text.strip() or not c.locator.strip() or c.locator!=c.locator.strip() for c in self.chunks) or len({c.locator for c in self.chunks})!=len(self.chunks) or sum(len(c.text) for c in self.chunks)>200000 or digest(chunks)!=self.extraction_sha256:
            raise ValueError('Invalid extracted evidence')
        if self.chunks and (not self.sha256 or self.status!='extracted'):
            raise ValueError('Extracted evidence must identify its original')
        return self


class Report(Contract):
    collection_id:UUID
    run_id:UUID
    observed_at:dt.datetime
    complete:bool
    items:list[Item]=Field(max_length=1000)

    @model_validator(mode='after')
    def valid(self):
        if self.observed_at.tzinfo is None or utc(self.observed_at)>dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=5):
            raise ValueError('Invalid collector observation time')
        if len({i.path.casefold() for i in self.items})!=len(self.items):
            raise ValueError('Duplicate source paths')
        return self


async def parse(request):
    data=bytearray()
    async for block in request.stream():
        if len(data)+len(block)>5000000: raise HTTPException(413,'Intake report exceeds 5 MB')
        data.extend(block)
    try: return Report.model_validate_json(data),hashlib.sha256(data).hexdigest()
    except ValueError: raise HTTPException(422,'Invalid metadata/extraction report') from None


def ingest(report,payload_hash,db):
    collection=db.query(LinkedCollection).filter_by(collection_id=report.collection_id).with_for_update().first()
    if not collection or not collection.enabled: raise HTTPException(404,'Enabled collection not found')
    previous=db.get(LinkedScan,report.run_id)
    if previous:
        if previous.collection_id!=collection.collection_id or previous.payload_sha256!=payload_hash:
            raise HTTPException(409,'Scan identity already used for different content')
        return {**previous.summary,'replayed':True}
    observed=utc(report.observed_at)
    if collection.last_observed_at and observed<=utc(collection.last_observed_at):
        raise HTTPException(409,'A newer collector observation is already installed')
    used=db.query(func.coalesce(func.sum(LinkedRevision.derived_bytes),0)).filter_by(collection_id=collection.collection_id).scalar()
    revision_count=db.query(LinkedRevision).filter_by(collection_id=collection.collection_id).count()
    if db.query(LinkedScan).filter_by(collection_id=collection.collection_id).count()>=10000:
        raise HTTPException(409,'Scan-history limit reached; archive/reconcile before collecting more')
    created,unchanged,skipped,seen=0,0,0,set()
    for item in report.items:
        document_id=uuid5(collection.collection_id,item.path.casefold()); seen.add(document_id)
        record=db.get(Document,document_id)
        latest=db.query(DocumentVersion).filter_by(document_id=document_id).order_by(DocumentVersion.revision.desc()).first() if record else None
        previous_link=db.get(LinkedRevision,latest.version_id) if latest else None
        if not item.sha256 or item.size is None:
            if previous_link: previous_link.available=False
            skipped+=1; continue
        chunks=[c.model_dump() for c in item.chunks]
        available=item.status in ('extracted','metadata_only')
        if latest and latest.sha256==item.sha256 and previous_link.extraction_sha256==item.extraction_sha256:
            previous_link.observed_at=observed; previous_link.available=available; previous_link.original_url=item.original_url
            unchanged+=1; continue
        # Serialize the same document row as review/sharing to prevent approval races.
        if record:
            db.query(Document).filter_by(document_id=document_id).with_for_update().first()
        else:
            record=Document(document_id=document_id,title=PurePosixPath(item.path).name[:200],document_type='knowledge',
                owner_id=collection.owner_id,visibility='private')
            db.add(record); db.flush()
        if revision_count+created>=10000:
            db.rollback(); raise HTTPException(413,'Collection revision limit reached; no scan changes applied')
        size=len(json.dumps(chunks,ensure_ascii=False,separators=(',',':')).encode())
        if used+size>collection.derived_limit_bytes:
            db.rollback(); raise HTTPException(413,'Collection derived-content quota exceeded; no scan changes applied')
        used+=size; identifier=uuid4()
        version=DocumentVersion(version_id=identifier,document_id=document_id,revision=latest.revision+1 if latest else 1,
            storage_key='linked/'+str(identifier),original_filename=PurePosixPath(item.path).name[:240],media_type='application/x-noc-linked',
            byte_size=item.size,sha256=item.sha256,uploaded_by=actor_context.get()['id'],change_note='Collector observation; original retained in OneDrive')
        db.add(version); db.flush()
        db.add(LinkedRevision(version_id=identifier,collection_id=collection.collection_id,source_path=item.path,original_url=item.original_url,
            extraction_sha256=item.extraction_sha256,chunks=chunks,derived_bytes=size,observed_at=observed,available=available))
        db.flush(); created+=1
    if report.complete:
        for row,identifier in db.query(LinkedRevision,DocumentVersion.document_id).join(DocumentVersion,LinkedRevision.version_id==DocumentVersion.version_id).filter(LinkedRevision.collection_id==collection.collection_id):
            if identifier not in seen: row.available=False
    issues=[{'path':i.path,'status':i.status} for i in report.items if i.status!='extracted']
    summary={'created_revisions':created,'unchanged':unchanged,'skipped':skipped,'complete':report.complete,'derived_bytes':used,
        'issues':issues[:100],'issue_count':len(issues)}
    collection.last_observed_at=observed
    db.add(LinkedScan(run_id=report.run_id,collection_id=collection.collection_id,payload_sha256=payload_hash,observed_at=observed,summary=summary))
    db.add(KnowledgeEvent(event_id=uuid4(),actor_id=actor_context.get()['id'],kind='linked_scan_imported',
        source_versions=[{'collection_id':str(collection.collection_id),'run_id':str(report.run_id),
            **{key:summary[key] for key in ('created_revisions','unchanged','skipped','complete','derived_bytes','issue_count')}}],occurred_at=dt.datetime.now(dt.timezone.utc)))
    db.commit()
    return summary


@router.post('/import')
async def import_report(request:Request,db:Session=Depends(get_db)):
    admin(); report,digest_value=await parse(request)
    return await run_in_threadpool(ingest,report,digest_value,db)


@router.post('/ingest')
async def collector_report(request:Request,db:Session=Depends(get_db)):
    if 'LinkedCollector' not in actor_context.get()['roles']: raise HTTPException(403,'Collector credential required')
    report,digest_value=await parse(request)
    if str(report.collection_id)!=settings.LINKED_COLLECTOR_COLLECTION_ID: raise HTTPException(403,'Collection is outside collector scope')
    return await run_in_threadpool(ingest,report,digest_value,db)


@router.get('')
def intake(offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),db:Session=Depends(get_db)):
    admin()
    collections=db.query(LinkedCollection).order_by(LinkedCollection.title).all()
    items=[]
    latest=db.query(DocumentVersion.document_id,func.max(DocumentVersion.revision).label('revision')).group_by(DocumentVersion.document_id).subquery()
    query=db.query(Document,DocumentVersion,LinkedRevision).join(DocumentVersion,DocumentVersion.document_id==Document.document_id).join(latest,
        (latest.c.document_id==DocumentVersion.document_id)&(latest.c.revision==DocumentVersion.revision)).join(LinkedRevision,LinkedRevision.version_id==DocumentVersion.version_id)
    total=query.count()
    rows=query.order_by(Document.created_at.desc(),Document.document_id).offset(offset).limit(limit).all()
    for d,v,l in rows:
        items.append({'document_id':d.document_id,'version_id':v.version_id,'title':d.title,'revision':v.revision,'path':l.source_path,
            'collection_id':l.collection_id,'original_bytes':v.byte_size,'derived_bytes':l.derived_bytes,'fresh':usable(db,v),
            'sha256':v.sha256,'extraction_sha256':l.extraction_sha256,'chunk_count':len(l.chunks),'observed_at':l.observed_at,'visibility':d.visibility,
            'duplicate_content':db.query(DocumentVersion).filter(DocumentVersion.sha256==v.sha256,DocumentVersion.document_id!=d.document_id).first() is not None})
    return {'collections':[{'collection_id':c.collection_id,'title':c.title,'enabled':c.enabled,'last_observed_at':c.last_observed_at,
        'freshness_seconds':c.freshness_seconds,'derived_limit_bytes':c.derived_limit_bytes,
        'derived_bytes':db.query(func.coalesce(func.sum(LinkedRevision.derived_bytes),0)).filter_by(collection_id=c.collection_id).scalar(),
        'last_scan':(db.query(LinkedScan).filter_by(collection_id=c.collection_id).order_by(LinkedScan.observed_at.desc()).first().summary if c.last_observed_at else None)} for c in collections],
        'items':items,'limit':limit,'offset':offset,'total':total,'originals_stored':False}


@router.get('/versions/{version_id}/preview')
def preview(version_id:UUID,db:Session=Depends(get_db)):
    admin()
    row=db.get(LinkedRevision,version_id)
    if not row: raise HTTPException(404,'Linked revision not found')
    return {'chunks':row.chunks,'extraction_sha256':row.extraction_sha256,
        'notice':'Collector-extracted text; original bytes remain in OneDrive. Inspect the source on the collector PC before approval.'}
