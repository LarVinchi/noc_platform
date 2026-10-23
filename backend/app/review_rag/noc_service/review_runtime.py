"""Private review-only corpus worker; indexes accepted text locally, never embeds it."""
import hmac
import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from .corpus_preview import CorpusController
from .store import SourceStore


def create_review_app(assessment, state, *, token, key='', model='gemini-3.5-flash-lite', generator_factory=None):
    if not 32<=len(token)<=512 or not token.isascii() or any(c.isspace() for c in token):
        raise ValueError('Configure a private review worker token')
    controller=CorpusController(assessment,state,key=key,configured_model=model,
        store_factory=lambda directory:SourceStore(directory/'review.sqlite3'),generator_factory=generator_factory)
    # Accepted demo text only. This registry is isolated from NOC's approved-source registry.
    controller._index()
    if not controller.ready():
        raise RuntimeError('Accepted snapshot could not be indexed locally')
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    app.state.controller=controller

    async def authenticate(request:Request):
        values=request.headers.getlist('authorization')
        scheme,_,supplied=(values[0] if len(values)==1 else '').partition(' ')
        if scheme.lower()!='bearer' or not supplied.isascii() or not hmac.compare_digest(supplied,token):
            raise HTTPException(401,'Private review worker authentication required')

    @app.get('/health/live')
    def live():return {'live':True}

    @app.get('/v1/status',dependencies=[Depends(authenticate)])
    def status():
        value=controller.status()
        value.update(enabled=True,generation_available=bool(key or generator_factory),retrieval_backend='keyword',
                     inventory=controller.inventory.search('',0,1)['summary'])
        return value

    @app.get('/v1/sources',dependencies=[Depends(authenticate)])
    def sources():return {'sources':controller.sources()}

    @app.get('/v1/incidents',dependencies=[Depends(authenticate)])
    def incidents(customer:str='',offset:int=0,limit:int=25):
        try:return controller.inventory.search(customer,offset,limit)
        except ValueError:raise HTTPException(422,'Invalid inventory filter or page') from None

    @app.get('/v1/incidents/export',dependencies=[Depends(authenticate)])
    def export(customer:str=''):
        try:return controller.inventory.export(customer)
        except ValueError:raise HTTPException(422,'Invalid inventory filter') from None

    @app.get('/v1/sources/{identifier}',dependencies=[Depends(authenticate)])
    def source(identifier:str):
        try:return controller.inventory.source(identifier)
        except KeyError:raise HTTPException(404,'Source not in accepted snapshot') from None

    @app.post('/v1/query',dependencies=[Depends(authenticate)])
    async def query(request:Request):
        raw=bytearray()
        async for block in request.stream():
            raw.extend(block)
            if len(raw)>60000:raise HTTPException(413,'Question exceeds limits')
        try:
            value=json.loads(raw)
            if not isinstance(value,dict) or set(value)-{'question','source_ids','model'}:raise ValueError()
            question=value['question'];selected=value.get('source_ids');chosen=value.get('model','gemini-3.5-flash-lite')
            if not isinstance(question,str) or not isinstance(chosen,str) or (selected is not None and
                    (not isinstance(selected,list) or any(not isinstance(i,str) for i in selected))):raise ValueError()
        except (ValueError,KeyError,TypeError):raise HTTPException(422,'Invalid review question') from None
        if not key and not generator_factory:raise HTTPException(503,'Generation is not configured; inventory remains available')
        return await run_in_threadpool(controller.query,question,selected,chosen,'keyword')

    return app


def create_runtime():
    return create_review_app(Path(os.environ['RAG_REVIEW_ASSESSMENT']),Path(os.environ['RAG_REVIEW_STATE']),
        token=os.environ.get('RAG_NOC_SERVICE_TOKEN',''),key=os.environ.get('GEMINI_API_KEY',''),
        model=os.environ.get('RAG_GEMINI_MODEL','gemini-3.5-flash-lite'))
