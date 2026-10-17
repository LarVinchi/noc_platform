from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from io import BytesIO
from zipfile import ZipFile
import pytest
from app.services.energy_collector import trial_records, trial_coverage
from app.services.energy_reporting import read_records, make_report, records_from_json, records_to_json

WAT = timezone(timedelta(hours=1))


def event(revision, hour, grid='off', gen='off', balance=None):
    return SimpleNamespace(site='PROJN01', revision=revision, effective_at=datetime(2026, 7, 4, hour, tzinfo=WAT),
                           entered_by='test-operator', observation={'grid': grid, 'gen': gen, 'grid_balance': balance,
                                                                   'diesel_litres': None, 'comment': ''})


def test_collector_projects_without_duplicate_off_entries():
    events = [event(1, 10, 'on', balance=100), event(2, 11, balance=90), event(3, 12, gen='on'), event(4, 14)]
    records = trial_records(events)
    site = make_report(records, '2026-07-04')['sites'][0]
    assert site['gridHours'] == 1 and site['genHours'] == 2
    assert site['gridUsed'] == 10
    coverage = trial_coverage(events, '2026-07-04')['PROJN01']
    assert coverage['confirmedNoGridOrGenHours'] == 1
    assert coverage['loadPowerStatus'] == 'unknown'
    assert coverage['unconfirmedHours'] == 20
    assert len([r for r in records if r['stop'] is None]) == 2


def test_unknown_states_are_not_confirmed_no_supply():
    events = [event(1, 10, grid='unknown'), event(2, 11)]
    coverage = trial_coverage(events, '2026-07-04')['PROJN01']
    assert coverage['confirmedNoGridOrGenHours'] == 0
    assert coverage['unconfirmedHours'] == 24


def workbook(headers=True):
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="RawData" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        labels = ''.join(f'<c r="{key}3" t="inlineStr"><is><t>{value}</t></is></c>' for key, value in {'B':'StartTime','C':'StopTime','D':'SitePowerSource','G':'EkedcStatus','S':'GeneratorStatus'}.items()) if headers else ''
        archive.writestr('xl/worksheets/sheet1.xml', f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="3">{labels}</row><row r="4"><c r="B4"><v>46207</v></c><c r="C4"><v>46207.5</v></c><c r="D4" t="inlineStr"><is><t>PROJN01-04174881666</t></is></c><c r="G4" t="inlineStr"><is><t>ON</t></is></c><c r="E4"><v>100</v></c><c r="F4"><v>80</v></c></row></sheetData></worksheet>')
    stream.seek(0)
    return stream


def test_workbook_contract_inline_strings_and_serialization():
    records = read_records(workbook())
    assert len(records) == 1
    assert records == records_from_json(records_to_json(records))
    site = make_report(records, '2026-07-04')['sites'][0]
    assert site['gridHours'] == 12 and site['gridUsed'] == 20
    with pytest.raises(ValueError, match='column contract'):
        read_records(workbook(headers=False))
