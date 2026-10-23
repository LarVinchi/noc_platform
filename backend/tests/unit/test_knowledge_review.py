import io
import json
import os
os.environ.setdefault('POSTGRES_PASSWORD','unit-test-unused')
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
import pytest
from app.api.routers import knowledge_review as review


@pytest.fixture
def client(monkeypatch):
    for name,value in {'KNOWLEDGE_REVIEW_ENABLED':True,'ENVIRONMENT':'development','AUTH_MODE':'preview',
        'KNOWLEDGE_REVIEW_URL':'http://private-worker:8000','KNOWLEDGE_REVIEW_TOKEN':SecretStr('x'*40)}.items():
        monkeypatch.setattr(review.settings,name,value)
    token=review.actor_context.set({'id':'test','roles':['NOC.Admin']})
    app=FastAPI();app.include_router(review.router)
    with TestClient(app) as client:yield client
    review.actor_context.reset(token)


def test_disabled_or_production_review_never_contacts_worker(client,monkeypatch):
    monkeypatch.setattr(review.settings,'ENVIRONMENT','production')
    assert client.get('/knowledge-review/status').json()['enabled'] is False
    assert client.get('/knowledge-review/incidents').status_code==404


def test_review_admin_boundary_and_validated_filters(client,monkeypatch):
    token=review.actor_context.set({'id':'viewer','roles':['NOC.Viewer']})
    assert client.get('/knowledge-review/status').status_code==403
    review.actor_context.reset(token)
    paths=[]
    monkeypatch.setattr(review,'exchange',lambda path,payload=None:paths.append(path) or {'summary':{'provider_calls':0}})
    assert client.get('/knowledge-review/incidents?customer=MTN%26x%3D1').status_code==200
    assert paths[-1].startswith('/v1/incidents?customer=MTN%26x%3D1&')
    assert client.get('/knowledge-review/incidents?offset=-1').status_code==422
    assert client.get('/knowledge-review/sources/not-a-uuid').status_code==422
    assert client.post('/knowledge-review/query',json={'question':'Test','source_ids':['invalid']}).status_code==422


def test_worker_client_keeps_secrets_in_header_and_bounds_response(client,monkeypatch):
    class Opener:
        def open(self,request,timeout):
            assert request.get_header('Authorization')=='Bearer '+'x'*40
            assert 'x'*40 not in request.full_url
            return io.BytesIO(json.dumps({'enabled':True}).encode())
    monkeypatch.setattr(review.urllib.request,'build_opener',lambda *args:Opener())
    assert client.get('/knowledge-review/status').json()=={'enabled':True}
    class Bad:
        def open(self,*args,**kwargs):raise RuntimeError('PRIVATE_BODY_AND_SECRET')
    monkeypatch.setattr(review.urllib.request,'build_opener',lambda *args:Bad())
    response=client.get('/knowledge-review/status')
    assert response.status_code==503 and 'PRIVATE_BODY' not in response.text
