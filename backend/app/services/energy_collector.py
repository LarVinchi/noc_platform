"""Project confirmed trial observations into intervals; never infer equipment downtime."""
import datetime as dt
from collections import defaultdict
from app.services.energy_reporting import window, union_seconds

WAT = dt.timezone(dt.timedelta(hours=1))


def wall_time(value):
    return value.astimezone(WAT).replace(tzinfo=None)


def trial_records(events):
    sites = defaultdict(list)
    for event in events:
        sites[event.site].append(event)
    records = []
    for site, observations in sites.items():
        observations.sort(key=lambda e: e.revision)
        for index, event in enumerate(observations):
            following = observations[index + 1] if index + 1 < len(observations) else None
            for kind, state_field, reading_field in [('grid', 'grid', 'grid_balance'), ('gen', 'gen', 'diesel_litres')]:
                observation = event.observation
                opening = observation.get(reading_field)
                closing = following.observation.get(reading_field) if following else None
                records.append({
                    'row': event.revision, 'site': site, 'source': f'{site}-trial-{kind}', 'kind': kind,
                    'start': wall_time(event.effective_at), 'stop': wall_time(following.effective_at) if following else None,
                    'status': observation[state_field].upper(), 'opening': opening, 'closing': closing,
                    'derived': False, 'meterHours': None, 'operator': event.entered_by,
                    'comment': observation.get('comment', ''),
                })
    return sorted(records, key=lambda r: (r['start'], r['row'], r['kind']))


def trial_coverage(events, day):
    begin, end = window(day)
    sites = defaultdict(list)
    for event in events:
        sites[event.site].append(event)
    output = {}
    for site, values in sites.items():
        values.sort(key=lambda e: e.revision)
        covered, off = [], []
        for left, right in zip(values, values[1:]):
            a, b = max(begin, wall_time(left.effective_at)), min(end, wall_time(right.effective_at))
            if b <= a:
                continue
            if 'unknown' not in (left.observation['grid'], left.observation['gen']):
                covered.append((a, b))
                if left.observation['grid'] == left.observation['gen'] == 'off':
                    off.append((a, b))
        output[site] = {'confirmedNoGridOrGenHours': union_seconds(off)/3600,
                        'unconfirmedHours': 24 - union_seconds(covered)/3600,
                        'loadPowerStatus': 'unknown', 'batteryPresent': True}
    return output
