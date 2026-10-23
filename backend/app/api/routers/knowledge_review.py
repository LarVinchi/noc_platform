"""Administrator-only accepted-demo corpus; separate from production approval."""
import json
import urllib.request
from urllib.parse import urlencode, urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.core.security import actor_context

router=APIRouter(prefix='/knowledge-review',tags=['Review knowledge corpus'])


def administrator():
    if 'NOC.Admin' not in actor_context.get().get('roles',[]):
        raise HTTPException(403,'Administrator role required for the review collection')


def enabled():
    return settings.KNOWLEDGE_REVIEW_ENABLED and settings.ENVIRONMENT=='development' and settings.AUTH_MODE=='preview'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def exchange(path,payload=None):
    if not enabled():raise HTTPException(404,'Review collection is not enabled')
    target=urlsplit(settings.KNOWLEDGE_REVIEW_URL)
    token=settings.KNOWLEDGE_REVIEW_TOKEN.get_secret_value()
    if (target.scheme not in ('http','https') or not target.hostname or target.username or target.password
            or target.query or target.fragment or not 32<=len(token)<=512 or not token.isascii()):
        raise HTTPException(503,'The private review collection has not been configured')
    request=urllib.request.Request(settings.KNOWLEDGE_REVIEW_URL.rstrip('/')+path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=135 if path=='/v1/query' else 30) as response:
            raw=response.read(3_000_001)
        if len(raw)>3_000_000:raise ValueError('Response exceeds limits')
        value=json.loads(raw)
        if not isinstance(value,dict):raise ValueError('Invalid response')
        return value
    except Exception as error:
        code=getattr(error,'code',None)
        detail={'category':type(error).__name__,'http_status':code if type(code) is int else None,
                'message':'Private review worker did not return a usable response. No answer released.'}
        raise HTTPException(503,detail) from None


@router.get('/status',dependencies=[Depends(administrator)])
def status():
    return exchange('/v1/status') if enabled() else {'enabled':False,'generation_available':False}


@router.get('/sources',dependencies=[Depends(administrator)])
def sources():return exchange('/v1/sources')


@router.get('/incidents',dependencies=[Depends(administrator)])
def incidents(customer:str=Query('',max_length=100),offset:int=Query(0,ge=0,le=1000),limit:int=Query(25,ge=1,le=100)):
    return exchange('/v1/incidents?'+urlencode({'customer':customer,'offset':offset,'limit':limit}))


@router.get('/incidents/export',dependencies=[Depends(administrator)])
def export(customer:str=Query('',max_length=100)):
    return exchange('/v1/incidents/export?'+urlencode({'customer':customer}))


@router.get('/sources/{identifier}',dependencies=[Depends(administrator)])
def source(identifier:UUID):return exchange('/v1/sources/'+str(identifier))


class Question(BaseModel):
    model_config=ConfigDict(extra='forbid')
    question:str=Field(min_length=3,max_length=4000)
    source_ids:list[UUID]|None=Field(default=None,max_length=1000)
    model:str=Field(default='gemini-3.5-flash-lite',pattern=r'^gemini-[a-z0-9.-]{1,80}$')


@router.post('/query',dependencies=[Depends(administrator)])
def query(data:Question):
    return exchange('/v1/query',data.model_dump(mode='json'))
