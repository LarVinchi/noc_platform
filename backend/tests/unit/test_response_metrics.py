from datetime import datetime, timedelta, timezone
import pytest
from app.services.response_metrics import union_seconds, deadline_state

START = datetime(2026,10,9,0,tzinfo=timezone.utc)


def test_overlap_is_counted_once_and_clipped_to_window():
    intervals = [(START-timedelta(minutes=30),START+timedelta(minutes=20)),
                 (START+timedelta(minutes=10),START+timedelta(minutes=40)),
                 (START+timedelta(minutes=50),None)]
    assert union_seconds(intervals,START,START+timedelta(hours=1)) == 50*60


def test_timezones_and_touching_intervals_have_no_double_count():
    wat = timezone(timedelta(hours=1))
    assert union_seconds([(START,START+timedelta(minutes=30)),
                          ((START+timedelta(minutes=30)).astimezone(wat),START+timedelta(hours=1))],START,START+timedelta(hours=1)) == 3600
    assert union_seconds([],START,START+timedelta(hours=1)) == 0


@pytest.mark.parametrize('offset,completion,expected',[
    (0,None,'pending'),(1,None,'breached'),(1,0,'met'),(2,1,'breached'),(-1,0,'pending')])
def test_deadline_boundary_and_historical_as_of(offset, completion, expected):
    assert deadline_state(START,START+timedelta(seconds=completion) if completion is not None else None,START+timedelta(seconds=offset)) == expected


def test_exclusion_and_absent_policy_are_explicit():
    assert deadline_state(None,None,START) == 'no_policy'
    assert deadline_state(START,None,START+timedelta(days=1),True) == 'excluded'
