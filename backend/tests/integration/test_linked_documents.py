"""Real intake/auth/knowledge routes; originals never enter document storage."""
import copy
import datetime as dt
import hashlib
from uuid import UUID, uuid4
import pytest
from pydantic import SecretStr
from tests.integration.test_knowledge_workflow import api  # noqa: F401
from app.models.documents import DocumentVersion
from app.models.linked_documents import LinkedCollection, LinkedRevision
from app.core.config import settings
from app.core import security
from fastapi import HTTPException
from app.services.linked_documents import digest


def collection(client,**kw):
    response=client.post('/api/document-intake/collections',json={'title':'Approved synthetic collection',**kw})
    assert response.status_code==200,response.text
    return response.json()['collection_id']


def report(identifier,text='Notify the shift lead after 15 minutes.',**kw):
    chunks=[{'locator':'Lines 1-1','text':text}]
    return {'collection_id':identifier,'run_id':str(uuid4()),'observed_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'complete':True,'items':[{'path':'Runbooks/test.txt','sha256':hashlib.sha256((text+'\n').encode()).hexdigest(),
        'size':len(text.encode())+1,'status':'extracted','chunks':chunks,'extraction_sha256':digest(chunks)}],**kw}


def import_report(client,value):
    response=client.post('/api/document-intake/import',json=value)
    assert response.status_code==200,response.text
    return response.json()


def source(client):
    return client.get('/api/knowledge/sources').json()['items'][0]


def approve(client,item):
    return client.post('/api/knowledge/versions/'+item['version']['version_id']+'/review',
        json={'action':'approve','note':'Reviewed original locally and verified extracted synthetic text'})


def test_linked_intake_review_query_provenance_without_originals(api,tmp_path):
    client,actor,calls,db=api
    value=report(collection(client))
    assert import_report(client,value)['created_revisions']==1
    assert import_report(client,value)['replayed']
    item=source(client)
    assert item['origin_kind']=='onedrive_link' and not item['approved'] and item['eligible']
    assert approve(client,item).status_code==200
    result=client.post('/api/knowledge/query',json={'question':'Who receives the incident?','document_ids':[item['document_id']]})
    assert result.status_code==200,result.text
    assert result.json()['citations'][0]['source']['sha256']==value['items'][0]['sha256']
    origin=f"/api/documents/{item['document_id']}/versions/{item['version']['version_id']}"
    assert client.get(origin+'/download').status_code==409
    assert client.get(origin+'/origin').json()['exact_original_available'] is False
    assert not list((tmp_path/'documents').rglob('*'))
    assert any(path=='/v1/sources/extracted' for path,_ in calls)


def test_new_revision_and_changed_extraction_require_new_approval(api):
    client,actor,calls,db=api
    identifier=collection(client); value=report(identifier)
    import_report(client,value); old=source(client); assert approve(client,old).status_code==200
    new=report(identifier,'Notify a different fictional team.')
    # Even if original attested hash is unchanged, changed extraction gets a new immutable version.
    new['items'][0]['sha256']=value['items'][0]['sha256']
    import_report(client,new); current=source(client)
    assert current['revision']==2 and not current['approved']
    assert current['version']['version_id']!=old['version']['version_id']
    assert client.post('/api/knowledge/query',json={'question':'Who?','document_ids':[current['document_id']]}).status_code==403


def test_partial_scan_retains_absent_sources_complete_scan_blocks_them(api):
    client,actor,calls,db=api
    identifier=collection(client); import_report(client,report(identifier)); item=source(client)
    assert approve(client,item).status_code==200
    import_report(client,report(identifier,items=[],complete=False))
    assert source(client)['eligible']
    import_report(client,report(identifier,items=[],complete=True))
    assert not source(client)['eligible']
    assert client.post('/api/knowledge/query',json={'question':'Who?','document_ids':[item['document_id']]}).status_code==403


def test_stale_observation_pause_and_no_replay_heartbeat(api):
    client,actor,calls,db=api
    identifier=collection(client,freshness_seconds=300)
    value=report(identifier,observed_at=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(hours=1)).isoformat())
    import_report(client,value)
    assert not source(client)['eligible']
    assert approve(client,source(client)).status_code==409
    import_report(client,value)
    assert not source(client)['eligible']
    import_report(client,report(identifier)); assert source(client)['eligible']
    assert client.patch('/api/document-intake/collections/'+identifier,json={'enabled':False}).status_code==200
    assert not source(client)['eligible']


def test_access_scope_and_duplicate_origins_stay_separate(api):
    client,actor,calls,db=api
    value=report(collection(client)); copy_item=copy.deepcopy(value['items'][0]); copy_item['path']='Other/test.txt'
    value['items'].append(copy_item); import_report(client,value)
    items=client.get('/api/document-intake').json()['items']
    assert len(items)==2 and all(i['duplicate_content'] for i in items)
    assert len({i['document_id'] for i in items})==2
    actor.update(id='viewer-test',roles=['NOC.Viewer'])
    assert client.get('/api/document-intake').status_code==403
    assert client.get('/api/knowledge/sources').json()['items']==[]
    assert client.post('/api/document-intake/import',json=value).status_code==403


def test_collection_quota_rolls_back_whole_report(api):
    client,actor,calls,db=api
    identifier=collection(client,derived_limit_bytes=100000)
    value=report(identifier)
    value['items']*=1
    # Legal per-source chunks, but exceed the collection quota on the second source.
    for n in range(2):
        item=copy.deepcopy(value['items'][0]); item['path']=f'large-{n}.txt'
        item['chunks']=[{'locator':f'Lines {i+1}-{i+1}','text':'x'*2500} for i in range(25)]
        item['extraction_sha256']=digest(item['chunks']); value['items'].append(item)
    result=client.post('/api/document-intake/import',json=value)
    assert result.status_code==413
    assert db.query(DocumentVersion).count()==0


@pytest.mark.parametrize('change',[lambda v:v['items'][0].update(path='../escape.txt'),
    lambda v:v['items'][0].update(extraction_sha256='0'*64),
    lambda v:v['items'][0].update(original_url='https://untrusted.example/file'),
    lambda v:v.update(original_bytes='not permitted')])
def test_reject_invalid_paths_tampered_content_and_original_blobs(api,change):
    client,actor,calls,db=api
    value=report(collection(client)); change(value)
    assert client.post('/api/document-intake/import',json=value).status_code==422
    assert db.query(DocumentVersion).count()==0


def test_collector_token_bound_to_one_collection_and_only_ingest(api,monkeypatch):
    client,actor,calls,db=api
    identifier=collection(client); other=collection(client)
    monkeypatch.setattr(settings,'LINKED_COLLECTOR_COLLECTION_ID',identifier)
    monkeypatch.setattr(settings,'LINKED_COLLECTOR_TOKEN',SecretStr('collector-test-token-'+'x'*32))
    assert client.post('/api/document-intake/ingest',json=report(identifier)).status_code==401
    headers={'Authorization':'Bearer '+settings.LINKED_COLLECTOR_TOKEN.get_secret_value()}
    def user_token(token):
        if token==settings.LINKED_COLLECTOR_TOKEN.get_secret_value(): raise HTTPException(401,'Not a user token')
        return actor.copy()
    monkeypatch.setattr(security,'validate_token',user_token)
    assert client.post('/api/document-intake/ingest',json=report(other),headers=headers).status_code==403
    assert client.post('/api/document-intake/ingest',json=report(identifier),headers=headers).status_code==200
    duplicate=[('Authorization',headers['Authorization']),('Authorization',headers['Authorization'])]
    assert client.post('/api/document-intake/ingest',json=report(identifier),headers=duplicate).status_code==401
    assert client.get('/api/document-intake',headers=headers).status_code==401
    assert client.post('/api/knowledge/query',json={'question':'Who?','document_ids':[str(uuid4())]},headers=headers).status_code==401


def test_reject_out_of_order_reports_and_changed_replay(api):
    client,actor,calls,db=api
    identifier=collection(client); value=report(identifier); import_report(client,value)
    old=report(identifier,observed_at=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(minutes=1)).isoformat())
    assert client.post('/api/document-intake/import',json=old).status_code==409
    value['complete']=False
    assert client.post('/api/document-intake/import',json=value).status_code==409
