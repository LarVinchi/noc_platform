"""UTC interval math. These metrics never infer outage coverage from silence."""
from datetime import datetime, timezone


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def union_seconds(intervals, start, end):
    start, end = utc(start), utc(end)
    clipped = sorted((max(utc(left), start), min(utc(right) if right else end, end))
                     for left, right in intervals if utc(left) < end and (right is None or utc(right) > start))
    total = 0.0
    previous = None
    for left, right in clipped:
        if right <= left:
            continue
        if previous is None:
            previous = [left, right]
        elif left <= previous[1]:
            previous[1] = max(previous[1], right)
        else:
            total += (previous[1] - previous[0]).total_seconds()
            previous = [left, right]
    return total + ((previous[1] - previous[0]).total_seconds() if previous else 0)


def deadline_state(deadline, completed, now, excluded=False):
    if excluded:
        return "excluded"
    if deadline is None:
        return "no_policy"
    if completed is not None and utc(completed) <= utc(now):
        return "met" if utc(completed) <= utc(deadline) else "breached"
    return "breached" if utc(now) > utc(deadline) else "pending"
