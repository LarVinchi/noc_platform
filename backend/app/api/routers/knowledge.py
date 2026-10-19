"""Opt-in, version-approved knowledge workflow; NOC owns user authorization."""
import datetime as dt
from uuid import UUID, uuid4
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import actor_context
from app.core.config import settings
from app.api.routers.documents import access, document, is_admin
from app.models.documents import Document, DocumentVersion
from app.models.knowledge import KnowledgeApproval, KnowledgeEvent
from app.services import knowledge_client as worker, document_storage as storage

router = APIRouter(prefix='/knowledge', tags=['Approved knowledge'])


def identity(version):
    return {'document_id': str(version.document_id), 'version_id': str(version.version_id), 'sha256': version.sha256}


def catalogue(db):
    latest = db.query(DocumentVersion.document_id, func.max(DocumentVersion.revision).label('revision')).group_by(DocumentVersion.document_id).subquery()
    return access(db.query(Document, DocumentVersion, KnowledgeApproval).join(DocumentVersion,
        DocumentVersion.document_id == Document.document_id).join(latest,
        (latest.c.document_id == Document.document_id) & (latest.c.revision == DocumentVersion.revision))
        .outerjoin(KnowledgeApproval, KnowledgeApproval.version_id == DocumentVersion.version_id))


def allowed(db, ids):
    return [identity(v) for _,v,a in catalogue(db).filter(Document.document_id.in_(ids)).all() if a and a.approved]


def audit(db, kind, sources, note=None, request_id=None, model=None, index_version=None):
    if note is not None:
        sources = [{**source, 'review_note': note} for source in sources]
    if model or index_version:
        sources = [{**source, 'model': model, 'index_version': index_version} for source in sources]
    db.add(KnowledgeEvent(event_id=request_id or uuid4(), actor_id=actor_context.get()['id'], kind=kind,
        source_versions=sources, occurred_at=dt.datetime.now(dt.timezone.utc)))


@router.get('/status')
def status(db: Session = Depends(get_db)):
    connected = False
    if worker.configured():
        try:
            connected = worker.request('/health/ready').get('adapters_configured') is True
        except Exception:
            pass
    rows = catalogue(db).all()
    approved = sum(bool(a and a.approved) for _,_,a in rows)
    return {'rag_connected': connected, 'query_available': connected and approved > 0,
        'generation_available': connected, 'approval_available': worker.configured() and is_admin(),
        'draft_generation_available': False, 'case_query_available': False,
        'indexed_sources': approved, 'approved_sources': approved,
        'accessible_catalogue_documents': access(db.query(Document)).count(),
        'source_mode': 'approved_txt_lexical_v1' if settings.KNOWLEDGE_ENABLED else 'catalogue_metadata_only',
        'provider_probed': False, 'requirements': ['Approved UTF-8 TXT source', 'Configured private Gemini worker',
            'Live citation and answer-quality evaluation before operational use']}


@router.get('/sources')
def sources(db: Session = Depends(get_db)):
    rows = catalogue(db).order_by(Document.created_at.desc()).limit(100).all()
    return {'items': [{'document_id': d.document_id, 'title': d.title, 'version': identity(v),
        'revision': v.revision, 'filename': v.original_filename,
        'supported': v.media_type == 'text/plain' and v.byte_size <= 200000,
        'approved': bool(a and a.approved), 'reviewed_by': a.reviewed_by if a else None,
        'reviewed_at': a.reviewed_at if a else None} for d,v,a in rows], 'limit': 100}


class Review(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['approve','revoke']
    note: str = Field(min_length=5,max_length=2000)


@router.post('/versions/{version_id}/review')
def review(version_id: UUID, data: Review, db: Session = Depends(get_db)):
    if not is_admin():
        raise HTTPException(403, 'Administrator role required to review knowledge sources')
    if not worker.configured():
        raise HTTPException(503, 'Knowledge integration is not enabled and configured')
    if len(data.note.strip()) < 5:
        raise HTTPException(422, 'Describe the approval or revocation reason')
    version = db.get(DocumentVersion, version_id)
    if not version:
        raise HTTPException(404, 'Document version not found')
    document(db, version.document_id, write=True)
    latest = db.query(DocumentVersion).filter_by(document_id=version.document_id).order_by(DocumentVersion.revision.desc()).first()
    if data.action == 'approve' and latest.version_id != version_id:
        raise HTTPException(409, 'Only the latest document revision can be approved')
    row = db.get(KnowledgeApproval, version_id)
    if not row:
        row = KnowledgeApproval(version_id=version_id)
        db.add(row)
    row.approved = False
    row.reviewed_by = actor_context.get()['id']
    row.reviewed_at = dt.datetime.now(dt.timezone.utc)
    row.note = data.note.strip()
    source = identity(version)
    if data.action == 'revoke':
        # Persist deny first. Failure to notify the worker cannot restore access.
        audit(db, 'source_revoked', [source], row.note)
        db.commit()
        try:
            worker.request('/v1/sources/revoke', source)
        except Exception:
            return {'approved': False, 'worker_notified': False}
        return {'approved': False, 'worker_notified': True}
    if version.media_type != 'text/plain' or version.byte_size > 200000:
        raise HTTPException(422, 'This first workflow supports UTF-8 TXT sources up to 200 KB')
    try:
        content = storage.verified_path(version).read_bytes().decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(422, 'The source must contain valid UTF-8 text') from None
    if any(len(line) > 2800 for line in content.splitlines()):
        raise HTTPException(422, 'Wrap source lines to at most 2800 characters before approving')
    try:
        indexed = worker.request('/v1/sources/index', {'source': source, 'content': content})
        if indexed.get('indexed') is not True or indexed.get('source') != source:
            raise ValueError('Index identity mismatch')
    except Exception:
        db.rollback()
        raise HTTPException(503, 'Source indexing failed; approval was not published') from None
    row.approved = True
    audit(db, 'source_approved', [source], row.note)
    db.commit()
    return {'approved': True, 'indexed': True}


class Question(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=3,max_length=4000)
    document_ids: list[UUID] = Field(min_length=1,max_length=10)


@router.post('/query')
def query(data: Question, db: Session = Depends(get_db)):
    if not worker.configured():
        raise HTTPException(503, 'Knowledge integration is not enabled and configured')
    if len(data.question.strip()) < 3:
        raise HTTPException(422, 'Enter a question')
    scope = allowed(db, data.document_ids)
    if len(scope) != len(set(data.document_ids)):
        raise HTTPException(403, 'Select only accessible, approved current source versions')
    request_id = uuid4()
    try:
        answer = worker.validate_answer(worker.request('/v1/query', {'request_id': str(request_id),
            'question': data.question.strip(), 'allowed_versions': scope}), request_id, scope)
    except Exception:
        audit(db, 'query_unavailable', scope,request_id=request_id)
        db.commit()
        raise HTTPException(503, 'Knowledge service unavailable or returned invalid evidence; no answer released') from None
    # Access, latest revision and approval may change while the provider is running.
    db.expire_all()
    current = allowed(db, data.document_ids)
    if {tuple(s.values()) for s in current} != {tuple(s.values()) for s in scope}:
        audit(db, 'query_scope_changed', scope,request_id=request_id)
        db.commit()
        raise HTTPException(409, 'Source access or approval changed; ask again with current approved sources')
    audit(db, 'query_'+answer.status, scope,request_id=request_id,model=answer.model,index_version=answer.index_version)
    db.commit()
    return answer.model_dump(mode='json')
