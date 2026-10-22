import copy
import pytest
from tests.integration.test_knowledge_workflow import api  # noqa: F401
from app.api.routers import ftth_reporting
from app.models.ftth_reporting import FtthNetworkSnapshot


@pytest.fixture
def network(api):
    client,actor,calls,db=api
    FtthNetworkSnapshot.__table__.create(db.bind)
    client.app.include_router(ftth_reporting.router,prefix='/api')
    return client,actor,db


def payload():
    return {'date':'2026-09-28','notes':'Reconciled synthetic test source',
        'areas':[{'id':'SYNTHETIC-01','zone':'Test zone','homes':100,'counts':[2,10,1,0]}],
        'outside':[{'zone':'Test zone','counts':[0,3,0,0]}]}


def test_publish_replay_and_exact_snapshot_history(network):
    client,actor,db=network
    result=client.post('/api/ftth/network-reports',json=payload())
    assert result.status_code==200,result.text
    value=result.json()['snapshot']
    assert value['created_by']=='admin-test' and value['partners']==ftth_reporting.PARTNERS
    assert client.post('/api/ftth/network-reports',json=payload()).json()['outcome']=='already_recorded'
    assert db.query(FtthNetworkSnapshot).count()==1
    changed=payload();changed['areas'][0]['counts'][1]=12
    updated=client.post('/api/ftth/network-reports',json=changed).json()['snapshot']
    assert updated['snapshot_id']!=value['snapshot_id']
    assert client.get('/api/ftth/network-reports/'+value['snapshot_id']).json()['areas'][0]['counts'][1]==10
    assert len(client.get('/api/ftth/network-reports').json()['items'])==2


@pytest.mark.parametrize('change',[
    lambda v:v['areas'][0].update(counts=[101,0,0,0]),
    lambda v:v['areas'][0].update(counts=[True,0,0,0]),
    lambda v:v['areas'][0].update(counts=[-1,0,0,0]),
    lambda v:v['areas'].append({**v['areas'][0],'id':'synthetic-01'}),
    lambda v:v.update(date='9999-12-31'),
    lambda v:v.update(date=0),
    lambda v:v.update(created_by='spoofed-author'),
    lambda v:v['outside'].append(copy.deepcopy(v['outside'][0])),
])
def test_invalid_capacity_counts_dates_and_identity_are_rejected(network,change):
    client,actor,db=network
    data=payload();change(data)
    assert client.post('/api/ftth/network-reports',json=data).status_code==422
    assert db.query(FtthNetworkSnapshot).count()==0


def test_readers_can_view_but_only_admins_publish(network):
    client,actor,db=network
    assert client.post('/api/ftth/network-reports',json=payload()).status_code==200
    actor['roles']=['NOC.Operator']
    assert client.post('/api/ftth/network-reports',json=payload()).status_code==403
    actor['roles']=['NOC.Viewer']
    assert client.get('/api/ftth/network-reports').status_code==200
    assert client.post('/api/ftth/network-reports',json=payload()).status_code==403


def test_snapshot_body_is_bounded(network):
    client,actor,db=network
    assert client.post('/api/ftth/network-reports',content='x'*2000001,headers={'Content-Type':'application/json'}).status_code==413
