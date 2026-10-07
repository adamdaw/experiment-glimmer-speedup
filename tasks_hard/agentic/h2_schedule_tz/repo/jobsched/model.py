from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class Schedule:
    """A parsed schedule.

    kind:     "daily", "weekly" or "interval"
    at:       wall-clock time of day (daily/weekly only)
    weekday:  0=Monday .. 6=Sunday (weekly only)
    minutes:  interval length in minutes (interval only)
    """

    kind: str
    at: time | None = None
    weekday: int | None = None
    minutes: int | None = None


@dataclass
class Job:
    name: str
    spec: str  # the original spec text, e.g. "weekly mon 09:30"
    schedule: Schedule
