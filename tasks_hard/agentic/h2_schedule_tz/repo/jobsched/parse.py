import re
from datetime import time

from .model import Schedule

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _hhmm(s: str) -> time:
    m = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", s)
    if not m:
        raise ValueError(f"bad time {s!r}, expected HH:MM")
    return time(int(m.group(1)), int(m.group(2)))


def parse(spec: str) -> Schedule:
    """Parse a schedule spec.

    Accepted forms (case-insensitive, single spaces):
      "daily HH:MM"          every day at HH:MM
      "weekly DAY HH:MM"     DAY is mon..sun
      "every Nm"             every N minutes, 1 <= N <= 1440
    Anything else raises ValueError.
    """
    parts = spec.strip().lower().split(" ")
    if len(parts) == 2 and parts[0] == "daily":
        return Schedule("daily", at=_hhmm(parts[1]))
    if len(parts) == 3 and parts[0] == "weekly" and parts[1] in WEEKDAYS:
        return Schedule("weekly", at=_hhmm(parts[2]), weekday=WEEKDAYS.index(parts[1]))
    if len(parts) == 2 and parts[0] == "every":
        m = re.fullmatch(r"(\d+)m", parts[1])
        if m and 1 <= int(m.group(1)) <= 1440:
            return Schedule("interval", minutes=int(m.group(1)))
    raise ValueError(f"unrecognised schedule {spec!r}")
