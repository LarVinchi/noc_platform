import datetime as dt
import unittest
from app.services.energy_reporting import comment_addition, events_for, make_report, read_records, timestamp, union_seconds, window


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

    def test_explicit_refill_preserves_usage_and_positive_addition(self):
        r = record(kind='gen', source='PROJN01-GEN', closing=140, comment='Diesel refill of 50 litres')
        s = self.site([r])
        self.assertEqual(s['dieselUsed'], 10)
        self.assertEqual(s['dieselAdded'], 50)
        self.assertEqual(s['records'][0]['addition'], 50)
        self.assertFalse(s['dieselPartial'])

    def test_refill_can_happen_despite_net_decrease(self):
        s = self.site([record(kind='gen', source='PROJN01-GEN', closing=90, comment='Top-up of 50L')])
        self.assertEqual(s['dieselUsed'], 60)
        self.assertEqual(s['dieselAdded'], 50)

    def test_actual_workbook_quantity_first_comments_and_level_targets(self):
        for comment, quantity in [('50 liters top up',50),('25L Top up',25),('25 Litres geneator top up',25)]:
            self.assertEqual(comment_addition(record(kind='gen',comment=comment)),quantity)
        self.assertIsNone(comment_addition(record(kind='gen',comment='Diesel top up to 8.9cm')))
        self.assertIsNone(comment_addition(record(kind='gen',comment='Refill 50 litres then refill 25 litres')))

    def test_unknown_refill_quantity_and_boundary_assignment(self):
        s = self.site([record(kind='gen', source='PROJN01-GEN',comment='Diesel top up')])
        self.assertIsNone(s['dieselUsed'])
        crossing = record(kind='gen',source='PROJN01-GEN',start=dt.datetime(2026,10,15,22,59,59),
            stop=dt.datetime(2026,10,16,0,59,59),closing=140,comment='Refill 50 litres')
        self.assertEqual(self.site([crossing])['dieselAdded'],50)
        self.assertEqual(self.site([crossing],'2026-10-15')['dieselAdded'],0)
        self.assertEqual(self.site([crossing])['dieselUsed'],5)

    def test_ekedc_topup_and_independent_source_kinds(self):
        s = self.site([record(closing=140,comment='Top up of 50 kWh')])
        self.assertEqual(s['gridUsed'],10)
        self.assertEqual(s['gridAdded'],50)
        self.assertEqual(events_for([record(),record(kind='gen',opening=200,closing=190)]),[])

    def test_inferred_refill_is_visible_without_inventing_consumption(self):
        s = self.site([record(kind='gen', source='PROJN01-GEN', closing=140)])
        self.assertEqual(s['dieselAdded'], 40)
        self.assertIsNone(s['dieselUsed'])
        self.assertFalse(s['records'][0]['additionConfirmed'])

    def test_between_session_refill_comment_is_not_added_twice(self):
        first = record(kind='gen',source='PROJN01-GEN')
        second = record(row=2,kind='gen',source='PROJN01-GEN',start=first['stop'],stop=dt.datetime(2026,10,16,14),opening=140,closing=130,comment='Refill 50 litres')
        s = self.site([first,second])
        self.assertEqual(s['dieselAdded'],50)
        self.assertEqual(s['dieselUsed'],20)

    def test_planned_or_inconsistent_refill_does_not_create_usage(self):
        s = self.site([record(kind='gen',source='PROJN01-GEN',closing=140,comment='Planned refill of 50 litres')])
        self.assertIsNone(s['dieselUsed'])
        s = self.site([record(kind='gen',source='PROJN01-GEN',closing=160,comment='Refill of 50 litres')])
        self.assertIsNone(s['dieselUsed'])
        self.assertTrue(s['dieselPartial'])

    def test_overlap_hours_merged_and_consumption_flagged(self):
        s = self.site([record(), record(row=2)])
        self.assertEqual(s['gridHours'], 2)
        self.assertTrue(any('Overlapping' in i['message'] for i in s['issues']))



if __name__ == '__main__':
    unittest.main()
