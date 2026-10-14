from typing import Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import actor_context
from app.models.documents import Document, DocumentVersion
from app.models.provisioning import ServiceOrder
from app.models.crm import Service
from app.models.incidents import Incident
from app.services import document_storage as storage

router = APIRouter(prefix='/documents',tags=['Private documents'])
TYPES = {'customer_handover','installation_acceptance','installation_evidence','shift_handover','rca','work_order','daily_report','weekly_report','knowledge','source_workbook','other'}


def is_admin():
    return 'NOC.Admin' in actor_context.get()['roles']


def access(query):
    if is_admin():
        return query
    return query.filter(or_(Document.owner_id==actor_context.get()['id'],Document.visibility=='noc'))


def document(db,identifier,write=False):
    query = db.query(Document).filter_by(document_id=identifier)
    if write:
        query = query.with_for_update()
    record = access(query).populate_existing().first()
    if not record:
        raise HTTPException(404,'Document not found')
    if write and not is_admin() and record.owner_id!=actor_context.get()['id']:
        raise HTTPException(403,'Only the document owner or an administrator can add revisions')
    return record


def version_row(value):
    return {column.name:getattr(value,column.name) for column in value.__table__.columns if column.name!='storage_key'}


def document_row(record,latest=None):
    return {column.name:getattr(record,column.name) for column in record.__table__.columns} | {
        'latest_version':version_row(latest) if latest else None,
        'review_state':'Unreviewed source','rag_state':'Not indexed','scan_state':'Malware scan not integrated'}


@router.get('')
def catalogue(search: str = Query('',max_length=200), document_type: str | None = None,
              order_id: UUID | None = None, service_id: UUID | None = None, incident_id: UUID | None = None,
              offset: int = Query(0,ge=0), limit: int = Query(50,ge=1,le=100), db: Session = Depends(get_db)):
    query = access(db.query(Document))
    if search.strip():
        query = query.filter(Document.title.ilike('%'+search.strip()+'%'))
    for field,value in (('document_type',document_type),('order_id',order_id),('service_id',service_id),('incident_id',incident_id)):
        if value is not None:
            query = query.filter(getattr(Document,field)==value)
    total = query.count()
    records = query.order_by(Document.created_at.desc(),Document.document_id).offset(offset).limit(limit).all()
    ids = [value.document_id for value in records]
    versions = db.query(DocumentVersion).filter(DocumentVersion.document_id.in_(ids)).order_by(DocumentVersion.document_id,DocumentVersion.revision.desc()).distinct(DocumentVersion.document_id).all() if ids else []
    latest = {value.document_id:value for value in versions}
    return {'total':total,'items':[document_row(value,latest.get(value.document_id)) for value in records],'offset':offset,'limit':limit}


def add_version(db,record,upload,note):
    if not 3<=len(note.strip())<=2000:
        raise HTTPException(422,'Describe the source/change in 3–2000 characters')
    staged,filename,extension,size,digest = storage.stage(upload)
    try:
        latest = db.query(DocumentVersion).filter_by(document_id=record.document_id).order_by(DocumentVersion.revision.desc()).first()
        if latest and latest.sha256==digest:
            return latest,False
        identifier = uuid4()
        key = storage.publish(staged,record.document_id,identifier,extension)
        version = DocumentVersion(version_id=identifier,document_id=record.document_id,revision=(latest.revision+1 if latest else 1),
            storage_key=key,original_filename=filename,media_type=storage.MEDIA[extension],byte_size=size,sha256=digest,
            uploaded_by=actor_context.get()['id'],change_note=note.strip())
        db.add(version)
        # On an ambiguous commit error retain bytes for reconciliation rather
        # than deleting an object that may already have committed metadata.
        db.commit(); db.refresh(version)
        return version,True
    finally:
        staged.unlink(missing_ok=True)


@router.post('')
def upload_document(file: UploadFile = File(...), title: str = Form(...,min_length=1,max_length=200),
                    document_type: str = Form(...), note: str = Form(...), visibility: Literal['private','noc'] = Form('private'),
                    order_id: UUID | None = Form(None), service_id: UUID | None = Form(None), incident_id: UUID | None = Form(None),
                    db: Session = Depends(get_db)):
    if document_type not in TYPES or not title.strip():
        raise HTTPException(422,'Choose a document type and non-empty title')
    if visibility=='noc' and not is_admin():
        raise HTTPException(403,'Administrator approval is required to share a document with all NOC roles')
    order = db.get(ServiceOrder,order_id) if order_id else None
    if order_id and not order:
        raise HTTPException(422,'Linked order not found')
    if order and order.activated_service_id:
        if service_id and service_id!=order.activated_service_id:
            raise HTTPException(422,'Selected service does not belong to this activated order')
        service_id = order.activated_service_id
    service = db.get(Service,service_id) if service_id else None
    if service_id and not service:
        raise HTTPException(422,'Linked service not found')
    if incident_id and not db.get(Incident,incident_id):
        raise HTTPException(422,'Linked incident not found')
    record = Document(document_id=uuid4(),title=title.strip(),document_type=document_type,owner_id=actor_context.get()['id'],
        visibility=visibility,order_id=order_id,service_id=service_id,customer_id=service.customer_id if service else None,incident_id=incident_id)
    db.add(record); db.flush()
    version,_ = add_version(db,record,file,note)
    db.refresh(record)
    return document_row(record,version)


@router.get('/{identifier}')
def detail(identifier: UUID,db: Session = Depends(get_db)):
    record = document(db,identifier)
    versions = db.query(DocumentVersion).filter_by(document_id=identifier).order_by(DocumentVersion.revision.desc()).all()
    result = document_row(record,versions[0] if versions else None)
    result['versions'] = [version_row(value) for value in versions]
    return result


@router.post('/{identifier}/versions')
def revision(identifier: UUID,file: UploadFile = File(...),note: str = Form(...),db: Session = Depends(get_db)):
    record = document(db,identifier,write=True)
    version,created = add_version(db,record,file,note)
    return {'outcome':'created' if created else 'already_current','version':version_row(version)}


class Sharing(BaseModel):
    visibility: Literal['private','noc']


@router.patch('/{identifier}/sharing')
def sharing(identifier: UUID,data: Sharing,db: Session = Depends(get_db)):
    if not is_admin():
        raise HTTPException(403,'Administrator role required to change document sharing')
    record = document(db,identifier,write=True)
    record.visibility = data.visibility
    db.commit(); db.refresh(record)
    return document_row(record)


@router.get('/{identifier}/versions/{version_id}/download')
def download(identifier: UUID,version_id: UUID,db: Session = Depends(get_db)):
    document(db,identifier)
    version = db.query(DocumentVersion).filter_by(document_id=identifier,version_id=version_id).first()
    if not version:
        raise HTTPException(404,'Document version not found')
    return FileResponse(storage.verified_path(version),media_type='application/octet-stream',filename=version.original_filename,
        headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'},content_disposition_type='attachment')
