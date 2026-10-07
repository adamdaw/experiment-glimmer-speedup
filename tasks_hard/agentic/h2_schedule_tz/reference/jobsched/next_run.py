from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .model import Schedule

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def next_run(schedule: Schedule, after: datetime) -> datetime:
    if after.tzinfo is None or after.utcoffset() is None:
        raise ValueError("after must be timezone-aware")
    if schedule.kind == "interval":
        step = timedelta(minutes=schedule.minutes)
        n = (after - EPOCH) // step + 1
        return EPOCH + n * step
    tz = ZoneInfo(schedule.tz)
    day = after.astimezone(tz).date() - timedelta(days=1)
    for _ in range(10):
        cand = datetime.combine(day, schedule.at).replace(tzinfo=tz, fold=0).astimezone(timezone.utc)
        if cand > after and (schedule.kind == "daily" or day.weekday() == schedule.weekday):
            return cand
        day += timedelta(days=1)
    raise AssertionError("unreachable")
