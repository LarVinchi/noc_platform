from uuid import uuid4
from io import BytesIO
from zipfile import ZipFile
from test_ftth_intake_api import api, pytestmark  # noqa: F401


def observation(**changes):
    return {'request_key': str(uuid4()), 'expected_revision': 0, 'effective_at': '2026-07-04T10:00:00+01:00',
            'grid': 'on', 'gen': 'off', 'grid_balance': 100, 'comment': 'Trial observation', **changes}


def test_collector_retry_conflict_projection_and_production_guard(api, monkeypatch):
    client, db = api
    from app.models.energy import EnergyTrialEvent
    assert db.query(EnergyTrialEvent).count() == 0
    first = observation()
    result = client.post('/api/energy/trial/PROJN01', json=first)
    assert result.status_code == 200, result.text
    assert result.json()['event']['revision'] == 1
    assert client.post('/api/energy/trial/PROJN01', json=first).json()['outcome'] == 'already_recorded'
    assert client.post('/api/energy/trial/PROJN01', json={**first, 'grid': 'off'}).status_code == 409
    assert client.post('/api/energy/trial/PROJN01', json=observation()).status_code == 409
    second = observation(expected_revision=1, effective_at='2026-07-04T11:00:00+01:00', grid='off', grid_balance=90)
    assert client.post('/api/energy/trial/PROJN01', json=second).status_code == 200
    report = client.get('/api/energy/report', params={'source':'trial','day':'2026-07-04'}).json()
    assert report['sites'][0]['gridHours'] == 1
    assert report['sites'][0]['gridUsed'] == 10
    assert not report['telemetry_connected']
    assert client.post('/api/energy/trial/LEKKP01', json=observation(diesel_litres=10)).status_code == 422
    assert client.post('/api/energy/trial/PROJN01', json=observation(expected_revision=2, effective_at='2099-01-01T00:00:00+01:00')).status_code == 422
    from app.core.config import settings
    monkeypatch.setattr(settings,'ENVIRONMENT','production')
    from app.core import security
    monkeypatch.setattr(security,'auth_configuration',lambda:{'configured':True,'mode':'entra'})
    monkeypatch.setattr(security,'validate_token',lambda token:{'id':'test','verified':True,'roles':['NOC.Operator']})
    assert client.post('/api/energy/trial/PROJN01', headers={'authorization':'Bearer test'}, json=first).status_code == 409


def test_workbook_import_roles_duplicate_revision_and_reports(api, monkeypatch):
    client, db = api
    stream = BytesIO()
    with ZipFile(stream, 'w') as z:
        z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="RawData" r:id="r1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        labels = ''.join(f'<c r="{col}3" t="inlineStr"><is><t>{label}</t></is></c>' for col,label in {'B':'StartTime','C':'StopTime','D':'SitePowerSource','G':'EkedcStatus','S':'GeneratorStatus'}.items())
        z.writestr('xl/worksheets/sheet1.xml', f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="3">{labels}</row><row r="4"><c r="B4"><v>46207</v></c><c r="C4"><v>46207.5</v></c><c r="D4" t="inlineStr"><is><t>PROJN01-04174881666</t></is></c><c r="G4" t="inlineStr"><is><t>ON</t></is></c></row></sheetData></worksheet>')
    files = {'file':('tracker.xlsx',stream.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
    first = client.post('/api/energy/imports', files=files)
    assert first.status_code == 200, first.text
    assert client.post('/api/energy/imports', files=files).json()['outcome'] == 'already_imported'
    assert not client.get('/api/energy/status').json()['connected']
    report = client.get('/api/energy/report',params={'day':'2026-07-04'}).json()
    assert report['sites'][0]['gridHours'] == 12
    assert report['sites'][0]['gridPartial']
    weekly = client.get('/api/energy/weekly', params={'week_start': '2026-06-29'})
    assert weekly.status_code == 200, weekly.text
    summary = weekly.json()
    assert summary['mode'] == 'workbook'
    assert summary['import']['id'] == first.json()['import']['id']
    assert len(summary['sites']) == 3
    site = summary['sites'][0]
    assert site['meterNumbers'] == ['04174881666']
    assert len(site['days']) == 7
    assert site['days'][5]['gridHours'] == report['sites'][0]['gridHours']
    assert site['gridHours'] == 12
    # Unrecorded elapsed days contribute zero; retain the partial-data flag.
    assert site['averageGridHours'] == 12 / 7
    assert site['days'][0]['gridHours'] == 0
    assert site['gridPartial']
    assert client.post('/api/energy/imports',files={'file':('broken.xlsx',b'not a zip')}).status_code == 422
    from app.core import security
    monkeypatch.setattr(security,'auth_configuration',lambda:{'configured':True,'mode':'entra'})
    actor={'id':'viewer','verified':True,'roles':['NOC.Viewer']}
    monkeypatch.setattr(security,'validate_token',lambda token:actor.copy())
    headers={'authorization':'Bearer test'}
    assert client.get('/api/energy/report',headers=headers,params={'day':'2026-07-04'}).status_code == 200
    assert client.get('/api/energy/weekly',headers=headers,params={'week_start':'2026-06-29'}).status_code == 200
    assert client.get('/api/energy/weekly',params={'week_start':'2026-06-29'}).status_code == 401
    assert client.post('/api/energy/imports',headers=headers,files=files).status_code == 403
    actor['roles']=['NOC.Operator']
    assert client.post('/api/energy/imports',headers=headers,files=files).status_code == 403


def test_weekly_missing_import_date_validation_and_production_trial_guard(api, monkeypatch):
    client, _ = api
    assert client.get('/api/energy/weekly', params={'week_start': '2026-06-29'}).status_code == 404
    assert client.get('/api/energy/weekly', params={'week_start': '2026-06-30'}).status_code == 422
    assert client.get('/api/energy/weekly', params={'week_start': '2099-01-05'}).status_code == 422
    response = client.get('/api/energy/weekly', params={'week_start': '2026-06-29', 'source': 'trial'})
    assert response.status_code == 200, response.text
    assert response.json()['mode'] == 'trial'
    site = response.json()['sites'][0]
    assert site['gridHours'] == 0
    assert site['averageGridHours'] == 0
    assert site['zeroDays'] == 7
    assert site['daysWithRecords'] == 0
    from app.core.config import settings
    from app.core import security
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'production')
    monkeypatch.setattr(security, 'auth_configuration', lambda: {'configured': True, 'mode': 'entra'})
    monkeypatch.setattr(security, 'validate_token', lambda token: {'id': 'viewer', 'verified': True, 'roles': ['NOC.Viewer']})
    assert client.get('/api/energy/weekly', headers={'authorization': 'Bearer test'},
                      params={'week_start': '2026-06-29', 'source': 'trial'}).status_code == 409
