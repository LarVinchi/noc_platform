"""Vendor an explicit, hashed runtime snapshot from the separately reviewed RAG repo."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

FILES=[*[f'noc_service/{name}.py' for name in ('__init__','contracts','corpus_preview','derived','embeddings',
    'engine','extraction','gemini','incident_inventory','loaders','review_runtime','snapshot','store','vector_store')]]


def sync(source,target):
    source=source.resolve(strict=True)
    target.mkdir(parents=True,exist_ok=True)
    (target/'__init__.py').write_text('"""Pinned runtime snapshot; see UPSTREAM.json."""\n')
    hashes={}
    for name in FILES:
        path=source/name
        if path.is_symlink() or not path.is_file():raise ValueError('Missing regular runtime source: '+name)
        data=path.read_text(encoding='utf-8').encode('utf-8')  # Stable LF bytes on Windows/Linux.
        destination=target/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(data)
        hashes[name]=hashlib.sha256(data).hexdigest()
    commit=subprocess.check_output(['git','-c','safe.directory='+source.as_posix(),'-C',str(source),'rev-parse','HEAD'],text=True).strip()
    manifest={'repository':'https://github.com/Sydneychioma/RAG-SYSTEM','upstream_commit':commit,
              'snapshot_sha256':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),'files':hashes,
              'scope':'Runtime code only. No documents, keys, indexes, preview UI or provider calls.'}
    (target/'UPSTREAM.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    args=parser.parse_args()
    target=Path(__file__).resolve().parents[1]/'backend/app/review_rag'
    result=sync(args.source,target)
    print('Runtime snapshot:',result['snapshot_sha256'],'files:',len(FILES))
