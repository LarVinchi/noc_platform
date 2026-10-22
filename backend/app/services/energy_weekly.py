"""Monday–Sunday summaries using the existing daily interval calculations."""
import datetime as dt
from app.services.energy_reporting import make_report, events_for, SITES

WAT = dt.timezone(dt.timedelta(hours=1))


def weekly_report(records, week_start, now=None):
    start = dt.date.fromisoformat(week_start)
    if start.weekday() != 0:
        raise ValueError('Week must start on Monday')
    if start > dt.datetime.now(WAT).date() + dt.timedelta(days=366):
        raise ValueError('Week is outside the supported reporting range')
    end = start + dt.timedelta(days=6)
    now = now or dt.datetime.now(WAT)
    elapsed = dt.datetime.combine(end, dt.time(23, 59, 59), WAT) <= now
    now = now.astimezone(WAT)
    average_days = min(7, max(0, (now.date() - start).days + 1))
    wall_now = now.replace(tzinfo=None)
    # Saved future closures are not completed work yet. Keep them open for source review.
    records = [{**r, 'stop': None} if r['stop'] and r['stop'] > wall_now else r
               for r in records if r['start'] <= wall_now]
    events = events_for(records)
    days = [make_report(records, (start + dt.timedelta(days=i)).isoformat(), events) for i in range(7)]
    result = {'weekStart': start.isoformat(), 'weekEnd': end.isoformat(), 'start': days[0]['start'],
              'end': days[-1]['end'], 'timezone': 'Africa/Lagos', 'elapsed': elapsed,
              'averageDays': average_days, 'averageBasis': 'Seven calendar days' if elapsed else 'Calendar days reached, including today',
              'zeroForUnrecordedDays': True, 'asOf': now.isoformat(),
              'sites': [], 'events': [event for day in days for event in day['events']]}
    for index, (site, info) in enumerate(SITES.items()):
        grid_measured = site == 'PROJN01' or any(r['site'] == site and r['kind'] == 'grid' and
            (r['opening'] is not None or r['closing'] is not None) for r in records)
        rows = []
        for position, day in enumerate(days):
            value = day['sites'][index]
            def observed(kind):
                return any(r['kind'] == kind and r['stop'] and r['clipStop'] and r['clipStop'] > r['clipStart']
                           and r['status'] in ('ON', 'OFF', 'Unit Closure', 'Unit Start', 'Diesel Cycle Closure', 'Diesel Cycle Start')
                           for r in value['records'])
            grid_known, gen_known = observed('grid'), observed('gen')
            logged = grid_known or gen_known
            included = position < average_days
            grid_used = value['gridUsed']
            if grid_measured and value['gridHours'] == 0 and grid_used is None and not value['gridPartial']:
                grid_used = 0
            diesel_used = value['dieselUsed']
            if info['fuel'] == 'Diesel' and value['genHours'] == 0 and not value['dieselPartial']:
                diesel_used = 0
            rows.append({'date': day['date'], 'gridHours': value['gridHours'] if included else None,
                         'genHours': value['genHours'] if included else None, 'gridUsed': grid_used if included else None,
                         'dieselUsed': diesel_used if included and info['fuel'] == 'Diesel' else None,
                         'gridAdded': value['gridAdded'] if included else None, 'dieselAdded': value['dieselAdded'] if included else None,
                         'gridAdditionInferred': any(e['site']==site and e['kind']=='grid' and not e['confirmed'] for e in day['events']),
                         'dieselAdditionInferred': any(e['site']==site and e['kind']=='gen' and not e['confirmed'] for e in day['events']),
                         'future': not included, 'zeroAssumed': included and not logged,
                         'gridRecorded': grid_known,
                         'gridPartial': value['gridPartial'], 'dieselPartial': value['dieselPartial'],
                         'issues': value['issues'], 'logged': logged})
        def total(key):
            values = [row[key] for row in rows if row[key] is not None]
            return sum(values) if values else None
        def average(key, complete=True):
            value = total(key)
            return value / average_days if value is not None and average_days and complete else None
        relevant = rows[:average_days]
        grid_complete = all(not row['gridPartial'] for row in relevant)
        gen_complete = all(not row['dieselPartial'] for row in relevant)
        grid_usage_complete = all(row['gridUsed'] is not None and not row['gridPartial'] for row in relevant)
        diesel_complete = info['fuel'] == 'Diesel' and all(row['dieselUsed'] is not None and not row['dieselPartial'] for row in relevant)
        issues = [issue for row in rows for issue in row['issues']]
        overlap = any('Overlapping' in issue['message'] for issue in issues)
        invalid = any('Stop precedes' in issue['message'] or 'Open record' in issue['message'] for issue in issues)
        # User reporting policy: no day entry means zero; malformed/missing readings remain qualified.
        grid_average = average('gridHours')
        gen_total, diesel_total = total('genHours'), total('dieselUsed')
        meters = sorted({r['source'].rsplit('-', 1)[-1] for r in records
                         if r['site'] == site and r['kind'] == 'grid' and r.get('source', '').rsplit('-', 1)[-1].isdigit()})
        result['sites'].append({'id': site, **info, 'meterNumbers': meters,
                               'generatorCapacity': '22 kVA' if site == 'PROJN01' else None,
                               'generatorCapacitySource': 'Weekly presentation template' if site == 'PROJN01' else None,
                               'days': rows, 'gridHours': total('gridHours'), 'genHours': gen_total,
                               'gridUsed': total('gridUsed'), 'dieselUsed': diesel_total,
                               'gridAdded': total('gridAdded'), 'dieselAdded': total('dieselAdded'),
                               'gridAdditionInferred': any(row['gridAdditionInferred'] for row in rows),
                               'dieselAdditionInferred': any(row['dieselAdditionInferred'] for row in rows),
                               'averageGridHours': grid_average,
                               'averageGenHours': average('genHours'),
                               'averageGridUsed': average('gridUsed', grid_usage_complete and not overlap and not invalid),
                               'averageDieselUsed': average('dieselUsed', diesel_complete and not overlap and not invalid),
                               'gridAvailabilityPercent': grid_average / 24 * 100 if grid_average is not None and not invalid else None,
                               'dieselLitresPerHour': diesel_total / gen_total if diesel_complete and not overlap and not invalid and gen_total else None,
                               'gridPartial': not grid_complete or invalid,
                               'genPartial': not gen_complete or invalid,
                               'gridUsagePartial': not grid_usage_complete or overlap or invalid,
                               'dieselUsagePartial': not diesel_complete or overlap or invalid,
                               'averageDays': average_days, 'zeroDays': sum(row['zeroAssumed'] for row in rows),
                               'daysWithGridRecords': sum(row['gridRecorded'] for row in rows),
                               'daysWithRecords': sum(row['logged'] for row in rows), 'issues': issues})
    return result
