from datetime import datetime, timedelta, timezone

from .model import Schedule

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def next_run(schedule: Schedule, after: datetime) -> datetime:
    """Return the first run time strictly after `after`, as a UTC datetime."""
    if schedule.kind == "interval":
        step = timedelta(minutes=schedule.minutes)
        n = (after.replace(tzinfo=timezone.utc) - EPOCH) // step + 1
        return EPOCH + n * step
    day = after.date()
    for _ in range(8):
        candidate = datetime.combine(day, schedule.at, tzinfo=timezone.utc)
        if candidate > after.replace(tzinfo=timezone.utc) and (
            schedule.kind == "daily" or candidate.weekday() == schedule.weekday
        ):
            return candidate
        day += timedelta(days=1)
    raise AssertionError("unreachable")
