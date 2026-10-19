"""Monday–Sunday summaries using the existing daily interval calculations."""
import datetime as dt
from app.services.energy_reporting import make_report, events_for, SITES

WAT = dt.timezone(dt.timedelta(hours=1))


def weekly_report(records, week_start, now=None):
    start = dt.date.fromisoformat(week_start)
    if start.weekday() != 0:
        raise ValueError('Week must start on Monday')
    end = start + dt.timedelta(days=6)
    now = now or dt.datetime.now(WAT)
    elapsed = dt.datetime.combine(end, dt.time(23, 59, 59), WAT) <= now
    events = events_for(records)
    days = [make_report(records, (start + dt.timedelta(days=i)).isoformat(), events) for i in range(7)]
    result = {'weekStart': start.isoformat(), 'weekEnd': end.isoformat(), 'start': days[0]['start'],
              'end': days[-1]['end'], 'timezone': 'Africa/Lagos', 'elapsed': elapsed,
              'sites': [], 'events': [event for day in days for event in day['events']]}
    for index, (site, info) in enumerate(SITES.items()):
        rows = []
        for day in days:
            value = day['sites'][index]
            def observed(kind):
                return any(r['kind'] == kind and r['stop'] and r['clipStop'] and r['clipStop'] > r['clipStart']
                           and r['status'] in ('ON', 'OFF', 'Unit Closure', 'Unit Start', 'Diesel Cycle Closure', 'Diesel Cycle Start')
                           for r in value['records'])
            grid_known, gen_known = observed('grid'), observed('gen')
            logged = grid_known or gen_known
            grid_used = value['gridUsed']
            if grid_known and value['gridHours'] == 0 and grid_used is None and not value['gridPartial']:
                grid_used = 0
            diesel_used = value['dieselUsed']
            if logged and info['fuel'] == 'Diesel' and value['genHours'] == 0 and not value['dieselPartial']:
                diesel_used = 0
            rows.append({'date': day['date'], 'gridHours': value['gridHours'] if grid_known else None,
                         'genHours': value['genHours'] if logged else None, 'gridUsed': grid_used,
                         'dieselUsed': diesel_used if info['fuel'] == 'Diesel' else None,
                         'gridPartial': value['gridPartial'], 'dieselPartial': value['dieselPartial'],
                         'issues': value['issues'], 'logged': logged})
        def total(key):
            values = [row[key] for row in rows if row[key] is not None]
            return sum(values) if values else None
        def average(key, complete):
            value = total(key)
            return value / 7 if value is not None and complete and elapsed else None
        grid_complete = all(row['gridHours'] is not None for row in rows)
        gen_complete = all(row['logged'] for row in rows)
        grid_usage_complete = all(row['gridUsed'] is not None and not row['gridPartial'] for row in rows)
        diesel_complete = info['fuel'] == 'Diesel' and all(row['dieselUsed'] is not None and not row['dieselPartial'] for row in rows)
        issues = [issue for row in rows for issue in row['issues']]
        overlap = any('Overlapping' in issue['message'] for issue in issues)
        invalid = any('Stop precedes' in issue['message'] or 'Open record' in issue['message'] for issue in issues)
        # Logged-hour averages describe the completed intervals we can sum.
        # An unresolved record makes these provisional, but does not erase
        # seven recorded daily values. Never substitute zero for a missing day.
        grid_average = average('gridHours', grid_complete)
        gen_total, diesel_total = total('genHours'), total('dieselUsed')
        meters = sorted({r['source'].rsplit('-', 1)[-1] for r in records
                         if r['site'] == site and r['kind'] == 'grid' and r.get('source', '').rsplit('-', 1)[-1].isdigit()})
        result['sites'].append({'id': site, **info, 'meterNumbers': meters,
                               'generatorCapacity': '22 kVA' if site == 'PROJN01' else None,
                               'generatorCapacitySource': 'Weekly presentation template' if site == 'PROJN01' else None,
                               'days': rows, 'gridHours': total('gridHours'), 'genHours': gen_total,
                               'gridUsed': total('gridUsed'), 'dieselUsed': diesel_total,
                               'averageGridHours': grid_average,
                               'averageGenHours': average('genHours', gen_complete),
                               'averageGridUsed': average('gridUsed', grid_usage_complete and not overlap and not invalid),
                               'averageDieselUsed': average('dieselUsed', diesel_complete and not overlap and not invalid),
                               'gridAvailabilityPercent': grid_average / 24 * 100 if grid_average is not None and not invalid else None,
                               'dieselLitresPerHour': diesel_total / gen_total if diesel_complete and not overlap and not invalid and gen_total else None,
                               'gridPartial': not grid_complete or not elapsed or invalid,
                               'genPartial': not gen_complete or not elapsed or invalid,
                               'gridUsagePartial': not grid_usage_complete or overlap or invalid or not elapsed,
                               'dieselUsagePartial': not diesel_complete or overlap or invalid or not elapsed,
                               'daysWithGridRecords': sum(row['gridHours'] is not None for row in rows),
                               'daysWithRecords': sum(row['logged'] for row in rows), 'issues': issues})
    return result
