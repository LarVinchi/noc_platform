from test_ftth_intake_api import api,pytestmark  # noqa: F401


def test_status_reports_pending_engine_and_respects_private_catalogue(api,monkeypatch,tmp_path):
    client,_=api
    from app.core.config import settings
    monkeypatch.setattr(settings,'DOCUMENT_STORAGE_ROOT',str(tmp_path/'knowledge-documents'))
    before=client.get('/api/knowledge/status').json()['accessible_catalogue_documents']
    uploaded=client.post('/api/documents',data={'title':'Knowledge privacy test','document_type':'knowledge','note':'Private source test'},files={'file':('source.txt',b'Knowledge evidence source')})
    assert uploaded.status_code==200,uploaded.text
    state=client.get('/api/knowledge/status').json()
    assert not state['rag_connected'] and not state['query_available'] and not state['generation_available']
    assert state['approved_sources']==state['indexed_sources']==0
    assert state['accessible_catalogue_documents']==before+1
    from app.core import security
    monkeypatch.setattr(security,'auth_configuration',lambda:{'configured':True,'mode':'entra'})
    monkeypatch.setattr(security,'validate_token',lambda token:{'id':'knowledge-viewer','verified':True,'roles':['NOC.Viewer']})
    headers={'authorization':'Bearer test'}
    from app.models.documents import Document
    _,db=api
    expected=db.query(Document).filter(Document.visibility=='noc').count()
    assert client.get('/api/knowledge/status',headers=headers).json()['accessible_catalogue_documents']==expected
    assert client.post('/api/knowledge/query',headers=headers,json={'question':'Access private knowledge','document_ids':[uploaded.json()['document_id']]}).status_code==503
