"""Client configuration, resolved from defaults < config file < environment."""
import json
import os
from dataclasses import dataclass, field, fields

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.httpkit.json")


@dataclass
class RetrySettings:
    max_retries: int = 3            # retries AFTER the first attempt
    backoff_base: float = 0.5       # seconds
    backoff_max: float = 8.0        # seconds, cap on a single sleep
    retry_on_status: tuple = (502, 503, 504)
    respect_retry_after: bool = True


@dataclass
class ClientConfig:
    base_url: str = "http://localhost"
    timeout: float = 10.0
    retry: RetrySettings = field(default_factory=RetrySettings)


def _apply(obj, data):
    for f in fields(obj):
        if f.name in data:
            val = data[f.name]
            if isinstance(getattr(obj, f.name), RetrySettings) and isinstance(val, dict):
                _apply(getattr(obj, f.name), val)
            else:
                setattr(obj, f.name, val)


def load_config(path=None):
    cfg = ClientConfig()
    path = path or os.environ.get("HTTPKIT_CONFIG", DEFAULT_CONFIG_PATH)
    if os.path.exists(path):
        with open(path) as fh:
            _apply(cfg, json.load(fh))
    env = os.environ
    if "HTTPKIT_TIMEOUT" in env:
        cfg.timeout = float(env["HTTPKIT_TIMEOUT"])
    if "HTTPKIT_RETRIES" in env:
        cfg.retry.max_retries = int(env["HTTPKIT_RETRIES"])
    if "HTTPKIT_BACKOFF_BASE" in env:
        cfg.retry.backoff_base = float(env["HTTPKIT_BACKOFF_BASE"])
    return cfg
