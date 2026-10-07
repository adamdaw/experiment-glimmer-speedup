"""Thin HTTP client with retries."""
import logging
import urllib.error
import urllib.request

from .config import load_config
from .retry import RetryPolicy

log = logging.getLogger(__name__)


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self.body = body


class HttpClient:
    def __init__(self, config=None, transport=None):
        self.config = config or load_config()
        self.policy = RetryPolicy(self.config.retry)
        self._transport = transport or self._urllib_transport

    def _urllib_transport(self, method, url, body, headers, timeout):
        req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return Response(r.status, dict(r.headers), r.read())
        except urllib.error.HTTPError as e:
            return Response(e.code, dict(e.headers), e.read())
        except urllib.error.URLError as e:
            raise ConnectionError(str(e.reason)) from e
        except OSError as e:  # socket.timeout is an OSError subclass
            raise TimeoutError(str(e)) from e

    def request(self, method, path, body=None, headers=None, retry=None):
        """Send a request. ``retry`` optionally overrides settings for this call only,
        e.g. retry={"max_retries": 0}."""
        policy = self.policy
        if retry:
            merged = dict(vars(self.config.retry))
            merged.update(retry)
            policy = RetryPolicy(type(self.config.retry)(**merged))
        url = self.config.base_url.rstrip("/") + "/" + path.lstrip("/")
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self._transport(method, url, body, headers, self.config.timeout)
            except (ConnectionError, TimeoutError) as exc:
                if not policy.should_retry(method, attempt, exc=exc):
                    raise
                log.warning("%s %s failed (%s), retry #%d", method, url, exc, attempt)
                policy.wait(attempt)
                continue
            if resp.status < 400:
                return resp
            if not policy.should_retry(method, attempt, status=resp.status):
                return resp
            retry_after = resp.headers.get("Retry-After") if resp.status == 429 else None
            log.warning("%s %s -> %d, retry #%d", method, url, resp.status, attempt)
            policy.wait(attempt, retry_after)

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body=body, **kw)
