"""Retry policy: decides whether/how long to wait before another attempt."""
import random
import time
from email.utils import parsedate_to_datetime

IDEMPOTENT = {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}


class RetryPolicy:
    def __init__(self, settings, sleep=time.sleep, rng=random.random):
        self.s = settings
        self._sleep = sleep
        self._rng = rng

    def should_retry(self, method, attempt, *, status=None, exc=None):
        """attempt is 1-based: the attempt that just failed."""
        if attempt > self.s.max_retries:
            return False
        if exc is not None:
            # connection failures never reached the server: always safe to retry
            if isinstance(exc, ConnectionError):
                return True
            # a timeout might have been processed server-side
            if isinstance(exc, TimeoutError):
                return method.upper() in IDEMPOTENT
            return False
        if status == 429:
            return True
        return status in self.s.retry_on_status and method.upper() in IDEMPOTENT

    def delay(self, attempt, retry_after=None):
        if retry_after is not None and self.s.respect_retry_after:
            return min(self._parse_retry_after(retry_after), self.s.backoff_max)
        exp = self.s.backoff_base * (2 ** attempt)
        return self._rng() * min(exp, self.s.backoff_max)

    @staticmethod
    def _parse_retry_after(value):
        try:
            return float(value)
        except ValueError:
            when = parsedate_to_datetime(value)
            return max(0.0, when.timestamp() - time.time())

    def wait(self, attempt, retry_after=None):
        d = self.delay(attempt, retry_after)
        self._sleep(d)
        return d
