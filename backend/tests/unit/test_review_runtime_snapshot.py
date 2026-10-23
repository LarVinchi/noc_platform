import hashlib
import json
from pathlib import Path
from fastapi.testclient import TestClient
from app.review_rag.noc_service.review_runtime import create_review_app


def test_runtime_snapshot_hashes_match_and_exclude_private_inputs():
    root=Path(__file__).resolve().parents[2]/'app/review_rag'
    manifest=json.loads((root/'UPSTREAM.json').read_text())
    assert len(manifest['files'])==14
    for name,digest in manifest['files'].items():
        assert name.endswith('.py') and not name.startswith(('/','.'))
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest
    assert not (root/'preview_web').exists()
    assert not (root/'.env.noc.local').exists()


def test_packaged_review_worker_serves_inventory_without_provider_or_embeddings(tmp_path):
    source=tmp_path/'input';(source/'extractions').mkdir(parents=True)
    text='Synthetic extraction fixture. '*10+'\nTable 3; first row context: C1=Label | C2=Value\nRow 1: C1=Customer Name | C2=MTNN\nRow 2: C1=Root Cause Analysis | C2=Synthetic cable cut.\n'
    data={'original_sha256':'a'*64,'original_size':123,'status':'extracted_for_review','review_flags':[],
          'chunks':[{'locator':'Table 3, rows 1-2','text':text}]}
    (source/'extractions/one.json').write_text(json.dumps(data))
    item={'path':'synthetic.docx','sha256':'a'*64,'bytes':123,'status':'extracted_for_review','review_flags':[],
          'chunks':1,'extraction_file':'extractions/one.json','transfer_hash_matches':True}
    (source/'assessment.json').write_text(json.dumps({'summary':{},'items':[item]}))
    app=create_review_app(source,tmp_path/'state',token='t'*40)
    with TestClient(app,headers={'Authorization':'Bearer '+'t'*40}) as client:
        status=client.get('/v1/status').json()
        assert status['indexed_sources']==1 and not status['generation_available']
        result=client.get('/v1/incidents?customer=MTN').json()
        assert result['summary']['matching_reports']==1 and result['summary']['provider_calls']==0
        assert result['items'][0]['causes'][0]['text']=='Synthetic cable cut.'
