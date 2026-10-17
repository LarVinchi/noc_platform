import datetime as dt
import unittest
from app.services.energy_reporting import events_for, make_report, read_records, timestamp, union_seconds, window


def record(**changes):
    r = {'row': 1, 'site': 'PROJN01', 'source': 'PROJN01-04174881666', 'kind': 'grid',
         'start': dt.datetime(2026, 10, 16, 10), 'stop': dt.datetime(2026, 10, 16, 12),
         'status': 'ON', 'opening': 100., 'closing': 90., 'derived': False,
         'meterHours': None, 'operator': '', 'comment': ''}
    r.update(changes)
    return r


class ReportingTests(unittest.TestCase):
    def site(self, records, day='2026-10-16'):
        return make_report(records, day)['sites'][0]

    def test_excel_second_precision(self):
        self.assertEqual(timestamp('46311.999988425923'), dt.datetime(2026, 10, 16, 23, 59, 59))

    def test_exact_reporting_boundary(self):
        a, b = window('2026-10-16')
        self.assertEqual(a, dt.datetime(2026, 10, 15, 23, 59, 59))
        self.assertEqual((b-a).total_seconds(), 86400)
        marker = record(start=b, stop=b, status='Unit Closure', opening=10, closing=10)
        next_marker = record(row=2, start=b, stop=b, status='Unit Start', opening=100, closing=100)
        events = events_for([marker, next_marker])
        self.assertEqual(len(make_report([], '2026-10-16', events)['events']), 1)
        self.assertEqual(len(make_report([], '2026-10-17', events)['events']), 0)

    def test_union_does_not_double_count(self):
        a, b = window('2026-10-16')
        self.assertEqual(union_seconds([(a, b), (a+dt.timedelta(hours=1), b)]), 86400)

    def test_positive_usage_and_missing_is_not_zero(self):
        self.assertEqual(self.site([record()])['gridUsed'], 10)
        s = self.site([record(closing=None)])
        self.assertIsNone(s['gridUsed'])
        self.assertTrue(s['gridPartial'])

    def test_cross_boundary_usage_prorated(self):
        s = self.site([record(start=dt.datetime(2026, 10, 15, 22, 59, 59), stop=dt.datetime(2026, 10, 16, 0, 59, 59))])
        self.assertEqual(s['gridHours'], 1)
        self.assertEqual(s['gridUsed'], 5)

    def test_open_record_excluded(self):
        s = self.site([record(stop=None)])
        self.assertEqual(s['gridHours'], 0)
        self.assertTrue(s['issues'])

    def test_marker_interval_retained(self):
        s = self.site([record(status='Unit Closure')])
        self.assertEqual(s['gridHours'], 2)
        self.assertEqual(s['gridUsed'], 10)
        self.assertTrue(s['issues'])

    def test_off_not_counted(self):
        s = self.site([record(status='OFF')])
        self.assertEqual(s['gridHours'], 0)
        self.assertIsNone(s['gridUsed'])

    def test_topup_is_not_negative_consumption(self):
        first = record(stop=dt.datetime(2026,10,16,10), status='Unit Closure', opening=10, closing=10)
        second = record(row=2, stop=first['stop'], status='Unit Start', opening=110, closing=110)
        e = events_for([first, second])
        self.assertEqual(e[0]['amount'], 100)
        self.assertTrue(e[0]['confirmed'])
        self.assertIsNone(self.site([first, second])['gridUsed'])

    def test_within_session_increase_is_unresolved(self):
        s = self.site([record(closing=150)])
        self.assertIsNone(s['gridUsed'])
        self.assertTrue(s['gridPartial'])

    def test_overlap_hours_merged_and_consumption_flagged(self):
        s = self.site([record(), record(row=2)])
        self.assertEqual(s['gridHours'], 2)
        self.assertTrue(any('Overlapping' in i['message'] for i in s['issues']))



if __name__ == '__main__':
    unittest.main()
