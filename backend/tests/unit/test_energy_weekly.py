import datetime as dt
import unittest
from app.services.energy_weekly import weekly_report, WAT


def records():
    result = []
    for index in range(7):
        start = dt.datetime(2026, 10, 4, 23, 59, 59) + dt.timedelta(days=index)
        for kind, hours, opening, closing in [('grid', 18, 200, 100), ('gen', 6, 100, 80)]:
            a = start if kind == 'grid' else start + dt.timedelta(hours=18)
            result.append(dict(row=len(result)+1, site='PROJN01', source='test', kind=kind,
                               start=a, stop=a+dt.timedelta(hours=hours), status='ON',
                               opening=opening, closing=closing, derived=False,
                               meterHours=None, operator='', comment=''))
    return result


class WeeklyTests(unittest.TestCase):
    def report(self, rows, now=None):
        return weekly_report(rows, '2026-10-05', now or dt.datetime(2026, 10, 12, tzinfo=WAT))

    def test_totals_and_seven_day_averages(self):
        report = self.report(records())
        site = report['sites'][0]
        self.assertEqual(site['gridHours'], 126)
        self.assertEqual(site['averageGridHours'], 18)
        self.assertEqual(site['gridAvailabilityPercent'], 75)
        self.assertEqual(site['genHours'], 42)
        self.assertEqual(site['gridUsed'], 700)
        self.assertEqual(site['dieselUsed'], 140)
        self.assertAlmostEqual(site['dieselLitresPerHour'], 140/42)
        self.assertEqual(report['start'], '2026-10-04T23:59:59')
        self.assertEqual(report['end'], '2026-10-11T23:59:59')

    def test_missing_day_is_zero_and_average_uses_seven_calendar_days(self):
        site = self.report(records()[:-2])['sites'][0]
        self.assertEqual(site['days'][-1]['gridHours'], 0)
        self.assertAlmostEqual(site['averageGridHours'], 108/7)
        self.assertEqual(site['zeroDays'], 1)
        self.assertFalse(site['gridPartial'])
        self.assertEqual(site['gridHours'], 108)

    def test_in_progress_average_counts_calendar_days_reached(self):
        site = self.report(records(), dt.datetime(2026, 10, 10, tzinfo=WAT))['sites'][0]
        self.assertEqual(site['averageDays'], 6)
        self.assertEqual(site['averageGridHours'], 15)
        self.assertIsNone(site['days'][-1]['gridHours'])  # Future Sunday is excluded.

    def test_missing_reading_preserves_hours(self):
        rows = records()
        rows[0]['closing'] = None
        site = self.report(rows)['sites'][0]
        self.assertEqual(site['averageGridHours'], 18)
        self.assertIsNone(site['averageGridUsed'])
        self.assertTrue(site['gridUsagePartial'])

    def test_empty_and_gas_never_invent_consumption(self):
        report = self.report([])
        for site in report['sites']:
            self.assertEqual(len(site['days']), 7)
            self.assertEqual(site['gridHours'], 0)
            self.assertEqual(site['averageGridHours'], 0)
            self.assertEqual(site['dieselUsed'], 0 if site['fuel'] == 'Diesel' else None)

    def test_open_record_preserves_provisional_seven_day_logged_average(self):
        rows = records()
        rows.append({**rows[-1], 'row': 100, 'stop': None})
        site = self.report(rows)['sites'][0]
        self.assertEqual(site['averageGridHours'], 18)
        self.assertEqual(site['averageGenHours'], 6)
        self.assertTrue(site['gridPartial'])
        self.assertTrue(site['genPartial'])
        self.assertIsNone(site['gridAvailabilityPercent'])
        self.assertIsNone(site['averageDieselUsed'])

    def test_no_completed_generator_runs_average_to_zero_on_recorded_days(self):
        rows = [r for r in records() if r['kind'] == 'grid']
        site = self.report(rows)['sites'][0]
        self.assertEqual(site['averageGenHours'], 0)
        self.assertEqual(site['averageGridHours'], 18)

    def test_open_record_keeps_average_visible_but_qualifies_zero_runtime(self):
        rows = records()[:-2]
        rows.append({**records()[-2], 'stop': None})
        site = self.report(rows)['sites'][0]
        self.assertAlmostEqual(site['averageGridHours'], 108/7)
        self.assertAlmostEqual(site['averageGenHours'], 36/7)
        self.assertTrue(site['gridPartial'])

    def test_monday_required(self):
        with self.assertRaises(ValueError):
            weekly_report([], '2026-10-06')

    def test_meter_identity_preserves_leading_zero_and_multiple_meters(self):
        rows = records()
        rows[0]['source'] = 'PROJN01-04174881666'
        rows[2]['source'] = 'PROJN01-12345678901'
        rows[1]['source'] = 'PROJN01-GEN'
        site = self.report(rows)['sites'][0]
        self.assertEqual(site['meterNumbers'], ['04174881666', '12345678901'])
        self.assertEqual(site['generatorCapacity'], '22 kVA')
        self.assertEqual(site['generatorCapacitySource'], 'Weekly presentation template')
