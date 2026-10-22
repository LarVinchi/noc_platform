"""Read-only reporting model. All workbook timestamps are Lagos wall time."""
from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET
import zipfile
import re
from collections import defaultdict

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
EPOCH = dt.datetime(1899, 12, 30)
SITES = {
    'PROJN01': {'name': 'Project Office', 'fuel': 'Diesel'},
    'LEKKP01': {'name': 'Lekki PoP', 'fuel': 'Gas'},
    'ADEMP01': {'name': 'Ademola PoP', 'fuel': 'Gas'},
}


def number(value):
    try:
        result = float(value) if value is not None and str(value).strip() else None
        if result is not None and not __import__('math').isfinite(result):
            raise OverflowError('Non-finite workbook number')
        return result
    except (ValueError, TypeError):
        return None


def timestamp(value):
    value = number(value)
    return EPOCH + dt.timedelta(seconds=round(value * 86400)) if value is not None else None


def iso(value):
    return value.isoformat() if value else None


def read_records(path):
    records = []
    with zipfile.ZipFile(path) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(t.text or '' for t in node.findall('.//m:t', NS))
                       for node in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('m:si', NS)]
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        sheet = next(s for s in workbook.find('m:sheets', NS) if s.attrib['name'] == 'RawData')
        relationships = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        target = relationships[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
        target = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        rows = ET.fromstring(archive.read(target)).findall('m:sheetData/m:row', NS)
        header = next((r for r in rows if r.attrib.get('r') == '3'), None)
        names = {}
        if header is not None:
            for cell in header:
                v = cell.find('m:v', NS)
                value = v.text if v is not None else None
                if cell.attrib.get('t') == 's' and value is not None:
                    value = strings[int(value)]
                elif cell.attrib.get('t') == 'inlineStr':
                    value = ''.join(t.text or '' for t in cell.findall('.//m:t', NS))
                names[cell.attrib['r']] = value
        if any(names.get(key) != value for key, value in {'B3': 'StartTime', 'C3': 'StopTime', 'D3': 'SitePowerSource', 'G3': 'EkedcStatus', 'S3': 'GeneratorStatus'}.items()):
            raise ValueError('RawData column contract changed')
        calibration = {}
        for calibration_row in rows[:10]:
            for cell in calibration_row:
                if cell.attrib['r'] in ('Z5', 'Z6'):
                    value = cell.find('m:v', NS)
                    calibration[cell.attrib['r']] = number(value.text) if value is not None else None
        litres_per_cm = (calibration['Z5'] * calibration['Z6'] / 1000
                         if calibration.get('Z5') and calibration.get('Z6') else None)
        for row in rows:
            cells = {}
            for cell in row:
                col = ''.join(c for c in cell.attrib['r'] if c.isalpha())
                v = cell.find('m:v', NS)
                value = v.text if v is not None else None
                if cell.attrib.get('t') == 's' and value is not None:
                    value = strings[int(value)]
                elif cell.attrib.get('t') == 'inlineStr':
                    value = ''.join(t.text or '' for t in cell.findall('.//m:t', NS))
                cells[col] = value
            start, source = timestamp(cells.get('B')), cells.get('D') or ''
            site = ('PROJN01' if source.startswith('PROJN01-') else
                    'LEKKP01' if source.startswith('LEKKP001-') else
                    'ADEMP01' if source.startswith('ADEMP001-') else None)
            if start is None or site is None:
                continue
            kind = 'gen' if source.upper().endswith('-GEN') else 'grid'
            a, b = ('E', 'F') if kind == 'grid' else ('M', 'N')
            opening, closing = number(cells.get(a)), number(cells.get(b))
            derived = False
            # The workbook's shared M/N formulas can have no cached result.
            # Rectangular tank cross-section is read from the workbook itself.
            if kind == 'gen' and site == 'PROJN01' and litres_per_cm:
                reserve = number(cells.get('L')) or 0
                for col, which in [('J', 'opening'), ('K', 'closing')]:
                    dip = number(cells.get(col))
                    if dip is not None and ((which == 'opening' and opening is None) or (which == 'closing' and closing is None)):
                        volume = dip * litres_per_cm + reserve
                        if which == 'opening': opening = volume
                        else: closing = volume
                        derived = True
            hm_start, hm_end = number(cells.get('H')), number(cells.get('I'))
            records.append({
                'row': int(row.attrib['r']), 'site': site, 'source': source, 'kind': kind,
                'start': start, 'stop': timestamp(cells.get('C')),
                'status': cells.get('G' if kind == 'grid' else 'S') or '',
                'opening': opening, 'closing': closing, 'derived': derived,
                'meterHours': (hm_end - hm_start) * 24 if hm_start is not None and hm_end is not None else None,
                'operator': cells.get('T') or '', 'comment': cells.get('U') or '',
            })
    return sorted(records, key=lambda r: (r['start'], r['row']))


def window(day):
    """A report labelled D covers (D-1 23:59:59, D 23:59:59]."""
    end = dt.datetime.combine(dt.date.fromisoformat(day), dt.time(23, 59, 59))
    return end - dt.timedelta(days=1), end


def union_seconds(intervals):
    total = 0
    end = None
    for a, b in sorted(intervals):
        if b <= a:
            continue
        total += (b - max(a, end)).total_seconds() if end is not None and a < end else (b - a).total_seconds()
        end = max(end, b) if end else b
    return total


def active(record):
    return record['status'] in ('ON', 'Unit Closure', 'Unit Start', 'Diesel Cycle Closure', 'Diesel Cycle Start')


def comment_addition(record):
    """Read an explicit quantity, not an intended purchase or a bare refill keyword."""
    comment = record.get('comment') or ''
    matches = list(re.finditer(r'\b(?:refill(?:ed|ing)?|top[\s-]*up|replenish(?:ed|ment)?|added)\s*(?:of\s*|with\s*|by\s*|[:=]\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(litres?|liters?|ltrs?|l\b|kwh|units?)', comment, re.I))
    matches.extend(re.finditer(r'\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(litres?|liters?|ltrs?|l\b|kwh|units?)\s*(?:(?:diesel|generator|geneator|was|were|of)\s+){0,3}(?:top[\s-]*up|refill(?:ed)?|added)\b', comment, re.I))
    quantities, seen = [], set()
    for match in matches:
        if re.search(r'\b(no|not|planned|expected|requested|pending|cancelled|canceled)\b', comment[max(0, match.start()-35):match.start()], re.I):
            continue
        liquid = match[2].lower().startswith('l')
        if liquid != (record['kind'] == 'gen'):
            continue
        quantity = float(match[1].replace(',', ''))
        if 0 < quantity <= 10000000 and match.span(1) not in seen:
            quantities.append(quantity); seen.add(match.span(1))
    return quantities[0] if len(quantities) == 1 else None


def events_for(records):
    """Identify additions; infer balance jumps only between consecutive source readings."""
    events, prior = [], {}
    for record in records:
        key = (record['site'], record['kind'], record['source'])
        prev = prior.get(key)
        opening, closing = record['opening'], record['closing']
        stated = comment_addition(record)
        incoming = prev and opening is not None and prev['closing'] is not None and opening > prev['closing'] + .01
        # A marker start follows a marker closure at the same timestamp.
        if incoming:
            paired = ('Start' in record['status'] and 'Closure' in prev['status']
                      and prev['stop'] == record['start'])
            consistent = stated is None or abs(stated - (opening - prev['closing'])) <= .01
            events.append({'site': record['site'], 'kind': record['kind'], 'time': iso(record['start']),
                           'amount': stated or opening - prev['closing'], 'row': record['row'], 'inSession': False,
                           'previousRow': prev['row'], 'evidence': 'Comment/opening balance mismatch · verify' if not consistent else 'Comment quantity at opening' if stated else 'Paired cycle markers' if paired else 'Balance increase · net addition, verify',
                           'confirmed': (paired or stated is not None) and consistent, 'comment': record['comment']})
        increased = opening is not None and closing is not None and closing > opening + .01
        if increased or (stated is not None and not incoming):
            amount = stated if stated is not None and not incoming else closing - opening
            events.append({'site': record['site'], 'kind': record['kind'], 'time': iso(record['stop'] or record['start']),
                           'amount': amount, 'row': record['row'], 'previousRow': None, 'inSession': True,
                           'evidence': 'Refill/top-up quantity in comment' if stated is not None and not incoming else 'Level increase · net addition, verify',
                           'confirmed': stated is not None and not incoming, 'comment': record['comment']})
        # Retain chronology: missing readings break inference instead of bridging unknown sessions.
        prior[key] = record
    return events


def make_report(records, day, all_events=None):
    begin, end = window(day)
    result = {'date': day, 'start': iso(begin), 'end': iso(end), 'sites': [], 'events': [], 'issues': []}
    source_events = all_events if all_events is not None else events_for(records)
    event_index = defaultdict(list)
    day_additions = defaultdict(float)
    for event in source_events:
        event_index[(event['site'], event['kind'], event['row'])].append(event)
    for event in source_events:
        if begin < dt.datetime.fromisoformat(event['time']) <= end:
            result['events'].append(event)
            day_additions[(event['site'], event['kind'], event['row'])] += event['amount']
    for site, info in SITES.items():
        selected, intervals, consumption = [], defaultdict(list), defaultdict(list)
        missing = defaultdict(int)
        meter_hours = []
        issues = []
        def issue(r, message):
            issues.append({'site': site, 'row': r['row'], 'message': message})
        for r in records:
            if r['site'] != site:
                continue
            start, stop = r['start'], r['stop']
            touches = (stop is not None and stop > begin and start < end and stop > start) or (begin < start <= end)
            if not touches:
                continue
            a, b = max(start, begin), min(stop, end) if stop else None
            duration = (b - a).total_seconds() if b and b > a else 0
            is_active = active(r)
            if stop is None:
                issue(r, 'Open record: stop time missing; excluded from totals')
                missing[r['kind']] += 1
            elif stop < start:
                issue(r, 'Stop precedes start; excluded from totals')
                missing[r['kind']] += 1
            elif duration and is_active:
                intervals[r['kind']].append((a, b))
                if r['status'] != 'ON':
                    issue(r, 'Cycle marker includes operating time; included, verify status')
            elif duration and r['status'] != 'OFF':
                issue(r, 'Unrecognised status: operating time excluded')
            opening, closing = r['opening'], r['closing']
            additions = event_index[(site, r['kind'], r['row'])]
            within = sum(e['amount'] for e in additions if e.get('inSession') and e['confirmed'])
            inferred = any(e.get('inSession') and not e['confirmed'] for e in additions)
            chart_addition = day_additions[(site, r['kind'], r['row'])]
            comment = r.get('comment', '')
            unquantified = (re.search(r'\b(refill(?:ed)?|top[\s-]*up)\b', comment, re.I)
                and not re.search(r'\b(no|not|planned|expected|requested|pending|cancelled|canceled)\b', comment, re.I)
                and comment_addition(r) is None and not any(not e.get('inSession') for e in additions))
            used = None
            if duration and is_active:
                if opening is None or closing is None:
                    if r['kind'] == 'grid' or info['fuel'] == 'Diesel':
                        missing[r['kind']] += 1
                        issue(r, 'Consumption reading missing; usage total is partial')
                elif inferred or unquantified or closing > opening + within + .01:
                    missing[r['kind']] += 1
                    issue(r, 'Refill/level increase shown separately; consumption needs an explicit, consistent addition quantity')
                else:
                    fraction = duration / (stop - start).total_seconds()
                    used = max(0, opening + within - closing) * fraction
                    consumption[r['kind']].append(used)
                    if fraction < 1:
                        issue(r, 'Session crosses reporting boundary; consumption prorated by time')
                if r['kind'] == 'gen' and r['meterHours'] is not None:
                    mh = r['meterHours']
                    if mh >= 0:
                        meter_hours.append(mh * duration / (stop - start).total_seconds())
                    else:
                        issue(r, 'Generator hour meter decreased; reading excluded')
            selected.append({**{k: v for k, v in r.items() if k not in ('start', 'stop')},
                             'start': iso(start), 'stop': iso(stop), 'hours': duration / 3600 if is_active else 0,
                             'used': used, 'clipStart': iso(a), 'clipStop': iso(b), 'active': is_active})
            selected[-1].update(addition=chart_addition, additionConfirmed=all(e['confirmed'] for e in additions),
                                additionLabel='Diesel refill' if r['kind'] == 'gen' else 'EKEDC top-up')
        hours = {k: union_seconds(intervals[k]) / 3600 for k in ('grid', 'gen')}
        for kind in ('grid', 'gen'):
            summed = sum((b - a).total_seconds() for a, b in intervals[kind]) / 3600
            if summed - hours[kind] > .001:
                issues.append({'site': site, 'row': None, 'message': f'Overlapping {kind} records: hours merged; consumption may be duplicated'})
        covered = union_seconds(intervals['grid'] + intervals['gen']) / 3600
        result['sites'].append({
            'id': site, **info, 'gridHours': hours['grid'], 'genHours': hours['gen'],
            'unaccountedHours': max(0, 24 - covered),
            'overlapHours': max(0, hours['grid'] + hours['gen'] - covered),
            'gridUsed': sum(consumption['grid']) if consumption['grid'] else None,
            'dieselUsed': sum(consumption['gen']) if consumption['gen'] and info['fuel'] == 'Diesel' else None,
            'gridAdded': sum(e['amount'] for e in result['events'] if e['site'] == site and e['kind'] == 'grid'),
            'dieselAdded': sum(e['amount'] for e in result['events'] if e['site'] == site and e['kind'] == 'gen' and info['fuel'] == 'Diesel'),
            'gridPartial': missing['grid'] > 0, 'dieselPartial': missing['gen'] > 0,
            'meterHours': sum(meter_hours) if meter_hours else None,
            'records': selected, 'issues': issues,
        })
        result['issues'].extend(issues)
    return result


def records_to_json(records):
    return [{**r, 'start': iso(r['start']), 'stop': iso(r['stop'])} for r in records]


def records_from_json(records):
    return [{**r, 'start': dt.datetime.fromisoformat(r['start']),
             'stop': dt.datetime.fromisoformat(r['stop']) if r['stop'] else None} for r in records]


def metadata(records, source_name):
    latest = max(r['start'] for r in records)
    return {'source': source_name, 'records': len(records),
            'firstDate': min(r['start'] for r in records).date().isoformat(),
            'lastDate': latest.date().isoformat(), 'latestRecord': iso(latest),
            'defaultDate': (latest.date() - dt.timedelta(days=1)).isoformat(),
            'timezone': 'Africa/Lagos'}
