"""Read-only integration status; no model calls or fabricated answers."""
from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.api.routers.documents import access
from app.models.documents import Document

router=APIRouter(prefix='/knowledge',tags=['Knowledge integration status'])


@router.get('/status')
def status(db: Session=Depends(get_db)):
    return {'rag_connected':False,'query_available':False,'generation_available':False,
            'approval_available':False,'indexed_sources':0,'approved_sources':0,
            'accessible_catalogue_documents':access(db.query(Document)).count(),
            'source_mode':'catalogue_metadata_only',
            'requirements':['Colleague RAG and completeness tools','Reviewed document approval and extraction pipeline',
                            'Permission-filtered retrieval and exact source citations','Evaluated answers and draft-review workflow']}
