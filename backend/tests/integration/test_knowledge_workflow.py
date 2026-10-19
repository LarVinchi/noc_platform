"""Real NOC routes/access with an isolated SQLite catalogue; no PostgreSQL connection."""
import os
os.environ.setdefault('POSTGRES_PASSWORD','unit-test-unused')
import datetime as dt
import hashlib
import copy
from uuid import UUID, uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from app.api.routers import documents, knowledge
from app.core import db as database, security
from app.core.config import settings
from app.models.documents import Document, DocumentVersion
from app.models.knowledge import KnowledgeApproval, KnowledgeEvent
from app.services import knowledge_client as worker


@compiles(JSONB,'sqlite')
def sqlite_json(type_, compiler, **kw):
    return 'JSON'


@pytest.fixture
def api(tmp_path,monkeypatch):
    engine = create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    @event.listens_for(engine,'connect')
    def now(connection,_):
        connection.create_function('now',0,lambda:dt.datetime.now(dt.timezone.utc).isoformat())
    tables = [Document.__table__,DocumentVersion.__table__,KnowledgeApproval.__table__,KnowledgeEvent.__table__]
    database.Base.metadata.create_all(engine,tables=tables)
    # Production audit context is set_config(), a PostgreSQL-only SQL function.
    event.remove(Session,'before_flush',database.set_audit_actor)
    session = Session(engine)
    monkeypatch.setattr(settings,'DOCUMENT_STORAGE_ROOT',str(tmp_path/'documents'))
    monkeypatch.setattr(worker,'configured',lambda:True)
    actor = {'id':'admin-test','roles':['NOC.Admin'],'verified':True}
    monkeypatch.setattr(security,'auth_configuration',lambda:{'mode':'entra','configured':True})
    monkeypatch.setattr(security,'validate_token',lambda token:actor.copy())
    index, calls = {}, []
    def request(path,payload=None):
        calls.append((path,payload))
        if path == '/health/ready': return {'adapters_configured':True}
        if path == '/v1/sources/index':
            assert hashlib.sha256(payload['content'].encode()).hexdigest() == payload['source']['sha256']
            index[payload['source']['version_id']] = payload
            return {'indexed':True,'source':payload['source']}
        if path == '/v1/sources/revoke':
            index.pop(payload['version_id'],None)
            return {'revoked':True}
        source = copy.deepcopy(payload['allowed_versions'][0])
        return {'request_id':payload['request_id'],'status':'answered','answer':'Notify the shift lead.',
            'citations':[{'chunk_id':'test-chunk','source':source,'locator':'Lines 1-2',
                          'excerpt':index[source['version_id']]['content'][:600]}]}
    monkeypatch.setattr(worker,'request',request)
    app = FastAPI(); app.include_router(documents.router,prefix='/api'); app.include_router(knowledge.router,prefix='/api')
    app.add_middleware(security.AccessMiddleware)
    def db():
        try: yield session
        finally: session.rollback()
    app.dependency_overrides[database.get_db] = db
    try:
        with TestClient(app,headers={'Authorization':'Bearer test'}) as client:
            yield client,actor,calls,session
    finally:
        session.close(); engine.dispose()
        event.listen(Session,'before_flush',database.set_audit_actor)


def upload(client):
    response = client.post('/api/documents',data={'title':'Test runbook','document_type':'knowledge','note':'Synthetic initial revision'},
        files={'file':('runbook.txt',b'Escalate an unresolved incident to the shift lead.\n','text/plain')})
    assert response.status_code == 200,response.text
    return response.json()


def approve(client,record):
    return client.post('/api/knowledge/versions/'+record['latest_version']['version_id']+'/review',
        json={'action':'approve','note':'Reviewed this synthetic procedure for the isolated test'})


def test_approved_workflow_exact_revision_and_revoke(api):
    client,actor,calls,db = api
    record = upload(client); q = {'question':'Who receives an unresolved incident?','document_ids':[record['document_id']]}
    assert client.post('/api/knowledge/query',json=q).status_code == 403
    assert approve(client,record).status_code == 200
    assert client.get('/api/knowledge/sources').json()['items'][0]['approved'] is True
    result = client.post('/api/knowledge/query',json=q)
    assert result.status_code == 200,result.text
    citation = result.json()['citations'][0]
    assert citation['source']['sha256'] == record['latest_version']['sha256']
    assert client.get(f"/api/documents/{record['document_id']}/versions/{citation['source']['version_id']}/download").status_code == 200
    revoke = client.post('/api/knowledge/versions/'+record['latest_version']['version_id']+'/review',json={'action':'revoke','note':'Withdraw this test approval'})
    assert revoke.status_code == 200
    assert client.post('/api/knowledge/query',json=q).status_code == 403
    assert db.query(KnowledgeEvent).count() >= 3


def test_private_shared_and_new_revision_require_current_approval(api):
    client,actor,_,_ = api
    record = upload(client); assert approve(client,record).status_code == 200
    q = {'question':'Who receives an unresolved incident?','document_ids':[record['document_id']]}
    actor.update(id='viewer-test',roles=['NOC.Viewer'])
    assert client.get('/api/knowledge/sources').json()['items'] == []
    assert client.post('/api/knowledge/query',json=q).status_code == 403
    assert approve(client,record).status_code == 403
    actor['roles'] = ['NOC.Admin']
    assert client.patch('/api/documents/'+record['document_id']+'/sharing',json={'visibility':'noc'}).status_code == 200
    actor['roles'] = ['NOC.Viewer']
    assert client.post('/api/knowledge/query',json=q).status_code == 200
    actor['roles'] = ['NOC.Admin']
    result = client.post('/api/documents/'+record['document_id']+'/versions',data={'note':'New unreviewed revision'},files={'file':('runbook.txt',b'Updated procedure for the test.')})
    assert result.status_code == 200
    assert client.get('/api/documents').json()['items'][0]['latest_version']['revision'] == 2
    assert client.post('/api/knowledge/query',json=q).status_code == 403
    assert approve(client,record).status_code == 409


def test_invalid_worker_citation_is_never_released(api,monkeypatch):
    client,_,_,_ = api
    record = upload(client); assert approve(client,record).status_code == 200
    original = worker.request
    def forged(path,payload=None):
        value = original(path,payload)
        if path == '/v1/query': value['citations'][0]['source']['version_id'] = str(uuid4())
        return value
    monkeypatch.setattr(worker,'request',forged)
    response = client.post('/api/knowledge/query',json={'question':'What happens?','document_ids':[record['document_id']]})
    assert response.status_code == 503 and 'citations' not in response.json()


def test_sharing_revoked_while_provider_runs_discards_answer(api,monkeypatch):
    client,actor,_,db = api
    record = upload(client); assert approve(client,record).status_code == 200
    client.patch('/api/documents/'+record['document_id']+'/sharing',json={'visibility':'noc'})
    actor.update(id='viewer-test',roles=['NOC.Viewer'])
    original = worker.request
    def revoke_during_query(path,payload=None):
        value = original(path,payload)
        if path == '/v1/query':
            db.query(Document).filter_by(document_id=UUID(record['document_id'])).update({'visibility':'private'})
            db.commit()
        return value
    monkeypatch.setattr(worker,'request',revoke_during_query)
    response = client.post('/api/knowledge/query',json={'question':'What happens?','document_ids':[record['document_id']]})
    assert response.status_code == 409,response.text


def test_revoke_persists_even_if_worker_unavailable(api,monkeypatch):
    client,_,_,_ = api
    record = upload(client); assert approve(client,record).status_code == 200
    def unavailable(*args,**kwargs):
        raise RuntimeError('Simulated offline worker')
    monkeypatch.setattr(worker,'request',unavailable)
    response = client.post('/api/knowledge/versions/'+record['latest_version']['version_id']+'/review',json={'action':'revoke','note':'Withdraw approval while the worker is unavailable'})
    assert response.status_code == 200 and response.json()['worker_notified'] is False
    assert client.post('/api/knowledge/query',json={'question':'What happens?','document_ids':[record['document_id']]}).status_code == 403


def test_disabled_integration_never_contacts_worker(api,monkeypatch):
    client,_,calls,_ = api
    record = upload(client)
    monkeypatch.setattr(worker,'configured',lambda:False)
    assert approve(client,record).status_code == 503
    assert client.post('/api/knowledge/query',json={'question':'What happens?','document_ids':[record['document_id']]}).status_code == 503
    assert calls == []
