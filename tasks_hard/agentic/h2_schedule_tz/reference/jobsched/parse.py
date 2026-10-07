import re
from datetime import time
from zoneinfo import ZoneInfo

from .model import Schedule

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _hhmm(s: str) -> time:
    m = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", s)
    if not m:
        raise ValueError(f"bad time {s!r}, expected HH:MM")
    return time(int(m.group(1)), int(m.group(2)))


def check_zone(zone: str) -> str:
    try:
        ZoneInfo(zone)
    except Exception:
        raise ValueError(f"unknown time zone {zone!r}") from None
    return zone


def parse(spec: str) -> Schedule:
    raw = spec.strip().split(" ")
    tz = "UTC"
    if raw and raw[-1].lower().startswith("tz="):
        tz = check_zone(raw[-1][3:])
        raw = raw[:-1]
    parts = [p.lower() for p in raw]
    if any(p.startswith("tz=") for p in parts):
        raise ValueError("tz= must come last and at most once")
    if len(parts) == 2 and parts[0] == "daily":
        return Schedule("daily", at=_hhmm(parts[1]), tz=tz)
    if len(parts) == 3 and parts[0] == "weekly" and parts[1] in WEEKDAYS:
        return Schedule("weekly", at=_hhmm(parts[2]), weekday=WEEKDAYS.index(parts[1]), tz=tz)
    if len(parts) == 2 and parts[0] == "every":
        m = re.fullmatch(r"(\d+)m", parts[1])
        if m and 1 <= int(m.group(1)) <= 1440:
            return Schedule("interval", minutes=int(m.group(1)), tz=tz)
    raise ValueError(f"unrecognised schedule {spec!r}")
