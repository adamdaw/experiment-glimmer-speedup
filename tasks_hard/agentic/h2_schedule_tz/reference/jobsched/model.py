from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class Schedule:
    kind: str
    at: time | None = None
    weekday: int | None = None
    minutes: int | None = None
    tz: str = "UTC"


@dataclass
class Job:
    name: str
    spec: str
    schedule: Schedule
