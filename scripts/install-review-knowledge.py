#!/usr/bin/env python3
"""Activate the accepted-text review worker from an already installed tested release."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import secrets
import subprocess


def private_write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    with temporary.open('w',encoding='utf-8') as stream:
        os.chmod(temporary,0o600)
        stream.write(text)
    temporary.replace(path)


def provider_settings(path):
    result={}
    if path is not None:
        if path.stat().st_size>65536:raise ValueError('Provider environment file exceeds limits')
        for line in path.read_text().splitlines():
            name,separator,value=line.partition('=')
            if separator and name.strip() in ('GEMINI_API_KEY','RAG_GEMINI_MODEL'):
                result[name.strip()]=value.strip().strip('"\'')
    key=result.get('GEMINI_API_KEY','')
    model=result.get('RAG_GEMINI_MODEL','gemini-3.5-flash-lite')
    if key and not re.fullmatch(r'[A-Za-z0-9_-]{10,300}',key):raise ValueError('Invalid private Gemini credential format')
    if not re.fullmatch(r'gemini-[a-z0-9.-]{1,80}',model):raise ValueError('Invalid generation model identifier')
    return key,model


def prepare(root,assessment,provider_env,image,uid,gid):
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',image):raise ValueError('Expected an installed immutable backend image ID')
    assessment=assessment.resolve(strict=True)
    if not (assessment/'assessment.json').is_file() or not (assessment/'extractions').is_dir():
        raise ValueError('Select the completed extraction directory, not the original documents')
    state=root/'.review-access/knowledge';state.mkdir(parents=True,exist_ok=True);state.chmod(0o700)
    if state.is_relative_to(assessment) or assessment.is_relative_to(state):raise ValueError('Keep index separate from input')
    index=state/'index';index.mkdir(exist_ok=True);index.chmod(0o700)
    token_file=state/'worker.token'
    if not token_file.exists():private_write(token_file,secrets.token_urlsafe(48))
    token=token_file.read_text().strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{32,512}',token):raise ValueError('Existing review token is invalid')
    key,model=provider_settings(provider_env)
    private_write(state/'worker.env',f'RAG_NOC_SERVICE_TOKEN={token}\nGEMINI_API_KEY={key}\nRAG_GEMINI_MODEL={model}\n')
    overlay={'services':{'api':{'environment':{'KNOWLEDGE_REVIEW_ENABLED':'true',
        'KNOWLEDGE_REVIEW_URL':'http://knowledge-review:8000','KNOWLEDGE_REVIEW_TOKEN':token}},
        'knowledge-review':{'image':image,'user':f'{uid}:{gid}','env_file':[str(state/'worker.env')],
            'volumes':[str(assessment)+':/assessment:ro',str(index)+':/state:rw']}}}
    private_write(state/'compose.json',json.dumps(overlay,indent=2)+'\n')
    return state


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--assessment',type=Path,required=True)
    parser.add_argument('--provider-env',type=Path)
    parser.add_argument('--activate',action='store_true')
    args=parser.parse_args()
    if platform.system()!='Linux' or os.geteuid()==0:raise SystemExit('Run as the Linux Docker Desktop owner, not root')
    os.umask(0o077)
    root=args.root.resolve()
    if root!=Path('/home/steve/Downloads/noc_platform'):raise SystemExit('This installer targets the existing steve review stack')
    current=json.loads((root/'.review-access/cd/current.json').read_text())
    runtime=Path(current['runtime']).resolve(strict=True)
    if not runtime.is_relative_to(root/'.review-access/releases'):raise SystemExit('Invalid installed runtime path')
    if 'knowledge-review:' not in (runtime/'compose.review.yaml').read_text():raise SystemExit('Deploy the tested knowledge review release first')
    docker=['docker','--context','desktop-linux']
    image=subprocess.check_output(docker+['inspect','noc-review-api-1','--format','{{.Image}}'],text=True).strip()
    import fcntl
    with (root/'.review-access/cd/lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state=prepare(root,args.assessment,args.provider_env,image,os.getuid(),os.getgid())
        if not args.activate:
            print('Protected review configuration prepared. Re-run with --activate to start it.');return
        already_enabled=(state/'enabled').exists()
        spec=importlib.util.spec_from_file_location('release_controller',runtime/'scripts/deploy-review-release.py')
        controller=importlib.util.module_from_spec(spec);spec.loader.exec_module(controller)
        private_write(state/'enabled','Accepted extracted-text review enabled; production approval remains separate.\n')
        command=controller.compose(root,runtime)+['-f',str(runtime/'images.json')]
        try:
            subprocess.run(command+['up','-d','--no-build','--no-deps','--wait','--wait-timeout','240','knowledge-review','api'],check=True)
        except Exception:
            if not already_enabled:
                (state/'enabled').unlink()
                subprocess.run(controller.compose(root,runtime)+['-f',str(runtime/'images.json'),
                    'up','-d','--no-build','--no-deps','--wait','api'],check=False)
            raise
        # Future tested releases must update the optional worker with the same backend image.
        target=root/'.review-access/cd/deploy-review-release.py'
        private_write(target,(runtime/'scripts/deploy-review-release.py').read_text());target.chmod(0o700)
        print('Review knowledge worker activated. Open Knowledge > Review collection.')
        print('Inventory scans accepted text locally; questions use Gemini. No embedding ingestion was started.')
        print('Check: docker --context desktop-linux logs --tail 30 noc-review-knowledge-review-1')


if __name__=='__main__':main()
