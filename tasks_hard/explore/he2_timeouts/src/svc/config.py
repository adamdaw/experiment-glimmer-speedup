import os
from dataclasses import dataclass


@dataclass
class HttpSettings:
    connect_timeout: float = 3.0
    read_timeout: float | None = None   # None = wait as long as the server takes
    retries: int = 2


def load() -> HttpSettings:
    s = HttpSettings()
    if "SVC_READ_TIMEOUT" in os.environ:
        s.read_timeout = float(os.environ["SVC_READ_TIMEOUT"])
    return s
