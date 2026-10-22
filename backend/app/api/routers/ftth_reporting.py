"""FTTH snapshot reporting; no implicit conversion of daily work into cumulative totals."""
import datetime as dt
import hashlib
import json
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator, field_validator
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.db import get_db
from app.core.security import actor_context
from app.models.ftth_reporting import FtthNetworkSnapshot

router=APIRouter(prefix='/ftth/network-reports',tags=['FTTH cumulative reports'])
PARTNERS=['MetroReach Retail','MTNN','MANGONET','TELEWYZ']


class Contract(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)


class Area(Contract):
    id:str=Field(pattern='^[A-Za-z0-9_-]{1,40}$')
    zone:str=Field(min_length=1,max_length=100)
    homes:StrictInt=Field(ge=0,le=10000000)
    counts:list[StrictInt]=Field(min_length=4,max_length=4)

    @model_validator(mode='after')
    def valid(self):
        if self.id.upper()=='OUTSIDE_RFS' or any(c<0 or c>10000000 for c in self.counts) or sum(self.counts)>self.homes:
            raise ValueError('Connections must fit homes passed and use a real service-area ID')
        return self


class Outside(Contract):
    zone:str=Field(min_length=1,max_length=100)
    counts:list[StrictInt]=Field(min_length=4,max_length=4)

    @model_validator(mode='after')
    def valid(self):
        if any(c<0 or c>10000000 for c in self.counts): raise ValueError('Invalid partner count')
        return self


class Snapshot(Contract):
    date:dt.date
    notes:str=Field(min_length=5,max_length=2000)
    areas:list[Area]=Field(min_length=1,max_length=5000)
    outside:list[Outside]=Field(default_factory=list,max_length=500)

    @field_validator('date',mode='before')
    @classmethod
    def exact_day(cls,value):
        if not isinstance(value,str) or dt.date.fromisoformat(value).isoformat()!=value:
            raise ValueError('Use an exact YYYY-MM-DD date')
        return value

    @model_validator(mode='after')
    def valid(self):
        today=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=1)).date()
        if self.date>today or len({a.id.casefold() for a in self.areas})!=len(self.areas) or len({a.zone.casefold() for a in self.outside})!=len(self.outside):
            raise ValueError('Future dates or duplicate source rows are not allowed')
        return self


def row(value):
    return {'snapshot_id':value.snapshot_id,'date':value.report_date,'notes':value.source_note,'sha256':value.sha256,
        'created_by':value.created_by,'created_at':value.created_at,**value.payload,'partners':PARTNERS}


@router.get('')
def listing(db:Session=Depends(get_db)):
    values=db.query(FtthNetworkSnapshot).order_by(FtthNetworkSnapshot.report_date.desc(),FtthNetworkSnapshot.created_at.desc()).limit(100).all()
    return {'items':[{'snapshot_id':v.snapshot_id,'date':v.report_date,'notes':v.source_note,'created_at':v.created_at} for v in values],'limit':100,'partners':PARTNERS}


@router.get('/{snapshot_id}')
def detail(snapshot_id:UUID,db:Session=Depends(get_db)):
    value=db.get(FtthNetworkSnapshot,snapshot_id)
    if not value: raise HTTPException(404,'FTTH snapshot not found')
    return row(value)


@router.post('')
async def publish(request:Request,db:Session=Depends(get_db)):
    if 'NOC.Admin' not in actor_context.get()['roles']: raise HTTPException(403,'Administrator role required to publish reconciled network totals')
    body=bytearray()
    async for block in request.stream():
        if len(body)+len(block)>2000000: raise HTTPException(413,'Snapshot exceeds 2 MB')
        body.extend(block)
    try: value=Snapshot.model_validate_json(body)
    except ValueError: raise HTTPException(422,'Invalid snapshot: check dates, unique areas, homes passed and four partner counts') from None
    return await run_in_threadpool(save_snapshot,value,db)


def save_snapshot(value,db):
    canonical=value.model_dump(mode='json')
    digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    previous=db.query(FtthNetworkSnapshot).filter_by(sha256=digest).first()
    if previous:return {'outcome':'already_recorded','snapshot':row(previous)}
    record=FtthNetworkSnapshot(snapshot_id=uuid4(),report_date=value.date,source_note=value.notes,
        payload={'areas':canonical['areas'],'outside':canonical['outside']},sha256=digest,created_by=actor_context.get()['id'])
    db.add(record)
    try: db.commit()
    except IntegrityError:
        db.rollback()
        previous=db.query(FtthNetworkSnapshot).filter_by(sha256=digest).first()
        if previous:return {'outcome':'already_recorded','snapshot':row(previous)}
        raise
    return {'outcome':'created','snapshot':row(record)}
