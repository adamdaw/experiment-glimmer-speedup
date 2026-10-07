# Blind grading packet (local-model eval, batch GS)

11 tasks: code reviews with planted bugs and explore/explain questions. Each task has the exact prompt, reference notes and several anonymous answers. Labels are shuffled independently per task, so A in one task is unrelated to A in another.

## Grading rubric (score each answer 1-5 on each axis)

| axis | 5 | 3 | 1 |
|---|---|---|---|
| **Correctness** | Every claim is right; the key conclusion (root cause / planted bugs / behavior) is correct | Main conclusion right but some wrong details | Main conclusion wrong |
| **Completeness** | Covers all key points in the reference notes that matter for the question | Covers about half | Misses most key points |
| **Groundedness** | Every claim is traceable to the provided code/log/doc; no invented functions, lines, config or events | Minor unsupported embellishment | Hallucinated facts that would mislead a reader |
| **Concision** | Tight, well organized, no padding; respects length limits | Some filler/repetition | Bloated or disorganized; key point buried |

Reference notes are guidance, not an exhaustive answer key: credit correct, grounded points that the notes don't list, and penalize confident wrong claims more than omissions. Grade each task's answers side by side. Labels are shuffled per task, so X in one task is unrelated to X in another.

Suggested scoresheet (copy per task): `task | label | correctness | completeness | groundedness | concision | notes`

For the two **cited-explore** tasks (`he1_cancel`, `he2_timeouts`), additionally count, per answer:
- **hallucinated citations**: a cited file or line that does not exist in the shown sources, or a citation used for code that is not shown;
- **wrong citations**: the line exists but does not support the claim it is attached to.
Groundedness for these two tasks should drop sharply with each hallucinated or wrong citation.

For review tasks, also count per answer: planted bugs found (0-2) and false alarms (claims that are wrong or not defects; real-but-unplanted issues are fine).


---

# Task `r1_report_cache` (review, standard set)

<details><summary>Full prompt given to the models (click to expand)</summary>

````text
You are reviewing a pull request. Context: Adds a TTL cache to report generation and a top_n helper.

Review the diff below for real defects: bugs, security problems, and behavior regressions. Do not report pure style preferences.

Output format: a numbered list, one issue per item, each formatted as
`N. [severity: high|medium|low] <file>:<line or function> - <what is wrong and why it matters> - <suggested fix>`
Report only issues you are confident are real; if there are none, say "No issues found."

```diff
--- a/reports/service.py
+++ b/reports/service.py
@@ -1,18 +1,39 @@
 import logging
+import time
 
 from .db import fetch_rows
 
-log = logging.getLogger(__name__)
+logger = logging.getLogger(__name__)
+
+_CACHE_TTL = 300
+_cache = {}
 
 
-def get_report(user_id, report_name, start, end):
-    rows = fetch_rows(user_id, report_name, start, end)
-    log.info("report %s rows=%d", report_name, len(rows))
-    return summarize(rows)
+def get_report(user_id: int, report_name: str, start: str, end: str) -> dict:
+    """Return the summarized report for one user, cached for _CACHE_TTL seconds."""
+    key = (report_name, start, end)
+    hit = _cache.get(key)
+    if hit and time.time() - hit[0] < _CACHE_TTL:
+        logger.debug("cache hit %s", key)
+        return hit[1]
+    rows = fetch_rows(user_id, report_name, start, end)
+    logger.info("report %s rows=%d", report_name, len(rows))
+    result = summarize(rows)
+    _cache[key] = (time.time(), result)
+    return result
 
 
-def summarize(rows):
-    total = sum(r["amount"] for r in rows)
-    return {"count": len(rows), "total": total, "avg": total / len(rows)}
+def summarize(rows: list[dict]) -> dict:
+    total = sum(r["amount"] for r in rows)
+    count = len(rows)
+    return {"count": count, "total": total, "avg": total / count if count else 0.0}
+
+
+def top_n(rows: list[dict], n: int = 5) -> list[dict]:
+    """Return the n rows with the largest amount, biggest first."""
+    return sorted(rows, key=lambda r: r["amount"])[:n]

```
````
</details>

### Reference notes

Planted bugs (the diff was constructed with these):
- Cache key omits user_id, so one user's cached report is served to other users (data leak / wrong data).
- top_n sorts ascending, returning the smallest amounts instead of the largest (needs reverse=True).


### Answer A

1. [severity: high] reports/service.py:get_report - Cache key is `(report_name, start, end)` and does not include `user_id`. `fetch_rows(user_id, ...)` is user-scoped but the cached result is shared across all users for the same report name/range, causing cross-user data leakage and incorrect results. Include `user_id` in the cache key, e.g. `key = (user_id, report_name, start, end)`.

2. [severity: medium] reports/service.py:top_n - The docstring states “Return the n rows with the largest amount, biggest first”, but implementation is `sorted(rows, key=lambda r: r["amount"])[:n]` which sorts ascending and returns the n smallest rows. This is a logic regression. Sort descending, e.g. `sorted(rows, key=lambda r: r["amount"], reverse=True)[:n]` or use `heapq.nlargest`.


### Answer B

1. [severity: high] reports/service.py:get_report - Cache key is `(report_name, start, end)` and does not include `user_id`. `fetch_rows(user_id, ...)` is user-scoped, so a cache hit for one user will return another user’s summarized report. This is a data leakage / privacy breach and a behavior regression. - Include `user_id` in the cache key, e.g. `key = (user_id, report_name, start, end)`, and use the same key for get/set.

2. [severity: high] reports/service.py:top_n - The implementation returns `sorted(rows, key=lambda r: r["amount"])[:n]`, which is ascending order and returns the n smallest rows. The docstring says “biggest first”. This is a functional bug that returns wrong results. - Sort descending: `sorted(rows, key=lambda r: r["amount"], reverse=True)[:n]`.

3. [severity: medium] reports/service.py:get_report - `_cache` is a module-level dict that only expires entries on read. Stale entries are never removed, so the cache can grow without bound over time. - Add eviction on write/read, e.g. purge expired entries or use a bounded TTL cache with max size.


### Answer C

1. [severity: high] reports/service.py:get_report - Cache key is `(report_name, start, end)` and does not include `user_id`. `fetch_rows(user_id, ...)` is user-specific, so different users sharing the same report_name/start/end will receive each other's cached summarized data. This is a data leakage / privacy breach and a behavior regression from the uncached version. - Include the user in the cache key, e.g. `key = (user_id, report_name, start, end)` and use the same key for get/store.

2. [severity: medium] reports/service.py:top_n - The implementation returns `sorted(rows, key=lambda r: r["amount"])[:n]`, which is ascending order and returns the n smallest rows. The docstring says “Return the n rows with the largest amount, biggest first”. This is a logic bug / behavior regression. - Sort descending: `sorted(rows, key=lambda r: r["amount"], reverse=True)[:n]`.


### Answer D

1. [severity: high] reports/service.py:get_report - Cache key is `(report_name, start, end)` and does not include `user_id`. The same cached summarized report will be returned to different users when they request the same report_name/start/end, causing cross-user data leakage. Suggested fix: include `user_id` in the cache key, e.g. `key = (user_id, report_name, start, end)`, and ensure the cache is per-user.

2. [severity: medium] reports/service.py:top_n - The implementation `sorted(rows, key=lambda r: r["amount"])[:n]` sorts ascending and returns the n smallest amounts. Docstring says “Return the n rows with the largest amount, biggest first”. This is a functional bug / behavior regression. Suggested fix: sort descending, e.g. `sorted(rows, key=lambda r: r["amount"], reverse=True)[:n]`.


### Answer E

1. [severity: high] reports/service.py:get_report - Cache key is `(report_name, start, end)` and does not include `user_id`. `fetch_rows(user_id, ...)` is user-specific, so a cached result for one user will be returned to a different user with the same report name and date range, causing data leakage and incorrect results. - Include `user_id` in the cache key, e.g. `key = (user_id, report_name, start, end)`, and use the same key for storage/lookup.

2. [severity: medium] reports/service.py:top_n - `sorted(rows, key=lambda r: r["amount"])[:n]` sorts ascending and returns the n smallest rows. The docstring states “Return the n rows with the largest amount, biggest first.” - Sort descending: `sorted(rows, key=lambda r: r["amount"], reverse=True)[:n]`.


---

# Task `r2_orders_route` (review, standard set)

<details><summary>Full prompt given to the models (click to expand)</summary>

````text
You are reviewing a pull request. Context: Adds pagination + status filter to GET /orders and a GET /orders/:id route.

Review the diff below for real defects: bugs, security problems, and behavior regressions. Do not report pure style preferences.

Output format: a numbered list, one issue per item, each formatted as
`N. [severity: high|medium|low] <file>:<line or function> - <what is wrong and why it matters> - <suggested fix>`
Report only issues you are confident are real; if there are none, say "No issues found."

```diff
--- a/src/routes/orders.js
+++ b/src/routes/orders.js
@@ -1,10 +1,34 @@
 const express = require('express');
-const router = express.Router();
 const db = require('../db');
+const { requireAuth } = require('../middleware/auth');
 
-router.get('/orders', async (req, res) => {
-  const rows = await db.query('SELECT * FROM orders WHERE customer_id = $1 ORDER BY created_at DESC', [req.user.id]);
-  res.json(rows);
+const router = express.Router();
+const PAGE_SIZE = 20;
+
+// GET /orders?page=1&status=shipped   (page is 1-based; page=1 is the newest 20 orders)
+router.get('/orders', requireAuth, async (req, res) => {
+  const page = parseInt(req.query.page || '1', 10);
+  const offset = page * PAGE_SIZE;
+  let sql = 'SELECT id, status, total_cents, created_at FROM orders WHERE customer_id = $1';
+  const params = [req.user.id];
+  if (req.query.status) {
+    sql += ` AND status = '${req.query.status}'`;
+  }
+  sql += ' ORDER BY created_at DESC LIMIT $2 OFFSET $3';
+  params.push(PAGE_SIZE, offset);
+  const rows = await db.query(sql, params);
+  res.json({ page, orders: rows });
+});
+
+router.get('/orders/:id', requireAuth, async (req, res) => {
+  const rows = await db.query(
+    'SELECT id, status, total_cents, created_at FROM orders WHERE id = $1 AND customer_id = $2',
+    [req.params.id, req.user.id]
+  );
+  if (rows.length === 0) {
+    return res.status(404).json({ error: 'not found' });
+  }
+  res.json(rows[0]);
 });
 
 module.exports = router;

```
````
</details>

### Reference notes

Planted bugs (the diff was constructed with these):
- req.query.status is interpolated into the SQL string -> SQL injection; should be a bound parameter.
- offset = page * PAGE_SIZE with 1-based page skips the first 20 orders; should be (page - 1) * PAGE_SIZE.


### Answer A

1. [high] src/routes/orders.js:router.get('/orders') - Status filter is interpolated directly into SQL with `sql += ` AND status = '${req.query.status}'``. This allows SQL injection and query manipulation via the `status` query parameter. - Use a parameterized placeholder for status, e.g. `sql += ' AND status = $2'` and push `req.query.status` onto `params`, and ideally whitelist allowed status values.

2. [high] src/routes/orders.js:router.get('/orders') - Pagination offset is calculated as `offset = page * PAGE_SIZE`. With 1-based paging this skips the first page: page=1 gives offset 20, so the first 20 newest orders are never returned and every page is shifted. - Calculate offset as `(page - 1) * PAGE_SIZE` and clamp page to >=1.

3. [medium] src/routes/orders.js:router.get('/orders') - `page` is parsed with `parseInt` but never validated. Non-numeric, zero or negative values produce `NaN`/negative offsets, causing DB errors or unintended results. - Validate `page` is a positive integer, default to 1 on invalid input, and reject/ clamp out-of-range values before building the query.


### Answer B

1. [severity: high] src/routes/orders.js:router.get('/orders') - Status filter is interpolated into SQL with `sql += ` AND status = '${req.query.status}'``. This is direct string interpolation, allowing SQL injection and bypass of the customer_id restriction. Suggested fix: use a parameterized placeholder, e.g. `sql += ' AND status = $2'` and push `req.query.status` onto `params`, then shift LIMIT/OFFSET placeholders to $3/$4.

2. [severity: high] src/routes/orders.js:router.get('/orders') - Pagination offset is computed as `offset = page * PAGE_SIZE`. With a 1-based page, page=1 yields offset 20 and skips the first page; every page is off-by-one and page=0 returns the second page. Suggested fix: validate `page` as a positive integer and compute `offset = (page - 1) * PAGE_SIZE`, defaulting to page 1 for invalid input.

3. [severity: medium] src/routes/orders.js:router.get('/orders') - `page` is parsed with `parseInt` but never validated. Non-numeric, negative or zero values produce `NaN` or negative offsets, causing a DB error / 500 instead of a clean 400. Suggested fix: validate `page = Math.max(1, parseInt(...))` or return 400 Bad Request when `Number.isNaN(page) || page < 1`.


### Answer C

1. [severity: high] src/routes/orders.js:router.get('/orders') - status filter is interpolated directly into SQL with `sql += \` AND status = '${req.query.status}'\``, allowing SQL injection and query breakage on quotes - use a parameterized placeholder for status, e.g. `AND status = $2` and push `req.query.status` onto `params`, then shift LIMIT/OFFSET to $3/$4.

2. [severity: medium] src/routes/orders.js:router.get('/orders') - pagination offset is computed as `offset = page * PAGE_SIZE`. With 1-based pages this skips the first page: page=1 yields offset 20. This is a behavior regression from the original un-paginated list - compute `offset = (Math.max(1, page) - 1) * PAGE_SIZE` and validate that `page` is a positive integer before use.


### Answer D

1. [severity: high] src/routes/orders.js:router.get('/orders') - Status filter is built by string interpolation `sql += \` AND status = '${req.query.status}'\``. This is SQL injection; an attacker can control the query text and bypass the `customer_id = $1` restriction or extract data. Use a parameterized predicate e.g. `sql += ' AND status = $2'` and push `req.query.status` onto `params`, ideally whitelisting against allowed status values.

2. [severity: high] src/routes/orders.js:router.get('/orders') - Pagination offset is calculated as `offset = page * PAGE_SIZE`. With 1-based paging this skips the first page: page=1 → offset=20, so the API returns rows 21-40 instead of 1-20. It also makes page=0 return the first page. Fix to `offset = (Math.max(1, page) - 1) * PAGE_SIZE`.

3. [severity: medium] src/routes/orders.js:router.get('/orders') - `page` is parsed with `parseInt` but never validated. Non-numeric, negative or zero values produce `NaN`/`negative` offset which is passed to `db.query` as `$3`, causing DB errors / 500s. Validate and clamp: ensure `page` is a positive integer, default to 1, and reject/ sanitize invalid values before building params.

4. [severity: medium] src/routes/orders.js:router.get('/orders') - Response shape changed from `res.json(rows)` to `res.json({ page, orders: rows })` and the projection changed from `SELECT *` to a fixed column list. Existing clients expecting an array at the top level will break. Confirm the API contract or version the change.


### Answer E

1. [severity: high] src/routes/orders.js:router.get('/orders') - Status filter is built by string interpolation `sql += ` AND status = '${req.query.status}'`` instead of a parameter. An attacker can inject SQL via `status` e.g. `shipped' OR '1'='1` to read orders belonging to other customers. - Use a parameterized query, e.g. `sql += ' AND status = $2'` and push `req.query.status` onto `params`, and adjust the LIMIT/OFFSET placeholders accordingly. Whitelist allowed status values as well.

2. [severity: high] src/routes/orders.js:router.get('/orders') - Pagination offset is computed as `const offset = page * PAGE_SIZE`. With 1-based pages this skips the first page: page=1 gives offset 20, page=2 gives offset 40, etc. Users never see the newest 20 orders and results are shifted. - Compute `offset = Math.max(0, (page - 1)) * PAGE_SIZE` after validating `page` is a positive integer, and reject/ coerce non-numeric or <1 values.


---

# Task `r3_charge_retry` (review, standard set)

<details><summary>Full prompt given to the models (click to expand)</summary>

````text
You are reviewing a pull request. Context: Adds retries around the gateway charge call.

Review the diff below for real defects: bugs, security problems, and behavior regressions. Do not report pure style preferences.

Output format: a numbered list, one issue per item, each formatted as
`N. [severity: high|medium|low] <file>:<line or function> - <what is wrong and why it matters> - <suggested fix>`
Report only issues you are confident are real; if there are none, say "No issues found."

```diff
--- a/payments/charge.py
+++ b/payments/charge.py
@@ -1,19 +1,37 @@
 import asyncio
 import logging
 
+from .errors import TransientGatewayError
+
 log = logging.getLogger(__name__)
+MAX_ATTEMPTS = 3
 
 
 class ChargeService:
-    def __init__(self, gateway, audit, ledger):
+    """Charges an account via the payment gateway, then audits and books it.
+
+    gateway.charge, audit.record and ledger.debit are all coroutines.
+    """
+
+    def __init__(self, gateway, audit, ledger):
         self.gateway = gateway
         self.audit = audit
         self.ledger = ledger
 
-    async def charge(self, account_id, amount_cents, idempotency_key):
-        result = await self.gateway.charge(account_id, amount_cents, idempotency_key)
-        await self.audit.record("charge", account_id, amount_cents, result.id)
-        await self.ledger.debit(account_id, amount_cents, ref=result.id)
-        return result
+    async def charge(self, account_id: str, amount_cents: int, idempotency_key: str):
+        if amount_cents <= 0:
+            raise ValueError("amount_cents must be positive")
+        result = None
+        for attempt in range(1, MAX_ATTEMPTS + 1):
+            try:
+                result = await self.gateway.charge(account_id, amount_cents, idempotency_key)
+            except TransientGatewayError as exc:
+                log.warning("charge attempt %d failed: %s", attempt, exc)
+                if attempt == MAX_ATTEMPTS:
+                    raise
+                await asyncio.sleep(0.2 * 2 ** attempt)
+        self.audit.record("charge", account_id, amount_cents, result.id)
+        await self.ledger.debit(account_id, amount_cents, ref=result.id)
+        log.info("charged %s %d (%s)", account_id, amount_cents, result.id)
+        return result

```
````
</details>

### Reference notes

Planted bugs (the diff was constructed with these):
- Loop has no break/return on success: the gateway is charged on every iteration (up to 3 times) even after a successful attempt.
- self.audit.record(...) is not awaited, so the coroutine never runs and the audit record is silently dropped.


### Answer A

1. [high] payments/charge.py:ChargeService.charge - `self.audit.record("charge", ...)` is called without `await`. `audit.record` is a coroutine per the class docstring, so the coroutine is created and discarded, the audit never runs and Python emits an unawaited-coroutine warning. This loses the audit trail and changes the ordering relative to `ledger.debit`. - Add `await` before the call, e.g. `await self.audit.record("charge", account_id, amount_cents, result.id)`, restoring the original awaited audit then debit order.

2. [high] payments/charge.py:ChargeService.charge - The retry `for` loop never breaks on success. After a successful `self.gateway.charge` the loop continues to the next attempt and calls the gateway again with the same `idempotency_key`. This causes unnecessary duplicate gateway calls and can overwrite a successful result and even raise a later transient error after a successful charge, preventing the subsequent audit/ledger from running. - Break out of the loop immediately after a successful charge, e.g. assign `result` then `break`, or move the success path out of the loop.


### Answer B

1. [high] payments/charge.py:charge - Successful `gateway.charge` does not break out of the retry loop. The loop continues for `MAX_ATTEMPTS` iterations even after a success, so a later transient failure will be logged and re-raised and a successful `result` from an earlier attempt can be discarded. This can cause duplicate gateway calls with the same idempotency key and can report failure to the caller despite a charge already having been made. Suggested fix: break / return immediately after a successful `await self.gateway.charge(...)`, so retries only happen on `TransientGatewayError`.

2. [high] payments/charge.py:charge - `self.audit.record(...)` is invoked without `await`. `audit.record` is a coroutine, so the call creates an un-awaited coroutine that is never executed, the audit entry is silently dropped, and any exception from auditing is lost. It also changes the original ordering where audit was awaited before ledger.debit. Suggested fix: `await self.audit.record("charge", account_id, amount_cents, result.id)` before awaiting `ledger.debit`, restoring the original awaited audit then debit sequence.


### Answer C

1. [severity: high] payments/charge.py:ChargeService.charge - `self.audit.record(...)` is called without `await`. The method is a coroutine in the original code and is now created but never scheduled. The audit entry will never be written, any exception from audit is lost, and the function can return before auditing is done. - Add `await` back: `await self.audit.record("charge", account_id, amount_cents, result.id)` and keep the original audit-before-ledger ordering.

2. [severity: high] payments/charge.py:ChargeService.charge - The retry loop never breaks on success. After a successful `gateway.charge` the loop continues to the next attempt, issuing additional gateway calls for the same `idempotency_key`. If a later attempt fails with `TransientGatewayError` a successful result from an earlier attempt is discarded and the exception is re-raised. This causes unnecessary load, can hit rate limits and can turn a successful charge into a failure. - Break out of the loop immediately after a successful charge, e.g. `result = await ...; break`, or return the result directly. Only retry when the call raises `TransientGatewayError`.


### Answer D

1. [high] payments/charge.py:ChargeService.charge - `self.audit.record("charge", ...)` is called without `await`. `audit.record` is a coroutine, so the audit is never scheduled/executed and a `RuntimeWarning: coroutine was never awaited` is emitted. This loses the audit trail and changes ordering relative to `ledger.debit`. - Add `await` before the call, e.g. `await self.audit.record("charge", account_id, amount_cents, result.id)`

2. [high] payments/charge.py:ChargeService.charge - the retry `for` loop does not break on a successful `gateway.charge`. After a success the loop continues to the next attempt and calls the gateway again with the same `idempotency_key` up to `MAX_ATTEMPTS` times. This adds unnecessary latency, load and extra gateway hits and can mask a transient failure on a later retry of an otherwise successful charge. - Break out of the loop immediately after a successful charge, e.g. `result = await self.gateway.charge(...); break` or use `while attempts < MAX_ATTEMPTS` with an early exit on success.


### Answer E

1. [high] payments/charge.py:ChargeService.charge - The retry loop never breaks on success so `gateway.charge` is invoked on every attempt up to `MAX_ATTEMPTS` even after a successful charge. With a shared `idempotency_key` this is wasteful and can hit rate limits; without perfect idempotency it risks duplicate charges and is a behavior regression from the original single-call semantics. - Break out of the loop immediately after a successful `await self.gateway.charge(...)`, e.g. `result = await ...; break` or return early, and only retry on `TransientGatewayError`.

2. [high] payments/charge.py:ChargeService.charge - `self.audit.record` is documented as a coroutine but is called without `await`. The coroutine is created and discarded, so the audit is never executed and any exception from auditing is silently lost, breaking the original post-charge audit guarantee. - Await the audit call as in the original implementation: `await self.audit.record("charge", account_id, amount_cents, result.id)` before proceeding to `ledger.debit`.

3. [medium] payments/charge.py:ChargeService.charge - Backoff uses `await asyncio.sleep(0.2 * 2 ** attempt)` with `attempt` starting at 1, giving first retry 0.4s, second 0.8s. This is an off-by-one from the usual `2**(attempt-1)` exponential backoff and changes retry timing. - Use `0.2 * 2 ** (attempt - 1)` or document the intended schedule.


---

# Task `e1_retry` (explore, standard set)

<details><summary>Full prompt given to the models (click to expand)</summary>

````text
How does request retry work in this codebase, and where is it configured? Specifically: which failures are retried (and for which HTTP methods), how many attempts happen with default settings, how the delay between attempts is computed, how configuration is resolved (defaults, file, environment, per-call), and how Retry-After is handled. Point out any bugs or places where the code and documentation disagree. Cite files/functions.

### README.md
```markdown
# httpkit

Retries are on by default (3 retries with exponential backoff).

Configure via `~/.httpkit.json`:

    {"timeout": 5, "retry": {"max_retries": 5, "backoff_base": 1.0}}

or environment variables: `HTTPKIT_TIMEOUT`, `HTTPKIT_MAX_RETRIES`, `HTTPKIT_BACKOFF_BASE`.
The server's `Retry-After` header is honored for 429 and 503 responses.
```

### httpkit/client.py
```python
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
```

### httpkit/config.py
```python
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
```

### httpkit/retry.py
```python
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
```

````
</details>

### Reference notes

Key facts a strong answer should contain (grounded in the code):
- Flow: HttpClient.request loops; transport raises ConnectionError/TimeoutError or returns Response; RetryPolicy.should_retry decides; RetryPolicy.wait sleeps delay().
- What is retried: ConnectionError always (any method, incl. POST); TimeoutError only for idempotent methods (GET/HEAD/OPTIONS/PUT/DELETE); HTTP 429 for ANY method (incl. POST); 502/503/504 (retry_on_status) only for idempotent methods; other errors / 4xx not retried (non-retryable error responses are returned, not raised).
- Attempts: max_retries=3 means up to 4 total attempts (should_retry returns False when attempt > max_retries; attempt is 1-based).
- Delay: "full jitter": rng() * min(backoff_base * 2**attempt, backoff_max). Because attempt starts at 1, the first retry's cap is 2*base = 1.0s (not base); caps 1,2,4 s with defaults; backoff_max 8s.
- Retry-After: only read for 429 (client passes it only when status == 429), capped at backoff_max, supports seconds or HTTP-date. README claims it's honored for 503 too -> doc/code mismatch.
- Config precedence: dataclass defaults < JSON file (path from HTTPKIT_CONFIG or ~/.httpkit.json) < env vars. Env var is HTTPKIT_RETRIES in code but README says HTTPKIT_MAX_RETRIES -> documented var silently ignored.
- Per-call override: request(..., retry={...}) merges dict over vars(settings) and builds a new RetrySettings/RetryPolicy (note: the override policy loses any custom sleep/rng injected into the default policy -- minor).
- Other notable issues: _urllib_transport maps ALL other OSError to TimeoutError (e.g. SSL/other socket errors become "timeouts"), and URLError wrapping a socket timeout is mapped to ConnectionError -> such timeouts would be retried even for POST (possible duplicate side effects). File config with JSON list for retry_on_status becomes a list (works with `in`). Retry-After given as HTTP-date in the past -> 0 delay.
- Where configured: config.py (RetrySettings defaults, load_config), retry.py (IDEMPOTENT set, status logic), client.py (per-call override, Retry-After only for 429).


### Answer A

**Retry flow**

`HttpClient.request` in `httpkit/client.py` does the loop

```python
attempt = 0
while True:
    attempt += 1
    resp = self._transport(...)
    ...
    if not policy.should_retry(method, attempt, status=resp.status):
        return resp
    ...
    policy.wait(attempt, retry_after)
```

`HttpClient.__init__` builds a `RetryPolicy(self.config.retry)`.  
`load_config` in `httpkit/config.py` builds the config

* defaults from the dataclasses
  `ClientConfig` / `RetrySettings`  
  `max_retries: int = 3  # retries AFTER the first attempt`
  `backoff_base: float = 0.5`
  `backoff_max: float = 8.0`
  `retry_on_status: tuple = (502, 503, 504)`
  `respect_retry_after: bool = True`
* file `~/.httpkit.json` or `HTTPKIT_CONFIG`, applied by `_apply`
* environment overrides afterwards

```
if "HTTPKIT_TIMEOUT" in env: cfg.timeout = float(...)
if "HTTPKIT_RETRIES" in env: cfg.retry.max_retries = int(...)
if "HTTPKIT_BACKOFF_BASE" in env: cfg.retry.backoff_base = float(...)
```

Defaults < file < env.

Per-call override:

```python
# httpkit/client.py HttpClient.request
if retry:
    merged = dict(vars(self.config.retry))
    merged.update(retry)
    policy = RetryPolicy(type(self.config.retry)(**merged))
```

So a call can pass `retry={"max_retries":0}` etc.

### What is retried

`RetryPolicy.should_retry` in `httpkit/retry.py`

```python
def should_retry(self, method, attempt, *, status=None, exc=None):
    if attempt > self.s.max_retries:          # 1-based
        return False
    if exc is not None:
        if isinstance(exc, ConnectionError):
            return True                       # always safe
        if isinstance(exc, TimeoutError):
            return method.upper() in IDEMPOTENT
        return False
    if status == 429:
        return True                           # no method check
    return status in self.s.retry_on_status and method.upper() in IDEMPOTENT
```

`IDEMPOTENT = {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}`

* Exceptions from `_urllib_transport`:
  * `ConnectionError` → retried for any method
  * `TimeoutError` → retried only for idempotent methods
  * other exceptions → no retry

* HTTP responses:
  * `429` → always retried, no idempotency check
  * `502,503,504` by default → retried only if method is idempotent
  * other 4xx/5xx → not retried

With the default `max_retries = 3` the loop runs attempt 1,2,3,4.  
`attempt > max_retries` stops, so 1 initial try + 3 retries = 4 attempts.

### Delay computation

`RetryPolicy.delay` / `wait`:

```python
def delay(self, attempt, retry_after=None):
    if retry_after is not None and self.s.respect_retry_after:
        return min(self._parse_retry_after(retry_after), self.s.backoff_max)
    exp = self.s.backoff_base * (2 ** attempt)
    return self._rng() * min(exp, self.s.backoff_max)
```

* If a `Retry-After` value is supplied and `respect_retry_after` is True, the wait is `min(parse(Retry-After), backoff_max)`. No jitter is applied in that branch.
* Otherwise exponential backoff with jitter: `random() * min(backoff_base * 2**attempt, backoff_max)`.

`_parse_retry_after` tries `float(value)` else `parsedate_to_datetime`.

`HttpClient.request` only extracts the header for 429:

```python
retry_after = resp.headers.get("Retry-After") if resp.status == 429 else None
policy.wait(attempt, retry_after)
```

So `Retry-After` is used only on 429 responses, and only if `respect_retry_after` is True.

### Configuration resolution

* Defaults → `ClientConfig` / `RetrySettings` dataclass defaults.
* File → `~/.httpkit.json` by default, overridable via `HTTPKIT_CONFIG` or `load_config(path=…)`. `_apply` recurses into `RetrySettings`.
* Environment → `HTTPKIT_TIMEOUT`, `HTTPKIT_RETRIES`, `HTTPKIT_BACKOFF_BASE` override the loaded values.
* Per-call → `request(..., retry={...})` merges into a new `RetryPolicy`.

### Disagreements / bugs

* **Env var name.** README says `HTTPKIT_MAX_RETRIES`. Code uses `HTTPKIT_RETRIES` in `httpkit/config.py:38`.
* **Retry-After scope.** README: “The server's `Retry-After` header is honored for 429 and 503 responses.” Code only reads the header when `resp.status == 429` `httpkit/client.py:44` and `should_retry` will retry 503 only if the method is idempotent and `503` is in `retry_on_status`. `Retry-After` is never used for 503.
* **429 method check.** `should_retry` returns `True` unconditionally for status 429. `retry_on_status` requires idempotency, but 429 does not. Non-idempotent POST will be retried on 429.
* **Backoff exponent off-by-one.** First retry uses `backoff_base * 2**1 = 2*base` instead of the more common `base * 2**0`. With defaults the first sleep is up to `0.5*2 = 1.0 s` rather than `0.5 s`.
* **Max retries wording.** Default comment says “retries AFTER the first attempt”. The README says “3 retries with exponential backoff” which matches, but the `attempt > max_retries` test makes the total attempts `max_retries + 1`. This is easy to misread.
* Minor: `delay` caps `Retry-After` with `backoff_max` via `min(..., backoff_max)`. README implies the header is honoured as-is.

These are the points where the implementation diverges from the documented behaviour.


### Answer B

**Retry flow**

`HttpClient.request`  *httpkit/client.py* `HttpClient.request`

```
attempt = 0
while True:
    attempt += 1
    resp = _transport(...)
    # exception path
    if not policy.should_retry(method, attempt, exc=exc): raise
    policy.wait(attempt)               # no Retry-After for exceptions
    continue

    # status path
    if resp.status < 400: return resp
    if not policy.should_retry(method, attempt, status=resp.status): return resp
    retry_after = resp.headers.get("Retry-After") if resp.status == 429 else None
    policy.wait(attempt, retry_after)
```

The policy is `RetryPolicy(self.config.retry)` created in `HttpClient.__init__`. A per-call
override

```python
merged = dict(vars(self.config.retry))
merged.update(retry)
policy = RetryPolicy(type(self.config.retry)(**merged))
```

creates a new `RetrySettings` for that call only.

* `RetryPolicy.should_retry`  *httpkit/retry.py*

```python
if attempt > self.s.max_retries: return False
if exc is not None:
    if isinstance(exc, ConnectionError): return True          # any method
    if isinstance(exc, TimeoutError):    return method.upper() in IDEMPOTENT
    return False
if status == 429: return True                                 # any method
return status in self.s.retry_on_status and method.upper() in IDEMPOTENT
```

`IDEMPOTENT = {"GET","HEAD","OPTIONS","PUT","DELETE"}`

So

* `ConnectionError` – always retried, method independent
* `TimeoutError` – retried only for idempotent methods
* `429 Too Many Requests` – always retried, method independent
* `502,503,504` – `self.s.retry_on_status` – retried only for idempotent methods

`attempt` is 1-based for the attempt that just failed. With the default
`max_retries = 3`  *httpkit/config.py* `RetrySettings.max_retries = 3  # retries AFTER the first attempt` the loop can run at most `1 + max_retries = 4` attempts; the `attempt > max_retries` guard stops further retries.

* `RetryPolicy.delay / wait`  *httpkit/retry.py*

```python
def delay(self, attempt, retry_after=None):
    if retry_after is not None and self.s.respect_retry_after:
        return min(self._parse_retry_after(retry_after), self.s.backoff_max)
    exp = self.s.backoff_base * (2 ** attempt)
    return self._rng() * min(exp, self.s.backoff_max)
```

* if a `Retry-After` value is supplied and `respect_retry_after` is true the
delay is `min(parse_retry_after, backoff_max)` with no jitter.
`_parse_retry_after` accepts a delta-seconds string or an HTTP-date.

* otherwise exponential backoff with jitter:
`delay ∈ [0, min(backoff_base * 2**attempt , backoff_max))`.

Defaults:

```
max_retries = 3
backoff_base = 0.5 s
backoff_max  = 8.0 s
retry_on_status = (502, 503, 504)
respect_retry_after = True
```

First retry → attempt=1 → exp = 0.5 * 2 = 1.0 s, jittered 0-1.0 s, etc.
The `2**attempt` is attempt-based, i.e. the first backoff is `2*base`
rather than the more common `base*2**(attempt-1)`.

### Configuration resolution

`load_config` *httpkit/config.py*

1. Defaults from `ClientConfig` / `RetrySettings` dataclasses.
2. File merge: `path = os.environ.get("HTTPKIT_CONFIG", "~/.httpkit.json")` → `_apply(cfg, json.load(fh))`. `_apply` recurses into `RetrySettings`.
3. Environment overrides, applied after the file:
   * `HTTPKIT_TIMEOUT` → `cfg.timeout`
   * `HTTPKIT_RETRIES` → `cfg.retry.max_retries`
   * `HTTPKIT_BACKOFF_BASE` → `cfg.retry.backoff_base`

Per-call override is the `retry` argument to `HttpClient.request`, which merges into a fresh `RetryPolicy` as shown above. No per-call override exists for `timeout` or `base_url`.

### Retry-After handling

* `HttpClient.request` only reads the header when `resp.status == 429`

```python
retry_after = resp.headers.get("Retry-After") if resp.status == 429 else None
policy.wait(attempt, retry_after)
```

`RetryPolicy.delay` will honour the value only if `respect_retry_after` is true, capping it at `backoff_max`.

### Disagreements / bugs

* README says env vars `HTTPKIT_TIMEOUT`, `HTTPKIT_MAX_RETRIES`, `HTTPKIT_BACKOFF_BASE`. Code uses `HTTPKIT_RETRIES` not `HTTPKIT_MAX_RETRIES`. *httpkit/config.py: load_config*.
* README says “The server's `Retry-After` header is honored for 429 and 503 responses.” Code only extracts and passes `Retry-After` for 429:
  `retry_after = resp.headers.get("Retry-After") if resp.status == 429 else None` *httpkit/client.py: request*. 503 will never get a Retry-After delay, only the normal exponential backoff.
* README documents 3 retries with exponential backoff, default config file example shows `backoff_base: 1.0`. Actual defaults are `max_retries=3`, `backoff_base=0.5` *httpkit/config.py: RetrySettings*.
* `should_retry` returns `True` for status 429 unconditionally, i.e. non-idempotent methods such as POST will be retried on 429. The 502/503/504 path correctly requires `method.upper() in IDEMPOTENT`.
* The exponential formula uses `2 ** attempt` rather than the conventional `2 ** (attempt-1)`, so the first backoff is twice the documented base.
* When a `Retry-After` is used the delay is `min(parse, backoff_max)` with no jitter, while normal backoff is jittered.

These are the points where the implementation diverges from the README and where off-by-one / naming inconsistencies exist.


### Answer C

**Configuration resolution**

* `httpkit/config.py` `ClientConfig` defaults

```python
base_url: str = "http://localhost"
timeout: float = 10.0
retry: RetrySettings = field(default_factory=RetrySettings)
```

`RetrySettings` defaults

```python
max_retries: int = 3            # retries AFTER the first attempt
backoff_base: float = 0.5
backoff_max: float = 8.0
retry_on_status: tuple = (502, 503, 504)
respect_retry_after: bool = True
```

`load_config` builds the object in the order

1. defaults → `cfg = ClientConfig()`
2. file → `~/.httpkit.json` or `HTTPKIT_CONFIG`, applied by `_apply`
3. environment → 

```
HTTPKIT_TIMEOUT   → cfg.timeout
HTTPKIT_RETRIES   → cfg.retry.max_retries
HTTPKIT_BACKOFF_BASE → cfg.retry.backoff_base
```

`httpkit/client.py` `HttpClient.__init__`

```python
self.config = config or load_config()
self.policy = RetryPolicy(self.config.retry)
```

Per-call override:

```python
def request(self, method, path, body=None, headers=None, retry=None):
    policy = self.policy
    if retry:
        merged = dict(vars(self.config.retry))
        merged.update(retry)
        policy = RetryPolicy(type(self.config.retry)(**merged))
```

So a call can do `client.request(..., retry={"max_retries":0})`. The merge is defaults < file < env < per-call.

README says env vars `HTTPKIT_TIMEOUT`, `HTTPKIT_MAX_RETRIES`, `HTTPKIT_BACKOFF_BASE`. The code uses `HTTPKIT_RETRIES` not `HTTPKIT_MAX_RETRIES`. Disagreement.

**Attempts with defaults**

`max_retries = 3` is *retries after the first attempt*.  
`RetryPolicy.should_retry` is 1-based:

```python
if attempt > self.s.max_retries:
    return False
```

First try = attempt 1, last retry = attempt 4. 4 attempts total.

**What is retried and for which methods**

`httpkit/retry.py` `IDEMPOTENT = {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}`

`RetryPolicy.should_retry`

* exc is not None
  * `ConnectionError` → `return True` unconditionally, any method
  * `TimeoutError` → `return method.upper() in IDEMPOTENT`
  * else → `False`
* status
  * `status == 429` → `return True` unconditionally, method ignored
  * else → `status in self.s.retry_on_status and method.upper() in IDEMPOTENT`
    i.e. 502, 503, 504 only for idempotent methods.

`httpkit/client.py` `HttpClient.request`

```python
except (ConnectionError, TimeoutError) as exc:
    if not policy.should_retry(method, attempt, exc=exc):
        raise
    ...
    policy.wait(attempt)
    continue

if resp.status < 400:
    return resp
if not policy.should_retry(method, attempt, status=resp.status):
    return resp
retry_after = resp.headers.get("Retry-After") if resp.status == 429 else None
...
policy.wait(attempt, retry_after)
```

So:
* Connection failures → always retried.
* Timeouts → retried only for idempotent methods.
* 429 → always retried, any method.
* 502/503/504 → retried only for idempotent methods.

**Delay computation**

`RetryPolicy.delay`

```python
if retry_after is not None and self.s.respect_retry_after:
    return min(self._parse_retry_after(retry_after), self.s.backoff_max)
exp = self.s.backoff_base * (2 ** attempt)
return self._rng() * min(exp, self.s.backoff_max)
```

* With no `Retry-After`: exponential backoff with jitter  
  `delay = random() * min(backoff_base * 2**attempt , backoff_max)`  
  first failure `attempt=1` → `base * 2`. The usual `2**(attempt-1)` is off-by-one.
* `backoff_max = 8.0 s` caps a single sleep.
* `wait` calls `self._sleep(d)`.

`_parse_retry_after` accepts a numeric seconds string or an HTTP-date via `email.utils.parsedate_to_datetime`, returns `max(0, when - now)`.

**Retry-After handling**

README:

> The server's `Retry-After` header is honored for 429 and 503 responses.

Code:

* `should_retry` returns True for 429 unconditionally and for 503 only if idempotent.
* `HttpClient.request` only extracts the header for 429:

```python
retry_after = resp.headers.get("Retry-After") if resp.status == 429 else None
policy.wait(attempt, retry_after)
```

503 is never passed to `wait`, so `Retry-After` is ignored for 503.  
Also `delay` will use the parsed `Retry-After` value capped to `backoff_max` with no jitter, while normal backoff uses jitter.

**Bugs / doc-code disagreements**

* Env var name: README documents `HTTPKIT_MAX_RETRIES`; `config.load_config` reads `HTTPKIT_RETRIES`.
* `Retry-After` documented for 429 *and* 503, implemented for 429 only in `HttpClient.request`.
* Backoff exponent is `2 ** attempt` not `2 ** (attempt-1)`. First retry uses `base*2` instead of `base`.
* 429 retry bypasses idempotency check, while 502/503/504 require idempotent methods. Documentation does not call this out.
* `ConnectionError` is retried for any method, even non-idempotent, which can be unsafe.
* `RetryPolicy.delay` returns `min(parse, backoff_max)` for `Retry-After` but the README implies the header is honored; the cap to `backoff_max` is undocumented.

Files referenced: `README.md`, `httpkit/client.py` `HttpClient.__init__`/`HttpClient.request`, `httpkit/config.py` `ClientConfig`/`RetrySettings`/`load_config`/`_apply`, `httpkit/retry.py` `RetryPolicy.should_retry`/`delay`/`wait`/`_parse_retry_after`.


### Answer D

**Configuration resolution**

* Defaults are the dataclass values in `httpkit/config.py` `ClientConfig` / `RetrySettings`
  * `base_url="http://localhost"`, `timeout=10.0`
  * `RetrySettings.max_retries=3   # retries AFTER the first attempt`
    `backoff_base=0.5`, `backoff_max=8.0`
    `retry_on_status=(502,503,504)`, `respect_retry_after=True`
* `load_config` builds `cfg = ClientConfig()` then `_apply(cfg, json.load(fh))` from
  `path or os.environ.get("HTTPKIT_CONFIG", DEFAULT_CONFIG_PATH)` `~/.httpkit.json`
  and finally overrides from environment:

  ```python
  if "HTTPKIT_TIMEOUT" in env: cfg.timeout = float(env["HTTPKIT_TIMEOUT"])
  if "HTTPKIT_RETRIES" in env: cfg.retry.max_retries = int(env["HTTPKIT_RETRIES"])
  if "HTTPKIT_BACKOFF_BASE" in env: cfg.retry.backoff_base = float(env["HTTPKIT_BACKOFF_BASE"])
  ```
  `httpkit/config.py:load_config`

  Order is defaults < file < environment, as documented in the module docstring.
  Per-call override exists in `HttpClient.request`:

  ```python
  if retry:
      merged = dict(vars(self.config.retry))
      merged.update(retry)
      policy = RetryPolicy(type(self.config.retry)(**merged))
  ```
  `httpkit/client.py:HttpClient.request`

**Which failures are retried and for which methods**

`RetryPolicy.should_retry(method, attempt, *, status=None, exc=None)` `httpkit/retry.py:RetryPolicy.should_retry`

* `attempt > self.s.max_retries` → `False`. `attempt` is 1-based, the attempt that just failed.
* Exception case
  * `ConnectionError` → `True` unconditionally, method independent.
  * `TimeoutError` → `True` only if `method.upper() in IDEMPOTENT`
  * other exceptions → `False`
* Status case
  * `status == 429` → `True` unconditionally, no idempotency check.
  * otherwise `status in self.s.retry_on_status and method.upper() in IDEMPOTENT`
    `IDEMPOTENT = {"GET","HEAD","OPTIONS","PUT","DELETE"}` `httpkit/retry.py:IDEMPOTENT`

With defaults `retry_on_status = (502,503,504)`. So 502/503/504 are retried only for idempotent methods, 429 is retried for any method, connection errors are always retried, timeouts only for idempotent methods.

**Number of attempts**

`max_retries` is “retries AFTER the first attempt”. The loop in
`HttpClient.request` increments `attempt` then tries:

```python
attempt += 1
...
if not policy.should_retry(method, attempt, exc=exc): raise
...
if not policy.should_retry(method, attempt, status=resp.status): return resp
```

`should_retry` returns `False` when `attempt > max_retries`. Default `max_retries=3`
→ attempts 1,2,3,4 → 3 retries, 4 total attempts.

**Delay computation**

`RetryPolicy.delay(attempt, retry_after=None)` `httpkit/retry.py:RetryPolicy.delay`

* If `retry_after is not None and self.s.respect_retry_after`:
  `return min(self._parse_retry_after(retry_after), self.s.backoff_max)`
  `_parse_retry_after` tries `float(value)` else `parsedate_to_datetime(value)` → seconds until the date.
* Else:
  `exp = self.s.backoff_base * (2 ** attempt)`
  `return self._rng() * min(exp, self.s.backoff_max)`

`HttpClient.request` calls `policy.wait(attempt, retry_after)` and
`policy.wait(attempt)` for exceptions. `wait` sleeps for `delay` and returns it.

With defaults `backoff_base=0.5`, first retry `attempt=1` → `exp =0.5*2=1.0` → jittered `0-1.0 s`, capped by `backoff_max=8.0`. The formula uses `2**attempt` not `2**(attempt-1)`, i.e. one step larger than the classic exponential backoff.

**Retry-After handling**

`HttpClient.request`:

```python
retry_after = resp.headers.get("Retry-After") if resp.status == 429 else None
...
policy.wait(attempt, retry_after)
```

Only 429 responses have the header looked up and passed to `delay`. `delay` will honour it when `respect_retry_after` is true, capped to `backoff_max`. No jitter is applied to a Retry-After delay.

**Disagreements / bugs**

* README vs code environment variable name
  * README: `HTTPKIT_MAX_RETRIES`
  * code: `HTTPKIT_RETRIES` `httpkit/config.py:load_config`. The documented variable does not work.
* README vs code Retry-After scope
  * README: “The server's `Retry-After` header is honored for 429 and 503 responses.”
  * code only extracts and passes `Retry-After` for status 429:
    `retry_after = resp.headers.get("Retry-After") if resp.status == 429 else None`
    `httpkit/client.py:HttpClient.request`. 503 retries use normal exponential backoff.
* 429 retry is unconditional
  * `should_retry` returns `True` for `status == 429` without checking `IDEMPOTENT`. 502/503/504 require idempotent methods, 429 does not. This is inconsistent with the idempotency guard used elsewhere.
* Retry-After capping undocumented
  * `delay` returns `min(parse_retry_after, backoff_max)`. README does not mention the cap.
* Off-by-one backoff
  * `exp = backoff_base * 2**attempt` with 1-based attempt gives first backoff `base*2`. Typical exponential backoff would use `2**(attempt-1)`.
* Jitter only on exponential path
  * When a Retry-After is used the jitter `self._rng()` is not applied, only the capped value is returned.

These are the places that implement retry: `httpkit/retry.py RetryPolicy.should_retry/delay/wait`, `httpkit/client.py HttpClient.request`, `httpkit/config.py load_config/_apply`, and the defaults documented in `README.md`.


### Answer E

**Configuration resolution**

* Defaults are in the dataclasses
`httpkit/config.py` `ClientConfig`
```python
base_url: str = "http://localhost"
timeout: float = 10.0
retry: RetrySettings = field(default_factory=RetrySettings)
```
`RetrySettings`
```python
max_retries: int = 3            # retries AFTER the first attempt
backoff_base: float = 0.5
backoff_max: float = 8.0
retry_on_status: tuple = (502, 503, 504)
respect_retry_after: bool = True
```

* File then environment
`httpkit/config.py` `load_config`
```python
cfg = ClientConfig()
path = path or os.environ.get("HTTPKIT_CONFIG", DEFAULT_CONFIG_PATH)
if os.path.exists(path): _apply(cfg, json.load(fh))
...
if "HTTPKIT_TIMEOUT" in env: cfg.timeout = ...
if "HTTPKIT_RETRIES" in env: cfg.retry.max_retries = ...
if "HTTPKIT_BACKOFF_BASE" in env: cfg.retry.backoff_base = ...
```
Resolution order is defaults < `~/.httpkit.json` / `HTTPKIT_CONFIG` < env.

* Per-call override
`httpkit/client.py` `HttpClient.request`
```python
policy = self.policy
if retry:
    merged = dict(vars(self.config.retry))
    merged.update(retry)
    policy = RetryPolicy(type(self.config.retry)(**merged))
```
A dict passed as `retry=` is merged on top of the config `RetrySettings` and a new `RetryPolicy` is used for that call only.

Documentation mismatch: README says env vars `HTTPKIT_MAX_RETRIES`, `HTTPKIT_BACKOFF_BASE`, `HTTPKIT_TIMEOUT`. The code uses `HTTPKIT_RETRIES` for max retries, not `HTTPKIT_MAX_RETRIES`. `httpkit/config.py:load_config`.

**What is retried**

`httpkit/retry.py` `RetryPolicy.should_retry(method, attempt, *, status=None, exc=None)`  
attempt is 1-based for the attempt that just failed and `attempt > self.s.max_retries` aborts first.

* Exceptions
  * `ConnectionError` → `return True` – always retried, no method check.
  * `TimeoutError` → `return method.upper() in IDEMPOTENT`
  * other exc → `False`

* HTTP status
  * `status == 429` → `return True` – retried for any method.
  * otherwise `status in self.s.retry_on_status and method.upper() in IDEMPOTENT`
  `IDEMPOTENT = {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}`

`httpkit/client.py` `HttpClient.request`
```python
except (ConnectionError, TimeoutError) as exc:
    if not policy.should_retry(method, attempt, exc=exc): raise
    ...
    policy.wait(attempt)
    continue
...
if resp.status < 400: return resp
if not policy.should_retry(method, attempt, status=resp.status): return resp
retry_after = resp.headers.get("Retry-After") if resp.status == 429 else None
...
policy.wait(attempt, retry_after)
```
So 2xx/3xx is returned immediately, 4xx other than 429 is returned immediately, 5xx in `retry_on_status` is retried only for idempotent methods.

**Number of attempts**

Default `max_retries = 3` is *retries after the first attempt*.

Loop in `HttpClient.request` increments `attempt` then tries. `should_retry` rejects when `attempt > max_retries`.  
Hence default total attempts = `max_retries + 1 = 4`.

**Delay computation**

`httpkit/retry.py` `RetryPolicy.delay(attempt, retry_after=None)` and `wait`

* If a `Retry-After` value is supplied and `respect_retry_after` is True:
  ```python
  return min(self._parse_retry_after(retry_after), self.s.backoff_max)
  ```
  `_parse_retry_after` tries `float(value)` else parses an HTTP date with `email.utils.parsedate_to_datetime`.

* Otherwise exponential backoff with jitter:
  ```python
  exp = self.s.backoff_base * (2 ** attempt)
  return self._rng() * min(exp, self.s.backoff_max)
  ```
  `attempt` is 1-based for the failed attempt, so first retry uses `base * 2**1`. The value is multiplied by `random.random()` → 0-1 jitter and capped by `backoff_max` before jitter.

`HttpClient.request` calls `policy.wait(attempt)` for exception retries and `policy.wait(attempt, retry_after)` for status retries.

**Retry-After handling**

Code only extracts the header for 429:
```python
retry_after = resp.headers.get("Retry-After") if resp.status == 429 else None
```
and passes it to `policy.wait`. The policy will honour it if `respect_retry_after` is True, capped to `backoff_max`.

README says: *“The server's `Retry-After` header is honored for 429 and 503 responses.”*  
Implementation honors it only for 429. 503 is in `retry_on_status` and is retried for idempotent methods but never uses `Retry-After`.

**Bugs / doc-code disagreements**

* Env var name: README documents `HTTPKIT_MAX_RETRIES`; code checks `HTTPKIT_RETRIES`. `httpkit/config.py:load_config`.
* Retry-After scope: README claims 429 and 503; code uses it only when `resp.status == 429`. `httpkit/client.py:HttpClient.request`.
* Backoff exponent off-by-one: first retry delay uses `backoff_base * 2**1` instead of the more common `backoff_base * 2**(attempt-1)`. `httpkit/retry.py:RetryPolicy.delay`.
* 429 is retried unconditionally, even for non-idempotent methods such as POST, while other retriable statuses require idempotency. `httpkit/retry.py:RetryPolicy.should_retry`.
* `ConnectionError` is retried unconditionally irrespective of method, which is intentional but worth noting.
* `Retry-After` is capped to `backoff_max` with `min`, so a server-requested longer wait is silently shortened.
* Per-call `retry` override rebuilds a `RetrySettings` from `vars(self.config.retry)`. Nested settings work, but the merge is shallow and does not allow overriding `retry_on_status` with a non-tuple without constructing a proper `RetrySettings`.

These are the points where the current implementation diverges from the README and where the retry behaviour is defined.


---

# Task `e2_log` (explore, standard set)

<details><summary>Full prompt given to the models (click to expand)</summary>

````text
Below is a 300-line excerpt of production logs from around an incident in which checkout requests started failing. Summarize what happened (timeline) and identify the most likely root cause, citing the specific log evidence. Separate the root cause from symptoms and from unrelated noise, and suggest the immediate mitigation and the real fix.

```
2026-09-14T13:59:00.000Z INFO  [checkout-svc] starting checkout-svc version=2.13.4 pid=41 pool.max=20 pool.acquire_timeout_ms=5000
2026-09-14T13:59:00.000Z WARN  [metrics-exporter] TLS certificate for metrics.internal expires in 29 days (2026-10-13)
2026-09-14T13:59:02.826Z INFO  [checkout-svc] req=r01001 path=/orders status=200 dur=32ms
2026-09-14T13:59:04.622Z INFO  [checkout-svc] req=r01002 path=/checkout status=200 dur=213ms
2026-09-14T13:59:08.509Z INFO  [checkout-svc] req=r01003 path=/products status=200 dur=74ms
2026-09-14T13:59:10.162Z INFO  [checkout-svc] req=r01004 path=/orders status=200 dur=37ms
2026-09-14T13:59:12.647Z INFO  [checkout-svc] req=r01005 path=/orders status=200 dur=35ms
2026-09-14T13:59:16.463Z INFO  [checkout-svc] req=r01006 path=/cart status=200 dur=35ms
2026-09-14T13:59:20.326Z INFO  [checkout-svc] req=r01007 path=/checkout status=200 dur=176ms
2026-09-14T13:59:22.016Z INFO  [checkout-svc] req=r01008 path=/cart status=200 dur=94ms
2026-09-14T13:59:25.232Z INFO  [checkout-svc] req=r01009 path=/checkout status=200 dur=266ms
2026-09-14T13:59:27.995Z INFO  [checkout-svc] req=r01010 path=/products status=200 dur=66ms
2026-09-14T13:59:29.917Z INFO  [checkout-svc] req=r01011 path=/products status=200 dur=68ms
2026-09-14T13:59:32.942Z INFO  [sqlpool] pool stats active=1 idle=19 waiting=0 max=20
2026-09-14T13:59:36.685Z INFO  [checkout-svc] req=r01012 path=/products status=200 dur=35ms
2026-09-14T13:59:40.720Z INFO  [checkout-svc] req=r01013 path=/products status=200 dur=156ms
2026-09-14T13:59:43.971Z INFO  [checkout-svc] req=r01014 path=/orders status=200 dur=136ms
2026-09-14T13:59:46.952Z INFO  [checkout-svc] req=r01015 path=/products status=200 dur=66ms
2026-09-14T13:59:49.451Z INFO  [checkout-svc] req=r01016 path=/cart status=200 dur=154ms
2026-09-14T13:59:52.978Z INFO  [checkout-svc] req=r01017 path=/products status=200 dur=134ms
2026-09-14T13:59:55.657Z INFO  [checkout-svc] req=r01018 path=/checkout status=200 dur=150ms
2026-09-14T13:59:59.253Z INFO  [checkout-svc] req=r01019 path=/products status=200 dur=107ms
2026-09-14T14:00:01.375Z INFO  [checkout-svc] req=r01020 path=/orders status=200 dur=30ms
2026-09-14T14:00:03.192Z INFO  [sqlpool] pool stats active=3 idle=17 waiting=0 max=20
2026-09-14T14:00:07.039Z INFO  [checkout-svc] req=r01021 path=/products status=200 dur=100ms
2026-09-14T14:00:09.932Z INFO  [checkout-svc] req=r01022 path=/products status=200 dur=147ms
2026-09-14T14:00:13.807Z INFO  [checkout-svc] req=r01023 path=/checkout status=200 dur=335ms
2026-09-14T14:00:15.690Z INFO  [checkout-svc] req=r01024 path=/orders status=200 dur=36ms
2026-09-14T14:00:17.438Z INFO  [checkout-svc] req=r01025 path=/cart status=200 dur=134ms
2026-09-14T14:00:20.103Z INFO  [checkout-svc] req=r01026 path=/products status=200 dur=108ms
2026-09-14T14:00:21.695Z INFO  [checkout-svc] req=r01027 path=/cart status=200 dur=63ms
2026-09-14T14:00:25.697Z INFO  [checkout-svc] req=r01028 path=/checkout status=200 dur=175ms
2026-09-14T14:00:28.374Z INFO  [checkout-svc] req=r01029 path=/cart status=200 dur=121ms
2026-09-14T14:00:31.475Z INFO  [checkout-svc] req=r01030 path=/orders status=200 dur=40ms
2026-09-14T14:00:33.656Z INFO  [sqlpool] pool stats active=2 idle=18 waiting=0 max=20
2026-09-14T14:00:36.801Z INFO  [checkout-svc] req=r01031 path=/cart status=200 dur=130ms
2026-09-14T14:00:40.554Z INFO  [checkout-svc] req=r01032 path=/orders status=200 dur=111ms
2026-09-14T14:00:43.612Z INFO  [checkout-svc] req=r01033 path=/cart status=200 dur=41ms
2026-09-14T14:00:45.833Z INFO  [checkout-svc] req=r01034 path=/products status=200 dur=79ms
2026-09-14T14:00:47.382Z INFO  [checkout-svc] req=r01035 path=/products status=200 dur=66ms
2026-09-14T14:00:49.958Z INFO  [checkout-svc] req=r01036 path=/cart status=200 dur=127ms
2026-09-14T14:00:53.647Z INFO  [checkout-svc] req=r01037 path=/products status=200 dur=101ms
2026-09-14T14:00:55.661Z INFO  [checkout-svc] req=r01038 path=/products status=200 dur=33ms
2026-09-14T14:00:59.031Z INFO  [checkout-svc] req=r01039 path=/products status=200 dur=120ms
2026-09-14T14:01:02.161Z INFO  [checkout-svc] req=r01040 path=/checkout status=200 dur=243ms
2026-09-14T14:01:06.259Z INFO  [sqlpool] pool stats active=2 idle=18 waiting=0 max=20
2026-09-14T14:01:08.013Z INFO  [checkout-svc] req=r01041 path=/cart status=200 dur=132ms
2026-09-14T14:01:10.177Z INFO  [deployer] rollout checkout-svc 2.13.4 -> 2.14.0 complete (changes: gift card balance check at checkout, new payment retry config, log format tweaks)
2026-09-14T14:01:10.177Z INFO  [checkout-svc] starting checkout-svc version=2.14.0 pid=57 pool.max=20 pool.acquire_timeout_ms=5000
2026-09-14T14:01:12.127Z INFO  [checkout-svc] req=r01042 path=/checkout status=200 dur=146ms
2026-09-14T14:01:13.627Z INFO  [checkout-svc] req=r01043 path=/products status=200 dur=45ms
2026-09-14T14:01:16.616Z INFO  [checkout-svc] req=r01044 path=/checkout status=200 dur=343ms
2026-09-14T14:01:18.967Z INFO  [checkout-svc] req=r01045 path=/cart status=200 dur=84ms
2026-09-14T14:01:21.889Z INFO  [checkout-svc] req=r01046 path=/orders status=200 dur=51ms
2026-09-14T14:01:23.861Z INFO  [checkout-svc] req=r01047 path=/orders status=200 dur=142ms
2026-09-14T14:01:27.342Z INFO  [checkout-svc] req=r01048 path=/cart status=200 dur=46ms
2026-09-14T14:01:30.245Z INFO  [checkout-svc] req=r01049 path=/orders status=200 dur=61ms
2026-09-14T14:01:33.859Z WARN  [giftcard-client] req=r01050 balance lookup card=****9654 -> 404 card_not_found (dur=84ms)
2026-09-14T14:01:33.859Z INFO  [checkout-svc] req=r01050 path=/checkout giftcard=rejected status=402 dur=129ms
2026-09-14T14:01:35.469Z INFO  [checkout-svc] req=r01051 path=/cart status=200 dur=43ms
2026-09-14T14:01:38.038Z INFO  [sqlpool] pool stats active=4 idle=16 waiting=0 max=20
2026-09-14T14:01:41.040Z INFO  [checkout-svc] req=r01052 path=/cart status=200 dur=77ms
2026-09-14T14:01:44.721Z INFO  [checkout-svc] req=r01053 path=/products status=200 dur=104ms
2026-09-14T14:01:48.827Z WARN  [runtime] gc pause 104ms (heap 71%)
2026-09-14T14:01:51.307Z INFO  [checkout-svc] req=r01055 path=/products status=200 dur=78ms
2026-09-14T14:01:53.625Z INFO  [checkout-svc] req=r01056 path=/cart status=200 dur=27ms
2026-09-14T14:01:55.239Z INFO  [checkout-svc] req=r01057 path=/orders status=200 dur=86ms
2026-09-14T14:01:57.532Z INFO  [checkout-svc] req=r01058 path=/cart status=200 dur=134ms
2026-09-14T14:02:00.463Z INFO  [checkout-svc] req=r01059 path=/cart status=200 dur=40ms
2026-09-14T14:02:02.866Z WARN  [giftcard-client] req=r01060 balance lookup card=****8701 -> 404 card_not_found (dur=53ms)
2026-09-14T14:02:02.866Z INFO  [checkout-svc] req=r01060 path=/checkout giftcard=rejected status=402 dur=121ms
2026-09-14T14:02:06.922Z INFO  [checkout-svc] req=r01061 path=/products status=200 dur=20ms
2026-09-14T14:02:10.385Z INFO  [sqlpool] pool stats active=5 idle=15 waiting=0 max=20
2026-09-14T14:02:13.294Z INFO  [checkout-svc] req=r01062 path=/checkout status=200 dur=333ms
2026-09-14T14:02:15.285Z INFO  [checkout-svc] req=r01063 path=/products status=200 dur=71ms
2026-09-14T14:02:18.743Z INFO  [checkout-svc] req=r01064 path=/orders status=200 dur=105ms
2026-09-14T14:02:20.598Z INFO  [checkout-svc] req=r01065 path=/products status=200 dur=121ms
2026-09-14T14:02:23.995Z INFO  [checkout-svc] req=r01066 path=/checkout status=200 dur=305ms
2026-09-14T14:02:26.145Z WARN  [giftcard-client] req=r01067 balance lookup card=****3081 -> 404 card_not_found (dur=77ms)
2026-09-14T14:02:26.145Z INFO  [checkout-svc] req=r01067 path=/checkout giftcard=rejected status=402 dur=119ms
2026-09-14T14:02:30.331Z INFO  [checkout-svc] req=r01068 path=/checkout giftcard=applied status=200 dur=299ms
2026-09-14T14:02:32.469Z INFO  [checkout-svc] req=r01069 path=/cart status=200 dur=25ms
2026-09-14T14:02:34.027Z INFO  [checkout-svc] req=r01070 path=/products status=200 dur=46ms
2026-09-14T14:02:37.683Z INFO  [checkout-svc] req=r01071 path=/cart status=200 dur=131ms
2026-09-14T14:02:39.980Z INFO  [checkout-svc] req=r01072 path=/cart status=200 dur=27ms
2026-09-14T14:02:42.511Z INFO  [sqlpool] pool stats active=4 idle=16 waiting=0 max=20
2026-09-14T14:02:45.210Z INFO  [checkout-svc] req=r01073 path=/products status=200 dur=103ms
2026-09-14T14:02:47.772Z INFO  [checkout-svc] req=r01074 path=/products status=200 dur=53ms
2026-09-14T14:02:49.521Z INFO  [checkout-svc] req=r01075 path=/cart status=200 dur=137ms
2026-09-14T14:02:53.410Z INFO  [checkout-svc] req=r01076 path=/products status=200 dur=127ms
2026-09-14T14:02:56.964Z WARN  [giftcard-client] req=r01077 balance lookup card=****3487 -> 404 card_not_found (dur=41ms)
2026-09-14T14:02:56.964Z INFO  [checkout-svc] req=r01077 path=/checkout giftcard=rejected status=402 dur=116ms
2026-09-14T14:02:59.214Z INFO  [checkout-svc] req=r01078 path=/products status=200 dur=58ms
2026-09-14T14:03:01.419Z WARN  [giftcard-client] req=r01079 balance lookup card=****2971 -> 404 card_not_found (dur=60ms)
2026-09-14T14:03:01.419Z INFO  [checkout-svc] req=r01079 path=/checkout giftcard=rejected status=402 dur=126ms
2026-09-14T14:03:05.092Z INFO  [checkout-svc] req=r01080 path=/products status=200 dur=47ms
2026-09-14T14:03:08.886Z WARN  [giftcard-client] req=r01081 balance lookup card=****4134 -> 404 card_not_found (dur=89ms)
2026-09-14T14:03:08.886Z INFO  [checkout-svc] req=r01081 path=/checkout giftcard=rejected status=402 dur=72ms
2026-09-14T14:03:12.465Z INFO  [checkout-svc] req=r01082 path=/checkout status=200 dur=314ms
2026-09-14T14:03:14.224Z INFO  [sqlpool] pool stats active=8 idle=12 waiting=0 max=20
2026-09-14T14:03:17.057Z INFO  [checkout-svc] req=r01083 path=/products status=200 dur=151ms
2026-09-14T14:03:19.373Z INFO  [checkout-svc] req=r01084 path=/orders status=200 dur=150ms
2026-09-14T14:03:23.057Z INFO  [checkout-svc] req=r01085 path=/products status=200 dur=83ms
2026-09-14T14:03:26.700Z INFO  [checkout-svc] req=r01086 path=/cart status=200 dur=71ms
2026-09-14T14:03:30.033Z WARN  [giftcard-client] req=r01087 balance lookup card=****2992 -> 404 card_not_found (dur=60ms)
2026-09-14T14:03:30.033Z INFO  [checkout-svc] req=r01087 path=/checkout giftcard=rejected status=402 dur=69ms
2026-09-14T14:03:32.518Z INFO  [checkout-svc] req=r01088 path=/cart status=200 dur=97ms
2026-09-14T14:03:34.519Z INFO  [checkout-svc] req=r01089 path=/cart status=200 dur=113ms
2026-09-14T14:03:36.604Z WARN  [redis] slow command GET session:* 38ms
2026-09-14T14:03:40.019Z WARN  [giftcard-client] req=r01091 balance lookup card=****2542 -> 404 card_not_found (dur=71ms)
2026-09-14T14:03:40.019Z INFO  [checkout-svc] req=r01091 path=/checkout giftcard=rejected status=402 dur=80ms
2026-09-14T14:03:42.435Z INFO  [checkout-svc] req=r01092 path=/checkout giftcard=applied status=200 dur=326ms
2026-09-14T14:03:45.324Z INFO  [sqlpool] pool stats active=10 idle=10 waiting=0 max=20
2026-09-14T14:03:47.625Z INFO  [checkout-svc] req=r01093 path=/checkout status=200 dur=304ms
2026-09-14T14:03:50.623Z WARN  [giftcard-client] req=r01094 balance lookup card=****8514 -> 404 card_not_found (dur=41ms)
2026-09-14T14:03:50.623Z INFO  [checkout-svc] req=r01094 path=/checkout giftcard=rejected status=402 dur=109ms
2026-09-14T14:03:53.480Z INFO  [checkout-svc] req=r01095 path=/cart status=200 dur=151ms
2026-09-14T14:03:55.243Z INFO  [checkout-svc] req=r01096 path=/checkout giftcard=applied status=200 dur=173ms
2026-09-14T14:03:57.087Z WARN  [node] disk usage /var/log 81%
2026-09-14T14:03:59.330Z WARN  [node] disk usage /var/log 81%
2026-09-14T14:04:02.559Z INFO  [checkout-svc] req=r01099 path=/products status=200 dur=86ms
2026-09-14T14:04:05.721Z WARN  [giftcard-client] req=r01100 balance lookup card=****9434 -> 404 card_not_found (dur=84ms)
2026-09-14T14:04:05.721Z INFO  [checkout-svc] req=r01100 path=/checkout giftcard=rejected status=402 dur=101ms
2026-09-14T14:04:07.587Z WARN  [sqlpool] connection pg-6 held for 115s by giftcard.balance_lookup (leak detection threshold 60s)
2026-09-14T14:04:09.383Z WARN  [node] disk usage /var/log 81%
2026-09-14T14:04:13.481Z WARN  [giftcard-client] req=r01103 balance lookup card=****5268 -> 404 card_not_found (dur=54ms)
2026-09-14T14:04:13.481Z INFO  [checkout-svc] req=r01103 path=/checkout giftcard=rejected status=402 dur=68ms
2026-09-14T14:04:16.064Z INFO  [sqlpool] pool stats active=12 idle=8 waiting=0 max=20
2026-09-14T14:04:19.422Z INFO  [checkout-svc] req=r01104 path=/checkout giftcard=applied status=200 dur=257ms
2026-09-14T14:04:23.468Z INFO  [checkout-svc] req=r01105 path=/checkout giftcard=applied status=200 dur=176ms
2026-09-14T14:04:25.629Z WARN  [redis] slow command GET session:* 41ms
2026-09-14T14:04:27.955Z INFO  [checkout-svc] req=r01107 path=/products status=200 dur=98ms
2026-09-14T14:04:31.630Z INFO  [checkout-svc] req=r01108 path=/cart status=200 dur=134ms
2026-09-14T14:04:35.178Z INFO  [checkout-svc] req=r01109 path=/cart status=200 dur=108ms
2026-09-14T14:04:36.752Z INFO  [checkout-svc] req=r01110 path=/checkout status=200 dur=123ms
2026-09-14T14:04:38.327Z INFO  [checkout-svc] req=r01111 path=/products status=200 dur=68ms
2026-09-14T14:04:41.933Z INFO  [checkout-svc] req=r01112 path=/orders status=200 dur=47ms
2026-09-14T14:04:46.129Z INFO  [sqlpool] pool stats active=14 idle=6 waiting=0 max=20
2026-09-14T14:04:49.399Z INFO  [checkout-svc] req=r01113 path=/products status=200 dur=120ms
2026-09-14T14:04:52.974Z WARN  [sqlpool] connection pg-7 held for 119s by giftcard.balance_lookup (leak detection threshold 60s)
2026-09-14T14:04:55.877Z WARN  [giftcard-client] req=r01115 balance lookup card=****3289 -> 404 card_not_found (dur=62ms)
2026-09-14T14:04:55.877Z INFO  [checkout-svc] req=r01115 path=/checkout giftcard=rejected status=402 dur=66ms
2026-09-14T14:04:57.908Z WARN  [giftcard-client] req=r01116 balance lookup card=****5187 -> 404 card_not_found (dur=43ms)
2026-09-14T14:04:57.908Z INFO  [checkout-svc] req=r01116 path=/checkout giftcard=rejected status=402 dur=70ms
2026-09-14T14:05:00.968Z INFO  [checkout-svc] req=r01117 path=/products status=200 dur=92ms
2026-09-14T14:05:04.920Z WARN  [runtime] gc pause 117ms (heap 71%)
2026-09-14T14:05:06.605Z INFO  [checkout-svc] req=r01119 path=/cart status=200 dur=88ms
2026-09-14T14:05:09.931Z INFO  [checkout-svc] req=r01120 path=/checkout giftcard=applied status=200 dur=805ms
2026-09-14T14:05:12.432Z WARN  [giftcard-client] req=r01121 balance lookup card=****6071 -> 404 card_not_found (dur=51ms)
2026-09-14T14:05:12.432Z INFO  [checkout-svc] req=r01121 path=/checkout giftcard=rejected status=402 dur=60ms
2026-09-14T14:05:15.305Z INFO  [checkout-svc] req=r01122 path=/orders status=200 dur=91ms
2026-09-14T14:05:18.864Z INFO  [sqlpool] pool stats active=17 idle=3 waiting=0 max=20
2026-09-14T14:05:21.187Z WARN  [runtime] gc pause 80ms (heap 71%)
2026-09-14T14:05:23.059Z WARN  [redis] slow command GET session:* 35ms
2026-09-14T14:05:25.148Z INFO  [checkout-svc] req=r01125 path=/checkout status=200 dur=220ms
2026-09-14T14:05:26.740Z WARN  [sqlpool] connection pg-8 held for 82s by giftcard.balance_lookup (leak detection threshold 60s)
2026-09-14T14:05:30.638Z INFO  [checkout-svc] req=r01127 path=/products status=200 dur=59ms
2026-09-14T14:05:34.831Z INFO  [checkout-svc] req=r01128 path=/products status=200 dur=119ms
2026-09-14T14:05:37.666Z INFO  [checkout-svc] req=r01129 path=/orders status=200 dur=58ms
2026-09-14T14:05:40.329Z INFO  [checkout-svc] req=r01130 path=/products status=200 dur=57ms
2026-09-14T14:05:42.008Z INFO  [checkout-svc] req=r01131 path=/products status=200 dur=151ms
2026-09-14T14:05:46.077Z INFO  [checkout-svc] req=r01132 path=/products status=200 dur=149ms
2026-09-14T14:05:48.147Z INFO  [checkout-svc] req=r01133 path=/products status=200 dur=149ms
2026-09-14T14:05:51.975Z INFO  [sqlpool] pool stats active=15 idle=5 waiting=0 max=20
2026-09-14T14:05:55.867Z INFO  [checkout-svc] req=r01134 path=/products status=200 dur=78ms
2026-09-14T14:05:57.715Z INFO  [checkout-svc] req=r01135 path=/checkout giftcard=applied status=200 dur=733ms
2026-09-14T14:06:00.757Z INFO  [checkout-svc] req=r01136 path=/products status=200 dur=32ms
2026-09-14T14:06:04.828Z INFO  [checkout-svc] req=r01137 path=/checkout giftcard=applied status=200 dur=930ms
2026-09-14T14:06:07.408Z INFO  [checkout-svc] req=r01138 path=/checkout giftcard=applied status=200 dur=937ms
2026-09-14T14:06:11.100Z WARN  [giftcard-client] req=r01139 balance lookup card=****9617 -> 404 card_not_found (dur=87ms)
2026-09-14T14:06:11.100Z INFO  [checkout-svc] req=r01139 path=/checkout giftcard=rejected status=402 dur=120ms
2026-09-14T14:06:13.632Z INFO  [checkout-svc] req=r01140 path=/products status=200 dur=1248ms
2026-09-14T14:06:15.972Z WARN  [runtime] gc pause 138ms (heap 71%)
2026-09-14T14:06:19.495Z INFO  [checkout-svc] req=r01142 path=/checkout status=200 dur=1618ms
2026-09-14T14:06:21.186Z INFO  [checkout-svc] req=r01143 path=/products status=200 dur=587ms
2026-09-14T14:06:25.142Z INFO  [sqlpool] pool stats active=16 idle=4 waiting=0 max=20
2026-09-14T14:06:28.000Z WARN  [redis] slow command GET session:* 49ms
2026-09-14T14:06:32.044Z INFO  [checkout-svc] req=r01145 path=/checkout status=200 dur=691ms
2026-09-14T14:06:35.533Z WARN  [node] disk usage /var/log 83%
2026-09-14T14:06:37.440Z INFO  [checkout-svc] req=r01147 path=/products status=200 dur=1536ms
2026-09-14T14:06:41.055Z WARN  [sqlpool] connection pg-15 held for 299s by giftcard.balance_lookup (leak detection threshold 60s)
2026-09-14T14:06:43.040Z INFO  [checkout-svc] req=r01149 path=/products status=200 dur=1547ms
2026-09-14T14:06:44.891Z INFO  [checkout-svc] req=r01150 path=/checkout status=200 dur=2273ms
2026-09-14T14:06:46.704Z INFO  [checkout-svc] req=r01151 path=/orders status=200 dur=1872ms
2026-09-14T14:06:49.063Z INFO  [checkout-svc] req=r01152 path=/cart status=200 dur=608ms
2026-09-14T14:06:51.143Z INFO  [checkout-svc] req=r01153 path=/cart status=200 dur=855ms
2026-09-14T14:06:55.114Z INFO  [checkout-svc] req=r01154 path=/products status=200 dur=752ms
2026-09-14T14:06:58.109Z INFO  [sqlpool] pool stats active=16 idle=4 waiting=0 max=20
2026-09-14T14:07:01.648Z INFO  [checkout-svc] req=r01155 path=/orders status=200 dur=421ms
2026-09-14T14:07:03.799Z INFO  [checkout-svc] req=r01156 path=/checkout giftcard=applied status=200 dur=927ms
2026-09-14T14:07:06.535Z INFO  [checkout-svc] req=r01157 path=/orders status=200 dur=1848ms
2026-09-14T14:07:09.329Z WARN  [giftcard-client] req=r01158 balance lookup card=****6428 -> 404 card_not_found (dur=88ms)
2026-09-14T14:07:09.329Z INFO  [checkout-svc] req=r01158 path=/checkout giftcard=rejected status=402 dur=103ms
2026-09-14T14:07:12.460Z INFO  [checkout-svc] req=r01159 path=/checkout giftcard=applied status=200 dur=908ms
2026-09-14T14:07:14.997Z INFO  [checkout-svc] req=r01160 path=/orders status=200 dur=631ms
2026-09-14T14:07:17.974Z INFO  [checkout-svc] req=r01161 path=/products status=200 dur=487ms
2026-09-14T14:07:20.623Z INFO  [checkout-svc] req=r01162 path=/checkout giftcard=applied status=200 dur=836ms
2026-09-14T14:07:23.144Z INFO  [checkout-svc] req=r01163 path=/orders status=200 dur=1642ms
2026-09-14T14:07:25.421Z INFO  [checkout-svc] req=r01164 path=/products status=200 dur=447ms
2026-09-14T14:07:29.505Z INFO  [sqlpool] pool stats active=18 idle=2 waiting=3 max=20
2026-09-14T14:07:33.254Z WARN  [giftcard-client] req=r01165 balance lookup card=****2320 -> 404 card_not_found (dur=86ms)
2026-09-14T14:07:33.254Z INFO  [checkout-svc] req=r01165 path=/checkout giftcard=rejected status=402 dur=112ms
2026-09-14T14:07:36.600Z INFO  [checkout-svc] req=r01166 path=/cart status=200 dur=2281ms
2026-09-14T14:07:38.300Z INFO  [checkout-svc] req=r01167 path=/products status=200 dur=951ms
2026-09-14T14:07:41.734Z INFO  [checkout-svc] req=r01168 path=/cart status=200 dur=1343ms
2026-09-14T14:07:45.907Z WARN  [redis] slow command GET session:* 45ms
2026-09-14T14:07:48.639Z INFO  [checkout-svc] req=r01170 path=/products status=200 dur=810ms
2026-09-14T14:07:50.824Z INFO  [checkout-svc] req=r01171 path=/checkout status=200 dur=2423ms
2026-09-14T14:07:54.360Z INFO  [checkout-svc] req=r01172 path=/orders status=200 dur=2148ms
2026-09-14T14:07:57.610Z WARN  [giftcard-client] req=r01173 balance lookup card=****4152 -> 404 card_not_found (dur=51ms)
2026-09-14T14:07:57.610Z INFO  [checkout-svc] req=r01173 path=/checkout giftcard=rejected status=402 dur=103ms
2026-09-14T14:08:01.386Z INFO  [sqlpool] pool stats active=19 idle=1 waiting=3 max=20
2026-09-14T14:08:03.865Z INFO  [checkout-svc] req=r01174 path=/products status=200 dur=353ms
2026-09-14T14:08:07.055Z INFO  [checkout-svc] req=r01175 path=/products status=200 dur=1214ms
2026-09-14T14:08:10.098Z WARN  [node] disk usage /var/log 81%
2026-09-14T14:08:13.638Z WARN  [sqlpool] connection pg-12 held for 125s by giftcard.balance_lookup (leak detection threshold 60s)
2026-09-14T14:08:17.199Z INFO  [checkout-svc] req=r01178 path=/products status=200 dur=654ms
2026-09-14T14:08:19.809Z INFO  [checkout-svc] req=r01179 path=/orders status=200 dur=2148ms
2026-09-14T14:08:23.077Z INFO  [checkout-svc] req=r01180 path=/products status=200 dur=746ms
2026-09-14T14:08:24.709Z INFO  [checkout-svc] req=r01181 path=/products status=200 dur=2347ms
2026-09-14T14:08:26.209Z INFO  [checkout-svc] req=r01182 path=/checkout giftcard=applied status=200 dur=1069ms
2026-09-14T14:08:28.726Z INFO  [checkout-svc] req=r01183 path=/cart status=200 dur=881ms
2026-09-14T14:08:32.365Z INFO  [sqlpool] pool stats active=20 idle=0 waiting=1 max=20
2026-09-14T14:08:36.516Z INFO  [checkout-svc] req=r01184 path=/orders status=200 dur=2499ms
2026-09-14T14:08:38.177Z WARN  [giftcard-client] req=r01185 balance lookup card=****3058 -> 404 card_not_found (dur=42ms)
2026-09-14T14:08:38.177Z INFO  [checkout-svc] req=r01185 path=/checkout giftcard=rejected status=402 dur=98ms
2026-09-14T14:08:40.201Z INFO  [checkout-svc] req=r01186 path=/products status=200 dur=790ms
2026-09-14T14:08:42.108Z ERROR [checkout-svc] req=r01187 path=/checkout error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5025ms
2026-09-14T14:08:44.676Z ERROR [checkout-svc] req=r01188 path=/checkout error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5001ms
2026-09-14T14:08:48.377Z ERROR [checkout-svc] req=r01189 path=/cart error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5018ms
2026-09-14T14:08:51.172Z INFO  [checkout-svc] req=r01190 path=/cart status=200 dur=2496ms
2026-09-14T14:08:53.633Z ERROR [checkout-svc] req=r01191 path=/checkout error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5027ms
2026-09-14T14:08:57.793Z ERROR [checkout-svc] req=r01192 path=/checkout error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5013ms
2026-09-14T14:09:01.334Z INFO  [checkout-svc] req=r01193 path=/products status=200 dur=659ms
2026-09-14T14:09:03.887Z INFO  [sqlpool] pool stats active=20 idle=0 waiting=5 max=20
2026-09-14T14:09:06.903Z ERROR [checkout-svc] req=r01194 path=/checkout error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5022ms
2026-09-14T14:09:10.125Z ERROR [checkout-svc] req=r01195 path=/cart error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5013ms
2026-09-14T14:09:11.652Z INFO  [checkout-svc] req=r01196 path=/products status=200 dur=625ms
2026-09-14T14:09:13.992Z ERROR [checkout-svc] req=r01197 path=/checkout error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5020ms
2026-09-14T14:09:16.286Z ERROR [checkout-svc] req=r01198 path=/checkout error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5017ms
2026-09-14T14:09:18.994Z ERROR [checkout-svc] req=r01199 path=/cart error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5040ms
2026-09-14T14:09:21.261Z INFO  [checkout-svc] req=r01200 path=/orders status=200 dur=557ms
2026-09-14T14:09:25.197Z ERROR [checkout-svc] req=r01201 path=/cart error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5004ms
2026-09-14T14:09:27.569Z ERROR [checkout-svc] req=r01202 path=/checkout error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5027ms
2026-09-14T14:09:29.281Z INFO  [checkout-svc] req=r01203 path=/cart status=200 dur=2161ms
2026-09-14T14:09:32.067Z INFO  [checkout-svc] req=r01204 path=/checkout status=200 dur=1710ms
2026-09-14T14:09:34.348Z INFO  [sqlpool] pool stats active=20 idle=0 waiting=6 max=20
2026-09-14T14:09:37.763Z ERROR [checkout-svc] req=r01205 path=/cart error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5024ms
2026-09-14T14:09:40.621Z WARN  [kubelet] liveness probe failed for checkout-svc-7c9d (GET /healthz timeout 3s) x3, restarting container
2026-09-14T14:09:40.621Z INFO  [checkout-svc] starting checkout-svc version=2.14.0 pid=12 pool.max=20 pool.acquire_timeout_ms=5000
2026-09-14T14:09:43.933Z WARN  [giftcard-client] req=r01206 balance lookup card=****1047 -> 404 card_not_found (dur=45ms)
2026-09-14T14:09:43.933Z INFO  [checkout-svc] req=r01206 path=/checkout giftcard=rejected status=402 dur=104ms
2026-09-14T14:09:47.154Z INFO  [checkout-svc] req=r01207 path=/checkout status=200 dur=263ms
2026-09-14T14:09:49.503Z INFO  [checkout-svc] req=r01208 path=/products status=200 dur=99ms
2026-09-14T14:09:52.774Z WARN  [giftcard-client] req=r01209 balance lookup card=****8757 -> 404 card_not_found (dur=74ms)
2026-09-14T14:09:52.774Z INFO  [checkout-svc] req=r01209 path=/checkout giftcard=rejected status=402 dur=117ms
2026-09-14T14:09:55.064Z INFO  [checkout-svc] req=r01210 path=/products status=200 dur=141ms
2026-09-14T14:09:56.688Z INFO  [checkout-svc] req=r01211 path=/cart status=200 dur=123ms
2026-09-14T14:09:58.354Z INFO  [checkout-svc] req=r01212 path=/orders status=200 dur=36ms
2026-09-14T14:10:00.107Z WARN  [redis] slow command GET session:* 34ms
2026-09-14T14:10:04.087Z INFO  [checkout-svc] req=r01214 path=/cart status=200 dur=105ms
2026-09-14T14:10:08.114Z INFO  [sqlpool] pool stats active=3 idle=17 waiting=0 max=20
2026-09-14T14:10:10.687Z INFO  [checkout-svc] req=r01215 path=/products status=200 dur=101ms
2026-09-14T14:10:13.315Z INFO  [checkout-svc] req=r01216 path=/products status=200 dur=36ms
2026-09-14T14:10:14.914Z INFO  [checkout-svc] req=r01217 path=/checkout status=200 dur=241ms
2026-09-14T14:10:18.321Z INFO  [checkout-svc] req=r01218 path=/orders status=200 dur=84ms
2026-09-14T14:10:21.582Z INFO  [checkout-svc] req=r01219 path=/cart status=200 dur=147ms
2026-09-14T14:10:23.831Z INFO  [checkout-svc] req=r01220 path=/checkout giftcard=applied status=200 dur=197ms
2026-09-14T14:10:27.818Z WARN  [runtime] gc pause 120ms (heap 71%)
2026-09-14T14:10:31.205Z INFO  [checkout-svc] req=r01222 path=/products status=200 dur=40ms
2026-09-14T14:10:34.801Z WARN  [giftcard-client] req=r01223 balance lookup card=****3620 -> 404 card_not_found (dur=44ms)
2026-09-14T14:10:34.801Z INFO  [checkout-svc] req=r01223 path=/checkout giftcard=rejected status=402 dur=64ms
2026-09-14T14:10:38.274Z INFO  [sqlpool] pool stats active=6 idle=14 waiting=0 max=20
2026-09-14T14:10:42.004Z INFO  [checkout-svc] req=r01224 path=/orders status=200 dur=46ms
2026-09-14T14:10:43.799Z WARN  [redis] slow command GET session:* 35ms
2026-09-14T14:10:46.152Z INFO  [checkout-svc] req=r01226 path=/checkout giftcard=applied status=200 dur=348ms
2026-09-14T14:10:48.361Z WARN  [runtime] gc pause 133ms (heap 71%)
2026-09-14T14:10:51.748Z INFO  [checkout-svc] req=r01228 path=/products status=200 dur=80ms
2026-09-14T14:10:55.453Z INFO  [checkout-svc] req=r01229 path=/products status=200 dur=51ms
2026-09-14T14:10:58.156Z INFO  [checkout-svc] req=r01230 path=/products status=200 dur=88ms
2026-09-14T14:11:01.183Z WARN  [redis] slow command GET session:* 46ms
2026-09-14T14:11:03.498Z INFO  [checkout-svc] req=r01232 path=/cart status=200 dur=82ms
2026-09-14T14:11:05.962Z WARN  [giftcard-client] req=r01233 balance lookup card=****4084 -> 404 card_not_found (dur=65ms)
2026-09-14T14:11:05.962Z INFO  [checkout-svc] req=r01233 path=/checkout giftcard=rejected status=402 dur=92ms
2026-09-14T14:11:08.469Z INFO  [sqlpool] pool stats active=7 idle=13 waiting=0 max=20
2026-09-14T14:11:12.124Z WARN  [runtime] gc pause 92ms (heap 71%)
2026-09-14T14:11:16.300Z INFO  [checkout-svc] req=r01235 path=/checkout status=200 dur=146ms
2026-09-14T14:11:17.818Z INFO  [checkout-svc] req=r01236 path=/products status=200 dur=79ms
2026-09-14T14:11:21.154Z INFO  [checkout-svc] req=r01237 path=/checkout status=200 dur=344ms
2026-09-14T14:11:23.856Z WARN  [runtime] gc pause 86ms (heap 71%)
2026-09-14T14:11:26.132Z INFO  [checkout-svc] req=r01239 path=/products status=200 dur=69ms
2026-09-14T14:11:27.939Z INFO  [checkout-svc] req=r01240 path=/products status=200 dur=65ms
2026-09-14T14:11:31.278Z INFO  [checkout-svc] req=r01241 path=/products status=200 dur=21ms
2026-09-14T14:11:33.211Z INFO  [checkout-svc] req=r01242 path=/products status=200 dur=109ms
2026-09-14T14:11:35.602Z WARN  [giftcard-client] req=r01243 balance lookup card=****6570 -> 404 card_not_found (dur=53ms)
2026-09-14T14:11:35.602Z INFO  [checkout-svc] req=r01243 path=/checkout giftcard=rejected status=402 dur=92ms
2026-09-14T14:11:37.258Z INFO  [checkout-svc] req=r01244 path=/products status=200 dur=72ms
2026-09-14T14:11:39.258Z ERROR [gateway] upstream checkout-svc: 5xx rate 38% over 1m (threshold 5%) -> paging on-call
2026-09-14T14:11:40.258Z WARN  [payments] retry config: max_attempts=4 backoff=exp (new in 2.14.0) - payment-provider latency p99 410ms (normal)
2026-09-14T14:11:42.258Z INFO  [dns] resolver cache refreshed (2 upstreams healthy)
```
````
</details>

### Reference notes

Ground truth (the log was generated from this scenario):
- Root cause: v2.14.0 (deployed 14:01:10, "gift card balance check at checkout") leaks a DB connection every time the gift-card balance lookup fails (404 card_not_found -> checkout returns 402). The connection is never returned to the pool.
- Evidence: pool stats active climbs monotonically after the deploy (2-3 before deploy -> 5, 10, 15, 20 with idle=0 and waiting>0 by ~14:08); sqlpool leak-detection warnings "connection pg-N held for Ns by giftcard.balance_lookup"; growth tracks the card_not_found 404 count; before 14:01 (v2.13.4) pool was stable.
- Symptoms: "sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" -> 503s on /checkout, /orders, /cart (not only gift-card requests); rising latencies on normal requests; liveness probe failures -> kubelet restart at ~14:09:41, which temporarily resets the pool (active=3) and then it starts climbing again (7 by 14:11) -> will recur. Gateway 5xx alert/page at end.
- Noise / red herrings: TLS cert expiring in 29 days (metrics-exporter), GC pauses ~80-160ms, redis slow GETs, disk usage /var/log 81-83%, payments retry config line (explicitly says provider latency normal), DNS refresh. A strong answer dismisses these explicitly or at least doesn't blame them.
- Mitigation: roll back to 2.13.4 (or feature-flag off the gift card check); restarts only buy minutes. Real fix: release the connection on the error path (try/finally / context manager) in giftcard.balance_lookup; add a test for the 404 path; consider pool leak-detection alerting.
- Wrong answers: blaming the payment retry config, GC, redis, cert, disk, or "pool too small" (increasing pool size only delays it).


### Answer A

**Timeline**

* 13:59:00 - 14:01:06 Normal steady state on v2.13.4 pid 41
  `2026-09-14T13:59:00.000Z INFO  [checkout-svc] starting checkout-svc version=2.13.4 pid=41 pool.max=20 pool.acquire_timeout_ms=5000`
  Requests /orders, /checkout, /cart, /products are 200 in 30-335 ms. 
  `2026-09-14T13:59:32.942Z INFO  [sqlpool] pool stats active=1 idle=19 waiting=0 max=20`
  `2026-09-14T14:01:06.259Z INFO  [sqlpool] pool stats active=2 idle=18 waiting=0 max=20`

* 14:01:10.177 Deploy
  `2026-09-14T14:01:10.177Z INFO  [deployer] rollout checkout-svc 2.13.4 -> 2.14.0 complete (changes: gift card balance check at checkout, new payment retry config, log format tweaks)`
  `2026-09-14T14:01:10.177Z INFO  [checkout-svc] starting checkout-svc version=2.14.0 pid=57 pool.max=20 pool.acquire_timeout_ms=5000`
  Requests continue 200 for a few minutes.

* 14:01:33 onwards Gift card checks appear and start failing fast
  `2026-09-14T14:01:33.859Z WARN  [giftcard-client] req=r01050 balance lookup card=****9654 -> 404 card_not_found (dur=84ms)`
  `2026-09-14T14:01:33.859Z INFO  [checkout-svc] req=r01050 path=/checkout giftcard=rejected status=402 dur=129ms`
  Repeated 404 card_not_found with 402 responses e.g. r01060, r01067, r01077, r01079...

* 14:01:38 - 14:07:29 Pool grows and latency creeps up
  `2026-09-14T14:01:38.038Z INFO  [sqlpool] pool stats active=4 idle=16 waiting=0 max=20`
  `2026-09-14T14:03:14.224Z INFO  [sqlpool] pool stats active=8 idle=12 waiting=0 max=20`
  `2026-09-14T14:04:16.064Z INFO  [sqlpool] pool stats active=12 idle=8 waiting=0 max=20`
  `2026-09-14T14:05:18.864Z INFO  [sqlpool] pool stats active=17 idle=3 waiting=0 max=20`
  `2026-09-14T14:07:29.505Z INFO  [sqlpool] pool stats active=18 idle=2 waiting=3 max=20`
  Request durations increase from ~200-300 ms to 600-1000 ms and then >1.5 s:
  `2026-09-14T14:06:44.891Z INFO  [checkout-svc] req=r01150 path=/checkout status=200 dur=2273ms`

* Connection leak detection fires
  `2026-09-14T14:04:07.587Z WARN  [sqlpool] connection pg-6 held for 115s by giftcard.balance_lookup (leak detection threshold 60s)`
  `2026-09-14T14:04:52.974Z WARN  [sqlpool] connection pg-7 held for 119s by giftcard.balance_lookup`
  `2026-09-14T14:05:26.740Z WARN  [sqlpool] connection pg-8 held for 82s by giftcard.balance_lookup`
  `2026-09-14T14:06:41.055Z WARN  [sqlpool] connection pg-15 held for 299s by giftcard.balance_lookup`
  `2026-09-14T14:08:13.638Z WARN  [sqlpool] connection pg-12 held for 125s by giftcard.balance_lookup`
  The leak is explicitly tied to `giftcard.balance_lookup`.

* Pool exhaustion and 503s
  `2026-09-14T14:08:32.365Z INFO  [sqlpool] pool stats active=20 idle=0 waiting=1 max=20`
  `2026-09-14T14:08:42.108Z ERROR [checkout-svc] req=r01187 path=/checkout error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5025ms`
  Followed by repeated timeouts:
  `2026-09-14T14:08:44.676Z ERROR [checkout-svc] req=r01188 path=/checkout ... status=503`
  `2026-09-14T14:09:03.887Z INFO  [sqlpool] pool stats active=20 idle=0 waiting=5 max=20`
  `2026-09-14T14:09:34.348Z INFO  [sqlpool] pool stats active=20 idle=0 waiting=6 max=20`

* Auto-restart
  `2026-09-14T14:09:40.621Z WARN  [kubelet] liveness probe failed for checkout-svc-7c9d (GET /healthz timeout 3s) x3, restarting container`
  `2026-09-14T14:09:40.621Z INFO  [checkout-svc] starting checkout-svc version=2.14.0 pid=12 pool.max=20 pool.acquire_timeout_ms=5000`
  After restart pool recovers:
  `2026-09-14T14:10:08.114Z INFO  [sqlpool] pool stats active=3 idle=17 waiting=0 max=20`
  Durations return to ~100-300 ms.

* Late alerting
  `2026-09-14T14:11:39.258Z ERROR [gateway] upstream checkout-svc: 5xx rate 38% over 1m (threshold 5%) -> paging on-call`

### Root cause
Connection leak introduced by the v2.14.0 change “gift card balance check at checkout”. 
The balance lookup obtains a sqlpool connection for `giftcard.balance_lookup` and does not release it on the error path, e.g. when the gift card service returns 404 card_not_found in ~40-89 ms. 
Evidence: deployment at 14:01:10.177 immediately precedes first giftcard-client 404 at 14:01:33.859 and the first leak warnings referencing `giftcard.balance_lookup` at 14:04:07.587. Connections stay held for 82-299 s, far longer than the 40-90 ms lookup duration, causing pool exhaustion.

### Symptoms, not cause
* Growing `sqlpool pool stats active` to max 20 with waiting queue >0
* Request latency growth and eventual `sqlpool: timeout acquiring connection after 5000ms` 503s on /checkout and /cart
* Liveness probe failures and container restart
* 5xx rate alert from gateway
* GC pauses 104-138 ms and Redis slow GET session:* 35-49 ms are secondary pressure from queuing/backlog.

### Unrelated noise
* `2026-09-14T13:59:00.000Z WARN  [metrics-exporter] TLS certificate for metrics.internal expires in 29 days`
* `2026-09-14T14:03:57.087Z WARN  [node] disk usage /var/log 81%` repeated 81-83%
* Payment retry config log `2026-09-14T14:11:40.258Z WARN  [payments] retry config: max_attempts=4 backoff=exp (new in 2.14.0) - payment-provider latency p99 410ms (normal)`
These are pre-existing or orthogonal.

### Immediate mitigation
* Disable the new gift card balance check via feature flag / config and roll back to 2.13.4, or restart the checkout-svc pods to reclaim leaked connections. The restart at 14:09:40 already restored service.
* If rollback not possible, temporarily increase pool.max and lower acquire_timeout to fail fast, but this only buys time.

### Real fix
* Fix checkout-svc v2.14.0 to ensure the sqlpool connection is always returned in a finally block for `giftcard.balance_lookup`, including the 404 card_not_found path.
* Add a per-call timeout and circuit breaker for the giftcard client so a slow/unhealthy upstream cannot hold DB connections.
* Add unit/integration tests for error paths of gift card lookup and a leak detection metric alert on `sqlpool connection held >60s`.
* Verify log format change did not drop error logging that masks release failures.


### Answer B

**Timeline**

* **13:59:00 - 14:01:06 Normal steady state v2.13.4**
  `2026-09-14T13:59:00.000Z INFO  [checkout-svc] starting checkout-svc version=2.13.4 pid=41 pool.max=20 pool.acquire_timeout_ms=5000`
  Requests `/checkout`, `/orders`, `/cart`, `/products` all 200 with 30-350 ms durations.
  `2026-09-14T13:59:32.942Z INFO  [sqlpool] pool stats active=1 idle=19 waiting=0 max=20`
  `2026-09-14T14:00:03.192Z INFO  [sqlpool] pool stats active=3 idle=17 waiting=0 max=20`
  `2026-09-14T14:01:06.259Z INFO  [sqlpool] pool stats active=2 idle=18 waiting=0 max=20`

* **14:01:10 Deployment of the change**
  `2026-09-14T14:01:10.177Z INFO  [deployer] rollout checkout-svc 2.13.4 -> 2.14.0 complete (changes: gift card balance check at checkout, new payment retry config, log format tweaks)`
  `2026-09-14T14:01:10.177Z INFO  [checkout-svc] starting checkout-svc version=2.14.0 pid=57 pool.max=20 pool.acquire_timeout_ms=5000`
  Requests continue 200 for a few minutes.

* **14:01:33 onward Gift-card checks appear and start rejecting**
  `2026-09-14T14:01:33.859Z WARN  [giftcard-client] req=r01050 balance lookup card=****9654 -> 404 card_not_found (dur=84ms)`
  `2026-09-14T14:01:33.859Z INFO  [checkout-svc] req=r01050 path=/checkout giftcard=rejected status=402 dur=129ms`
  Same pattern repeats: `2026-09-14T14:02:02.866Z WARN [giftcard-client] req=r01060 balance lookup card=****8701 -> 404 card_not_found`, `2026-09-14T14:02:26.145Z WARN [giftcard-client] req=r01067 ... 404 card_not_found`, etc.

* **14:04:07 Connection leak detected**
  `2026-09-14T14:04:07.587Z WARN  [sqlpool] connection pg-6 held for 115s by giftcard.balance_lookup (leak detection threshold 60s)`
  Pool utilisation starts climbing:
  `2026-09-14T14:01:38.038Z INFO  [sqlpool] pool stats active=4 idle=16 waiting=0 max=20`
  `2026-09-14T14:03:45.324Z INFO  [sqlpool] pool stats active=10 idle=10 waiting=0 max=20`
  `2026-09-14T14:04:16.064Z INFO  [sqlpool] pool stats active=12 idle=8 waiting=0 max=20`
  `2026-09-14T14:04:46.129Z INFO  [sqlpool] pool stats active=14 idle=6 waiting=0 max=20`
  `2026-09-14T14:05:18.864Z INFO  [sqlpool] pool stats active=17 idle=3 waiting=0 max=20`

  Further leak warnings:
  `2026-09-14T14:04:52.974Z WARN  [sqlpool] connection pg-7 held for 119s by giftcard.balance_lookup`
  `2026-09-14T14:05:26.740Z WARN  [sqlpool] connection pg-8 held for 82s by giftcard.balance_lookup`
  `2026-09-14T14:06:41.055Z WARN  [sqlpool] connection pg-15 held for 299s by giftcard.balance_lookup`
  `2026-09-14T14:08:13.638Z WARN  [sqlpool] connection pg-12 held for 125s by giftcard.balance_lookup`

* **14:06 onward Latency degradation**
  Durations move from ~300 ms to >700 ms, then >1.5 s:
  `2026-09-14T14:06:13.632Z INFO  [checkout-svc] req=r01140 path=/products status=200 dur=1248ms`
  `2026-09-14T14:06:44.891Z INFO  [checkout-svc] req=r01150 path=/checkout status=200 dur=2273ms`
  `2026-09-14T14:07:29.505Z INFO  [sqlpool] pool stats active=18 idle=2 waiting=3 max=20`
  `2026-09-14T14:08:01.386Z INFO  [sqlpool] pool stats active=19 idle=1 waiting=3 max=20`

* **14:08:32 Pool exhaustion / 503s**
  `2026-09-14T14:08:32.365Z INFO  [sqlpool] pool stats active=20 idle=0 waiting=1 max=20`
  `2026-09-14T14:08:42.108Z ERROR [checkout-svc] req=r01187 path=/checkout error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5025ms`
  `2026-09-14T14:08:44.676Z ERROR [checkout-svc] req=r01188 path=/checkout error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5001ms`
  `2026-09-14T14:08:48.377Z ERROR [checkout-svc] req=r01189 path=/cart error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5018ms`
  Continued 503s with `active=20 idle=0 waiting=5/6`:
  `2026-09-14T14:09:03.887Z INFO  [sqlpool] pool stats active=20 idle=0 waiting=5 max=20`
  `2026-09-14T14:09:34.348Z INFO  [sqlpool] pool stats active=20 idle=0 waiting=6 max=20`

* **14:09:40 Crash loop / recovery**
  `2026-09-14T14:09:40.621Z WARN  [kubelet] liveness probe failed for checkout-svc-7c9d (GET /healthz timeout 3s) x3, restarting container`
  `2026-09-14T14:09:40.621Z INFO  [checkout-svc] starting checkout-svc version=2.14.0 pid=12 pool.max=20 pool.acquire_timeout_ms=5000`
  After restart pool is healthy again:
  `2026-09-14T14:10:08.114Z INFO  [sqlpool] pool stats active=3 idle=17 waiting=0 max=20`
  Requests return to ~100-300 ms.

### Root cause

SQL connection leak introduced by the 2.14.0 gift card balance check at checkout.

The deploy log ties the change to the incident:
`2026-09-14T14:01:10.177Z INFO  [deployer] rollout checkout-svc 2.13.4 -> 2.14.0 complete (changes: gift card balance check at checkout, new payment retry config, log format tweaks)`

After rollout, connections are held indefinitely by `giftcard.balance_lookup` and are never returned to the pool. The leak detector confirms it:
`2026-09-14T14:04:07.587Z WARN  [sqlpool] connection pg-6 held for 115s by giftcard.balance_lookup (leak detection threshold 60s)`
`2026-09-14T14:04:52.974Z WARN  [sqlpool] connection pg-7 held for 119s by giftcard.balance_lookup`
`2026-09-14T14:06:41.055Z WARN  [sqlpool] connection pg-15 held for 299s by giftcard.balance_lookup`

The 404 `card_not_found` responses from the giftcard client are fast, 40-90 ms:
`2026-09-14T14:01:33.859Z WARN  [giftcard-client] req=r01050 balance lookup card=****9654 -> 404 card_not_found (dur=84ms)`
The fast client response plus long held DB connections indicates the pool connection is acquired for the balance lookup and not released on the error / non-success path.

### Symptoms

* Rising `active` pool count and growing `waiting` queue up to `active=20 idle=0 waiting=6 max=20`
* Request latency increase from ~150-300 ms to 800-2,400 ms then timeouts
* `sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)` → HTTP 503 on `/checkout` and `/cart`
* Liveness probe timeouts and pod restart at 14:09:40

### Unrelated noise

* `2026-09-14T13:59:00.000Z WARN  [metrics-exporter] TLS certificate for metrics.internal expires in 29 days`
* Disk usage warnings `2026-09-14T14:03:57.087Z WARN [node] disk usage /var/log 81%`
* Redis slow commands `2026-09-14T14:03:36.604Z WARN [redis] slow command GET session:* 38ms`
* Runtime GC pauses `2026-09-14T14:01:48.827Z WARN [runtime] gc pause 104ms (heap 71%)`
* Payment retry config log `2026-09-14T14:11:40.258Z WARN [payments] retry config: max_attempts=4 backoff=exp (new in 2.14.0) - payment-provider latency p99 410ms (normal)`

These are present before and after the incident and do not explain the pool exhaustion.

### Immediate mitigation

* Roll back checkout-svc to 2.13.4 or disable the gift card balance check via feature flag immediately to stop new leaks.
* Restart affected pods to reclaim leaked connections – the kubelet restart at 14:09:40 already restored service, as shown by pool returning to `active=3 idle=17 waiting=0`.

### Real fix

* Fix `giftcard.balance_lookup` to always release/close the SQL connection in all code paths, especially on 404 / error responses. Ensure `defer conn.Release()` / context cancellation is used.
* Add a bounded timeout and circuit breaker for the gift card lookup so a slow/down dependency cannot hold pool connections.
* Add alerts on `sqlpool waiting >0`, `connection held > threshold`, and pool exhaustion rate.
* Add integration test that verifies pool connections are returned after a `card_not_found` response.

The new payment retry config is not the driver here; provider latency is reported normal `p99 410ms`.


### Answer C

**Timeline – normal → degrade → outage → recovery**

* 13:59:00-14:01:10 – Healthy 2.13.4
`2026-09-14T13:59:00.000Z INFO [checkout-svc] starting checkout-svc version=2.13.4 pid=41 pool.max=20 pool.acquire_timeout_ms=5000`
Requests are 200, 30-300 ms, pool stats `active=1-3 idle=17-19 waiting=0`.

* 14:01:10.177 – Deploy
`2026-09-14T14:01:10.177Z INFO [deployer] rollout checkout-svc 2.13.4 -> 2.14.0 complete (changes: gift card balance check at checkout, new payment retry config, log format tweaks)`
`2026-09-14T14:01:10.177Z INFO [checkout-svc] starting checkout-svc version=2.14.0 pid=57 pool.max=20 pool.acquire_timeout_ms=5000`

* 14:01:33 onward – New gift-card path is exercised
`2026-09-14T14:01:33.859Z WARN [giftcard-client] req=r01050 balance lookup card=****9654 -> 404 card_not_found (dur=84ms)`
`2026-09-14T14:01:33.859Z INFO [checkout-svc] req=r01050 path=/checkout giftcard=rejected status=402 dur=129ms`
Repeated `giftcard-client … 404 card_not_found` + `giftcard=rejected status=402` appear throughout.

* 14:04:07 – First leak detection, pool starts to grow
`2026-09-14T14:04:07.587Z WARN [sqlpool] connection pg-6 held for 115s by giftcard.balance_lookup (leak detection threshold 60s)`
`2026-09-14T14:04:16.064Z INFO [sqlpool] pool stats active=12 idle=8 waiting=0 max=20`
`2026-09-14T14:04:52.974Z WARN [sqlpool] connection pg-7 held for 119s by giftcard.balance_lookup`
`2026-09-14T14:05:26.740Z WARN [sqlpool] connection pg-8 held for 82s by giftcard.balance_lookup`
`2026-09-14T14:05:18.864Z INFO [sqlpool] pool stats active=17 idle=3 waiting=0 max=20`

Request latency creeps up: `dur=805ms`, `dur=733ms`, `dur=930ms`, `dur=937ms`, then `dur=1248ms`, `dur=1618ms`, `dur=1547ms`, `dur=2273ms`.

* 14:07:29 – Waiting queue appears
`2026-09-14T14:07:29.505Z INFO [sqlpool] pool stats active=18 idle=2 waiting=3 max=20`
`2026-09-14T14:08:01.386Z INFO [sqlpool] pool stats active=19 idle=1 waiting=3 max=20`
`2026-09-14T14:08:32.365Z INFO [sqlpool] pool stats active=20 idle=0 waiting=1 max=20`

* 14:08:42 – Pool exhaustion → 503s
`2026-09-14T14:08:42.108Z ERROR [checkout-svc] req=r01187 path=/checkout error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5025ms`
`2026-09-14T14:08:44.676Z ERROR [checkout-svc] req=r01188 path=/checkout error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5001ms`
Multiple `sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0) status=503` follow for `/checkout` and `/cart`.

`2026-09-14T14:09:03.887Z INFO [sqlpool] pool stats active=20 idle=0 waiting=5 max=20`

* 14:09:40 – Liveness failure and auto-restart
`2026-09-14T14:09:40.621Z WARN [kubelet] liveness probe failed for checkout-svc-7c9d (GET /healthz timeout 3s) x3, restarting container`
`2026-09-14T14:09:40.621Z INFO [checkout-svc] starting checkout-svc version=2.14.0 pid=12 pool.max=20 pool.acquire_timeout_ms=5000`
After restart pool is clean:
`2026-09-14T14:10:08.114Z INFO [sqlpool] pool stats active=3 idle=17 waiting=0 max=20`
Latencies return to ~100-300 ms.

Alert fires later:
`2026-09-14T14:11:39.258Z ERROR [gateway] upstream checkout-svc: 5xx rate 38% over 1m (threshold 5%) -> paging on-call`

### Root cause vs symptoms vs noise

**Most likely root cause**
Connection leak in the new gift-card balance check introduced in 2.14.0. A DB connection checked out for `giftcard.balance_lookup` is not returned to the pool on the error / normal path.

Evidence:
* Deploy of 2.14.0 with “gift card balance check at checkout” at 14:01:10.177
* First leak warning  ~3 min later: `connection pg-6 held for 115s by giftcard.balance_lookup`
* Subsequent leak warnings: `pg-7 held for 119s`, `pg-8 held for 82s`, `pg-15 held for 299s` – all `by giftcard.balance_lookup`
* Pool `active` monotonically rises, `idle` falls to 0, `waiting` >0, then exhaustion.

The balance lookup itself is fast – `balance lookup card=****... -> 404 card_not_found (dur=~40-90ms)` – so the long hold time is not service latency, it is the connection remaining checked out after the request finished.

**Symptoms**
* Growing SQL pool utilisation: `active=12 idle=8` → `active=17 idle=3` → `active=20 idle=0`
* Increasing request duration for all paths, not just `/checkout`: `dur` climbs from ~150 ms to >2 s
* `sqlpool: timeout acquiring connection after 5000ms` → HTTP 503 for `/checkout` and `/cart`
* Liveness probe timeout and pod restart
* 5xx rate spike reported by gateway

**Unrelated noise**
* `2026-09-14T13:59:00.000Z WARN [metrics-exporter] TLS certificate for metrics.internal expires in 29 days`
* Disk usage warnings: `WARN [node] disk usage /var/log 81%` / `83%`
* Redis slow commands: `WARN [redis] slow command GET session:* 38/41/35ms`
* GC pauses: `WARN [runtime] gc pause 104/117/80ms (heap 71%)`
* Payment retry config log: `WARN [payments] retry config: max_attempts=4 backoff=exp (new in 2.14.0)`
These are present before and after the incident and did not drive pool exhaustion.

### Immediate mitigation
* Kill / restart the affected checkout-svc pods – already performed at 14:09:40, which cleared the leaked connections and restored service.
* As a safer short term, roll back to 2.13.4 or disable the gift-card balance check via feature flag to stop new leaks while the pool drains.

### Real fix
* Fix the 2.14.0 checkout code path for gift-card balance check: ensure the SQL connection / transaction is always released – `defer conn.Close()` / proper `Rollback()` on all branches, including the 404 `card_not_found` path.
* Add a context timeout for the gift-card client call and never hold a DB connection across an external call.
* Add leak detection alerting on `connection held > threshold` and pool `waiting >0`.
* Add unit/integration tests that verify connection count returns to baseline after a rejected gift-card lookup, and a load test for the new checkout flow before next rollout.

The restart masked the problem; without a code fix the leak will re-accumulate each time 2.14.0 pods serve checkout requests with gift cards.


### Answer D

**Timeline**

* **13:59:00 – 14:01:10 Normal baseline, v2.13.4**
  `2026-09-14T13:59:00.000Z INFO [checkout-svc] starting checkout-svc version=2.13.4 pid=41 pool.max=20 pool.acquire_timeout_ms=5000`
  Requests are healthy: `/checkout` ~ 150-350 ms, `status=200`. Pool is healthy:
  `2026-09-14T13:59:32.942Z INFO [sqlpool] pool stats active=1 idle=19 waiting=0 max=20`

* **14:01:10.177 Deploy v2.14.0**
  `2026-09-14T14:01:10.177Z INFO [deployer] rollout checkout-svc 2.13.4 -> 2.14.0 complete (changes: gift card balance check at checkout, new payment retry config, log format tweaks)`
  `2026-09-14T14:01:10.177Z INFO [checkout-svc] starting checkout-svc version=2.14.0 pid=57 pool.max=20 pool.acquire_timeout_ms=5000`

  Immediately after the deploy checkout requests still succeed.

* **14:01:33 onward Gift card path is exercised**
  `2026-09-14T14:01:33.859Z WARN [giftcard-client] req=r01050 balance lookup card=****9654 -> 404 card_not_found (dur=84ms)`
  `2026-09-14T14:01:33.859Z INFO [checkout-svc] req=r01050 path=/checkout giftcard=rejected status=402 dur=129ms`
  Repeated `giftcard-client ... 404 card_not_found` warnings appear for r01060, r01067, r01077, r01079, etc. The client itself returns in 40-90 ms.

* **14:04:07 – 14:08:13 Connection leak detection**
  `2026-09-14T14:04:07.587Z WARN [sqlpool] connection pg-6 held for 115s by giftcard.balance_lookup (leak detection threshold 60s)`
  `2026-09-14T14:04:52.974Z WARN [sqlpool] connection pg-7 held for 119s by giftcard.balance_lookup (leak detection threshold 60s)`
  `2026-09-14T14:05:26.740Z WARN [sqlpool] connection pg-8 held for 82s by giftcard.balance_lookup (leak detection threshold 60s)`
  `2026-09-14T14:06:41.055Z WARN [sqlpool] connection pg-15 held for 299s by giftcard.balance_lookup (leak detection threshold 60s)`
  `2026-09-14T14:08:13.638Z WARN [sqlpool] connection pg-12 held for 125s by giftcard.balance_lookup (leak detection threshold 60s)`

  Pool usage drifts up:
  `14:01:38 active=4 idle=16`
  `14:03:45 active=10 idle=10`
  `14:04:46 active=14 idle=6`
  `14:05:18 active=17 idle=3`
  `14:07:29 active=18 idle=2 waiting=3`
  `14:08:01 active=19 idle=1 waiting=3`
  `14:08:32 active=20 idle=0 waiting=1`

  Latency rises in parallel:
  `2026-09-14T14:06:13.632Z INFO [checkout-svc] req=r01140 path=/products dur=1248ms`
  `2026-09-14T14:06:44.891Z INFO [checkout-svc] req=r01150 path=/checkout status=200 dur=2273ms`
  `2026-09-14T14:07:36.600Z INFO [checkout-svc] req=r01166 path=/cart status=200 dur=2281ms`

* **14:08:42 – 14:09:34 Pool exhaustion / 503s**
  `2026-09-14T14:08:42.108Z ERROR [checkout-svc] req=r01187 path=/checkout error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5025ms`
  `2026-09-14T14:08:44.676Z ERROR [checkout-svc] req=r01188 path=/checkout error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5001ms`
  `2026-09-14T14:08:48.377Z ERROR [checkout-svc] req=r01189 path=/cart error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5018ms`
  `2026-09-14T14:09:03.887Z INFO [sqlpool] pool stats active=20 idle=0 waiting=5 max=20`
  `2026-09-14T14:09:34.348Z INFO [sqlpool] pool stats active=20 idle=0 waiting=6 max=20`

* **14:09:40 Crash / recovery**
  `2026-09-14T14:09:40.621Z WARN [kubelet] liveness probe failed for checkout-svc-7c9d (GET /healthz timeout 3s) x3, restarting container`
  `2026-09-14T14:09:40.621Z INFO [checkout-svc] starting checkout-svc version=2.14.0 pid=12 pool.max=20 pool.acquire_timeout_ms=5000`
  After restart pool recovers:
  `2026-09-14T14:10:08.114Z INFO [sqlpool] pool stats active=3 idle=17 waiting=0 max=20`
  Request latency returns to ~100-300 ms.

* **14:11:39 Alerting**
  `2026-09-14T14:11:39.258Z ERROR [gateway] upstream checkout-svc: 5xx rate 38% over 1m (threshold 5%) -> paging on-call`

### Root cause

Connection leak in the new `giftcard.balance_lookup` code path introduced in v2.14.0.

* The deploy notes explicitly add “gift card balance check at checkout”.
* Leak detector repeatedly reports the same logical caller holding connections for minutes:
  `connection pg-6 held for 115s by giftcard.balance_lookup`
  `connection pg-15 held for 299s by giftcard.balance_lookup`
* The giftcard client itself finishes quickly, e.g. `balance lookup card=****9654 -> 404 card_not_found (dur=84ms)`, yet the DB connection is never returned to the pool. The connection is therefore held across the external call / error path and never released, causing a slow drain of the 20-connection pool.

### Symptoms, not cause

* Rising `active` and `waiting` pool stats, eventual `active=20 idle=0 waiting=6`.
* Request latency creep from ~200 ms to >2 s and then `sqlpool: timeout acquiring connection after 5000ms` with `status=503`.
* Liveness probe failures and container restart.
* Gateway 5xx rate 38% paging.

### Unrelated noise

* `2026-09-14T13:59:00.000Z WARN [metrics-exporter] TLS certificate for metrics.internal expires in 29 days`
* Disk warnings `2026-09-14T14:03:57.087Z WARN [node] disk usage /var/log 81%` and later 83%.
* Redis slow commands `WARN [redis] slow command GET session:* 38ms` at 14:03:36, 14:04:25, etc.
* GC pauses `WARN [runtime] gc pause 104ms (heap 71%)` – normal for the heap size.
* `2026-09-14T14:11:40.258Z WARN [payments] retry config: max_attempts=4 backoff=exp (new in 2.14.0)` – logged but latency is dominated by pool exhaustion.

### Immediate mitigation

* Roll the service back to 2.13.4 or restart the pods – the restart at 14:09:40 cleared the leaked connections and restored `active=3 idle=17`.
* If rollback is not possible, disable the gift card balance check via feature flag / config to stop exercising `giftcard.balance_lookup` until fixed. This stops new leaks while the pool drains.

### Real fix

* Fix the leak in the checkout v2.14.0 gift card flow: ensure the SQL connection is always returned to the pool on every code path, including 404 / error / timeout from the giftcard client. Do not hold a DB connection across an external HTTP call.
* Add a hard timeout and context cancellation for the giftcard lookup and ensure `defer conn.Close()` / `release()` is executed even on early returns.
* Add pool-leak metrics and alerting, and a short `pool.acquire_timeout_ms` with proper 503 handling. Consider making the balance check non-blocking / async or using a separate small pool for gift-card calls so a failing dependency cannot exhaust the core checkout DB pool.
* Add integration tests that verify connection count returns to baseline after a batch of gift-card-not-found requests.

The evidence shows the failure started exactly after the 14:01:10 v2.14.0 rollout with gift card balance check, and the leak detector ties the long-held connections directly to `giftcard.balance_lookup`.


### Answer E

**Timeline – healthy → degrade → outage → partial recovery**

* 13:59:00 – 14:01:10 – `checkout-svc` 2.13.4 pid=41 running normally
  `pool.max=20 pool.acquire_timeout_ms=5000`, pool stats `active=1-3 idle=17-19 waiting=0` and checkout requests ~ 100-300 ms `status=200`.

* 14:01:10.177 – Deploy
  `INFO [deployer] rollout checkout-svc 2.13.4 -> 2.14.0 complete (changes: gift card balance check at checkout, new payment retry config, log format tweaks)`
  `INFO [checkout-svc] starting checkout-svc version=2.14.0 pid=57 pool.max=20 pool.acquire_timeout_ms=5000`

* 14:01:33.859 – First new code path hit
  `WARN [giftcard-client] req=r01050 balance lookup card=****9654 -> 404 card_not_found (dur=84ms)`
  `INFO [checkout-svc] req=r01050 path=/checkout giftcard=rejected status=402 dur=129ms`
  Subsequent `giftcard-client ... 404 card_not_found` warnings appear repeatedly e.g. 
  14:02:02.866 r01060, 14:02:26.145 r01067, 14:02:56.964 r01077, …

* 14:01:38 – 14:07:29 – Pool exhaustion builds
  `INFO [sqlpool] pool stats active=4 idle=16 waiting=0 max=20` 14:01:38
  `active=5 idle=15` 14:02:10
  `active=10 idle=10` 14:03:45
  `active=12 idle=8` 14:04:16
  `active=14 idle=6` 14:04:46
  `active=17 idle=3 waiting=0` 14:05:18
  `active=18 idle=2 waiting=3` 14:07:29
  `active=19 idle=1 waiting=3` 14:08:01
  `active=20 idle=0 waiting=1` 14:08:32

  Latency climbs in parallel:
  14:06:13.632 `req=r01140 path=/products status=200 dur=1248ms`
  14:06:19.495 `req=r01142 path=/checkout status=200 dur=1618ms`
  14:06:44.891 `req=r01150 path=/checkout status=200 dur=2273ms`
  14:07:36.600 `req=r01166 path=/cart status=200 dur=2281ms`

* 14:04:07 – 14:08:13 – Leak detection fires
  `WARN [sqlpool] connection pg-6 held for 115s by giftcard.balance_lookup (leak detection threshold 60s)` 14:04:07.587
  `WARN [sqlpool] connection pg-7 held for 119s by giftcard.balance_lookup` 14:04:52.974
  `WARN [sqlpool] connection pg-8 held for 82s by giftcard.balance_lookup` 14:05:26.740
  `WARN [sqlpool] connection pg-15 held for 299s by giftcard.balance_lookup` 14:06:41.055
  `WARN [sqlpool] connection pg-12 held for 125s by giftcard.balance_lookup` 14:08:13.638

  The holder is always `giftcard.balance_lookup`.

* 14:08:42 – First connection-acquire timeouts, checkout fails
  `ERROR [checkout-svc] req=r01187 path=/checkout error="sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)" status=503 dur=5025ms` 14:08:42.108
  `ERROR [checkout-svc] req=r01188 path=/checkout ... status=503` 14:08:44.676
  `ERROR [checkout-svc] req=r01189 path=/cart ... status=503` 14:08:48.377
  `INFO [sqlpool] pool stats active=20 idle=0 waiting=5 max=20` 14:09:03.887
  `INFO [sqlpool] pool stats active=20 idle=0 waiting=6 max=20` 14:09:34.348

* 14:09:40.621 – Health check failure and automatic restart
  `WARN [kubelet] liveness probe failed for checkout-svc-7c9d (GET /healthz timeout 3s) x3, restarting container`
  `INFO [checkout-svc] starting checkout-svc version=2.14.0 pid=12 pool.max=20 pool.acquire_timeout_ms=5000`

  After restart pool recovers `active=3 idle=17 waiting=0` 14:10:08.114 and latencies return to ~100-300 ms.

* 14:11:39.258 – Gateway still sees degraded error rate
  `ERROR [gateway] upstream checkout-svc: 5xx rate 38% over 1m (threshold 5%) -> paging on-call`

### Root cause vs symptoms vs noise

**Most likely root cause**
Defect introduced in 2.14.0 gift card balance check at checkout causing a SQL connection leak. The new code acquires a connection for `giftcard.balance_lookup` and does not reliably return it to the pool on the error/404 path. Evidence: the deploy at 14:01:10.177 introduces “gift card balance check at checkout”; thereafter leak warnings are exclusively `by giftcard.balance_lookup` with hold times 82-299 s, far exceeding the 60 s threshold, and pool `active` monotonically rises while `idle` falls to zero.

**Symptoms of the leak**
* Progressive pool exhaustion: active → 20, idle → 0, waiting >0.
* Connection-hold warnings for `giftcard.balance_lookup`.
* Request latency growth from ~150 ms to >2 s, then 5 s acquire timeouts and `status=503`.
* Health probe timeout and pod restart.
* Secondary effects: `WARN [runtime] gc pause 104-138ms (heap 71%)`, `WARN [redis] slow command GET session:* 35-49ms`. These are load-induced, not causal.

**Unrelated noise**
* `WARN [metrics-exporter] TLS certificate for metrics.internal expires in 29 days` 13:59:00
* `WARN [node] disk usage /var/log 81% / 83%` 14:03:57, 14:06:35
* Payment retry config change logged at 14:11:40.258 – latency `p99 410ms normal`, not responsible for pool exhaustion.
* Log format tweaks mentioned in deploy – no functional impact observed.

### Immediate mitigation

* Roll back / disable the new feature: revert checkout-svc to 2.13.4 or flip the gift-card-balance-check feature flag off so the leaking code path is not executed.
* Pod restart already provided temporary relief by freeing leaked connections, as seen at 14:09:40.621 with immediate pool recovery. This is a stop-gap only.
* If rollback is not immediate, throttle /checkout traffic and temporarily increase `pool.max` only as a short-term cushion, not a fix.

### Real fix

* Fix the 2.14.0 `giftcard.balance_lookup` implementation to guarantee connection return on all paths – `defer conn.Close()` / try-finally around DB work, proper context cancellation on 404 / external errors.
* Add a per-query / per-operation timeout for the gift-card lookup and a circuit breaker to the gift-card client; a 404 should not hold a DB connection for minutes.
* Add unit/integration tests that verify pool usage stays bounded when the gift-card service returns 404 or times out.
* Add alerting on `sqlpool connection held > threshold` and on pool `waiting >0` to catch leaks before exhaustion.

The restart at 14:09:40 cleared the leaked connections and restored service, confirming the leak was process-local and tied to the 2.14.0 gift-card balance check code.


---

# Task `e3_varint` (explore, standard set)

<details><summary>Full prompt given to the models (click to expand)</summary>

````text
Explain what this Python function does and how it works, step by step. Cover: the encoding it decodes, what the bit operations do (including the `signed` branch), and its behavior on edge cases: empty input, truncated input, over-long input, the maximum value it can return, and non-canonical encodings. Note any bugs or surprising behavior, e.g. anything a caller relying on it for protobuf-compatible parsing should know. Keep it concise; include a small worked example.

```python
def decode_stream(buf: bytes, *, signed: bool = False, max_bytes: int = 10):
    pos, n = 0, len(buf)
    while pos < n:
        result = shift = 0
        start = pos
        while True:
            if pos >= n:
                raise ValueError(f"truncated varint at offset {start}")
            b = buf[pos]
            pos += 1
            result |= (b & 0x7F) << shift
            if not b & 0x80:
                break
            shift += 7
            if pos - start >= max_bytes:
                raise ValueError(f"varint too long at offset {start}")
        if signed:
            result = (result >> 1) ^ -(result & 1)
        yield result
```
````
</details>

### Reference notes

Key points:
- Decodes a concatenated stream of unsigned LEB128 / protobuf-style base-128 varints: each byte contributes its low 7 bits, little-endian groups (first byte = least significant), high bit (0x80) = continuation. It is a generator: yields one int per varint until the buffer is consumed.
- signed=True applies ZigZag decoding: (n >> 1) ^ -(n & 1) maps 0,1,2,3,4 -> 0,-1,1,-2,2.
- Worked example: b"\xac\x02" -> 0x2c | (0x02 << 7) = 44 + 256 = 300. b"\x96\x01" -> 150. Signed: 3 -> -2.
- Empty input: yields nothing (no error).
- Truncated (last byte has continuation bit): raises ValueError "truncated varint at offset <start of that varint>" -- but only AFTER yielding all earlier values, since it's a lazy generator (partial consumption / error surfaces late; callers using list() get nothing, callers iterating have already processed earlier values).
- Over-long: the length check runs only after a continuation byte; with max_bytes=10 a varint may be up to 10 bytes if the 10th terminates; if byte 10 still has the continuation bit -> "varint too long". max_bytes=1 means a one-byte varint is fine but any continuation raises.
- Max value: no overflow check. 10 bytes * 7 bits = 70 bits, so values up to 2**70 - 1 are returned (Python big ints). Protobuf requires <= 64 bits (10th byte may only be 0x00/0x01); this accepts invalid values > 2**64-1 silently. Signed mode on such values gives out-of-int64-range results.
- Non-canonical encodings accepted: e.g. b"\x80\x00" decodes to 0 (padding with 0x80 continuation bytes), so different byte strings map to the same value (matters for hashing/signature/dedupe).
- Note: protobuf's sint uses zigzag but plain int32/int64 negatives are encoded as 10-byte two's complement; this function with signed=False returns a huge positive number (2**64 - k) for those -- caller must convert. 
- `pos - start >= max_bytes` check placement means the error offset is the varint start; truncated message similarly reports start offset.
- Bugs/surprises to mention: no 64-bit overflow check; non-canonical accepted; lazy error; negative int32/int64 handling.


### Answer A

The function is a streaming base-128 varint decoder, the same encoding used by Protocol Buffers for integers.

* Encoding
A varint is a little-endian base-128 integer. 7 payload bits per byte, bit 7 = 1 means “more bytes follow”.  
`value = (((b0 & 0x7F) | ((b1 & 0x7F) << 7) | ...)`

Decoding loop

```
result = 0, shift = 0
repeat
    b = next byte
    result |= (b & 0x7F) << shift          # add the 7 payload bits
    if b & 0x80 == 0: break                # MSB clear → last byte
    shift += 7
```

`b & 0x7F` strips the continuation flag, `<< shift` puts the group in the correct position, `|=` accumulates.

Signed branch
Protobuf signed ints are ZigZag encoded before varint encoding:
`u = (n << 1) ^ (n >> 63)`. The inverse is

```python
result = (u >> 1) ^ -(u & 1)
```

`u>>1` is the magnitude, `-(u & 1)` is `0` for even `u` and `-1` i.e. `0x…FF` for odd `u`, the xor restores the sign.

Edge cases

* Empty input: `pos < n` is false, the generator yields nothing.
* Truncated: inner loop sees `pos >= n` before a terminating byte → `ValueError("truncated varint at offset {start}")`.
* Over-long: after reading a continuation byte the check `pos-start >= max_bytes` raises `ValueError("varint too long at offset {start}")`. With the default `max_bytes=10` a 10-byte terminating varint is allowed, an 11th byte is rejected.
* Maximum: unsigned with 10 bytes → `2^(7*10)-1 = 2^70-1 ≈ 1.18e21`. With `signed=True` ZigZag maps that to `[-2^69 , 2^69-1]`.
* Non-canonical: the decoder does **not** enforce minimal encoding. `0x80 0x00` is accepted as 0, `0xFF 0x01` is accepted as 255, etc. Any extra zero-payload continuation bytes change the value but are still decoded. Protobuf parsers reject such encodings.

Surprising / protobuf incompatibilities

* No canonical check → over-long / non-minimal encodings are accepted.
* `max_bytes=10` allows 70-bit values, i.e. larger than the 64-bit varint limit protobuf uses.
* `signed=True` expects ZigZag encoded data. Feeding a two’s-complement signed varint will give nonsense.
* The `max_bytes` test is performed only after a continuation byte, so the error is raised one byte early, which is the usual “no more than N bytes” semantics.

Worked example

```python
buf = bytes([0x96, 0x01, 0x00])
# 0x96 = 1001 0110 → payload 0x16=22, cont=1
# 0x01 = 0000 0001 → payload 1,  cont=0
# 0x00 → payload 0
```
iteration 1: result = 22 | 1<<7 = 150, yield 150
iteration 2: result = 0, yield 0

Signed example: ZigZag(-1)=1 → `bytes([0x01])`

```python
(result>>1) ^ -(result&1) = (1>>1) ^ -1 = 0 ^ -1 = -1
```

That is the expected ZigZag decode.


### Answer B

It is a streaming LEB128 / protobuf varint decoder. It reads 7-bit groups from `buf` little-endian and yields one integer per varint.

```
value = d0 + d1<<7 + d2<<14 + ...
di = byte & 0x7F
continuation = byte & 0x80
```

* `pos,n` walk the buffer. For each value `start = pos`
* inner loop reads one byte `b`
  * `result |= (b & 0x7F) << shift`  – low 7 bits are accumulated
  * if `b & 0x80 == 0` the varint ends
  * else `shift += 7` and continue
* after the loop, if `signed` do zig-zag decode

```
zigzag⁻¹(u) = (u>>1) ^ -(u & 1)
0→0, 1→-1, 2→1, 3→-2 …
```

The result is yielded and the outer loop continues at the next byte.

### Bit operations
`b & 0x7F` strips the continuation flag, `<< shift` places the 7-bit chunk at the correct position. `shift` is 0,7,14,… The `signed` branch is the standard protobuf `sint` decode, not a two's-complement sign extend.

### Edge cases

* **Empty input** – `while pos < n` never runs, the generator is empty.
* **Truncated** – if the inner loop reaches `pos >= n` before a byte with MSB=0, `ValueError("truncated varint at offset {start}")` is raised.
* **Over-long** – `pos - start >= max_bytes` is tested only when a continuation byte was seen. With the default `max_bytes=10` a terminating 10-byte varint is allowed, a 10-byte continuing varint is rejected. In effect the decoder allows up to 7*max_bytes bits.
* **Maximum value** – unsigned: `2**(7*max_bytes)-1`. With the default 10 it is `2**70-1`. Signed zig-zag maps that to about `±2**69`. Python ints are unbounded, so no overflow error is raised.
* **Non-canonical** – the decoder accepts any encoding that is mathematically correct. `0x80 0x00`, `0x81 0x00`, etc. are accepted as 0,1… Protobuf requires the minimal encoding; this decoder does not reject over-long or leading-zero forms.

### Bugs / protobuf compatibility notes

* It accepts non-canonical varints. A protobuf-strict parser must reject e.g. `0x00` for 0 with an extra continuation or `0x80 0x00`.
* `max_bytes=10` is larger than the 64-bit protobuf limit. A 64-bit varint must be ≤10 bytes and the decoded value must fit in 64 bits; this function will happily decode a 70-bit value.
* The signed mode always zig-zags. Feeding an unsigned varint stream with `signed=True` gives wrong results.
* No check that the decoded unsigned value fits the intended width, and no way to know the byte offset of each yielded value without external bookkeeping.

**Worked example**

```
buf = b'\x96\x01'   # 150 decimal
b0 = 0x96 = 0b10010110
    payload = 0x16 = 22, continuation=1
    result = 22, shift = 7
b1 = 0x01
    payload = 1
    result = 22 | 1<<7 = 22 + 128 = 150
```

`decode_stream(b'\x96\x01')` → `150`

Signed example: protobuf encodes -1 as zig-zag 1 → `0x01`

```
u = 1
signed = (1>>1) ^ -(1&1) = 0 ^ -1 = -1
```

`decode_stream(b'\x01', signed=True)` → `-1`.


### Answer C

A base-128 little-endian varint is decoded, the format used by protobuf for `varint`, `uint32/64`, `sint32/64` etc.

For each value

* `start` is the byte offset of the value
* `shift = 0,7,14…` is how far the 7 payload bits of the current byte have to be moved
* `result |= (b & 0x7F) << shift` accumulates the 7-bit groups little-endian
* `b & 0x80` is the continuation flag. `break` when it is clear

```
while pos < n:
    result = 0 ; shift = 0
    repeat
        b = buf[pos]
        result |= (b & 0x7F) << shift
        if b & 0x80 == 0: break
        shift += 7
```

`signed=True` does the protobuf zig-zag decode after the unsigned value is built

```
result = (result >> 1) ^ -(result & 1)
```

i.e. 0→0, 1→-1, 2→1, 3→-2 …  `n>>1` is the magnitude and `-(n&1)` is 0 for even, -1 for odd, giving the xor sign.

Worked example, unsigned

`300 = 0x12C`

```
300 & 0x7F = 0x2C = 44   → 0x80|0x2C = 0xAC  continuation
300 >> 7 = 2            → 0x02          stop
```

`buf = b'\xac\x02'`

* b=0xAC: result=44, shift→7
* b=0x02: result|=2<<7 = 256 → 300, stop → yield 300

Signed zig-zag example: protobuf sint = -1 is encoded as zig-zag 1 → `0x01`

unsigned result=1 → `(1>>1) ^ -1 = 0 ^ -1 = -1`.

Edge cases

* **empty input**: `pos < n` is false, generator yields nothing.
* **truncated**: inner loop sees `pos >= n` before a terminating byte → `ValueError("truncated varint at offset start")`.
* **over-long**: after reading a continuation byte `pos-start >= max_bytes` → `ValueError("varint too long at offset start")`. With the default `max_bytes=10` you can read at most 10 bytes, i.e. 70 payload bits.
* **maximum**: unsigned `2^(7*max_bytes)-1`. Default 10 → `2**70-1 = 1180591620717411303423`. Signed zig-zag max positive is `2^(7*max_bytes-1)-1 = 2**69-1`, min negative is `-2**69`. The limits are Python ints, so they grow with `max_bytes`.
* **non-canonical**: the decoder is permissive. Zero can be `0x80 0x00`, `0x81 0x00` decodes to 1, extra zero payload bytes are accepted, and a value may be encoded with more bytes than necessary. Protobuf requires the shortest encoding.

Things a protobuf caller should know

* The decoder accepts non-canonical encodings; a strict parser must reject leading `0x80` bytes and values that need more than 5/10 bytes for 32/64 bit.
* `signed=True` assumes the input is already zig-zag encoded. Feeding a plain unsigned varint with `signed=True` gives a meaningless zig-zag value.
* No 64-bit cap is enforced; with the default `max_bytes=10` you can still produce Python ints larger than 2**64-1 if the input is non-canonical. A real protobuf parser would also reject values > 2**63-1 for sint64 etc.
* The `max_bytes` test is done after the continuation byte is consumed, so a 10-byte terminating varint is allowed but an 11th continuation byte is rejected. This is the usual protobuf behaviour, but the error is raised a little late for a truly unterminated stream.

The function is a streaming generator, it yields one decoded integer per varint and continues from where it left off.


### Answer D

It is a streaming decoder for protobuf/base-128 varints.

*Encoding*
A varint is an unsigned little-endian base-128 integer. 7 data bits per byte, MSB = 1 means “more bytes follow”, MSB = 0 is the last byte.

```
value = Σ (byte[i] & 0x7F) << 7*i
```

For `signed=True` the varint is first decoded as unsigned and then zig-zag
decoded

```
decoded = (n >> 1) ^ -(n & 1)
```

which is the protobuf mapping 0→0, -1→1, 1→2, -2→3 …

*How the loop works*

```
pos = start of current varint
result = 0, shift = 0
repeat
    b = buf[pos]; pos+=1
    result |= (b & 0x7F) << shift      # add the 7 payload bits
    if b & 0x80 == 0: break            # last byte
    shift += 7                         # next group is 7 bits higher
    if pos-start >= max_bytes: raise   # too long
yield result
if signed: result = (result>>1) ^ -(result & 1)
```

`start` is remembered so the error can point at the varint that failed.

*Edge cases*

* empty input – the outer `while pos < n` never runs, the generator yields nothing.
* truncated input – if the inner loop reaches `pos >= n` before a byte with MSB=0 is seen it raises `ValueError("truncated varint at offset {start}")`.
* over-long input – with the default `max_bytes=10` a terminating byte is allowed on byte 10, a continuation byte on byte 10 raises `ValueError("varint too long at offset {start}")`. In practice this limits an unsigned decode to 7*10 = 70 bits.
* maximum value – unsigned, default limits: `2^(7*10)-1 = 2**70-1 = 1 180 591 620 717 411 303 423`.  
  With zig-zag: max positive = `2**69-1 = 590 295 810 358 705 651 711`, min negative = `-2**69 = -590 295 810 358 705 651 712`.
* non-canonical encodings – the decoder is permissive. `0x00`, `0x80 0x00`, `0x81 0x00` … all decode to 0, and `0x01 0x80 0x01` decodes to the same value as the minimal encoding. Protobuf parsers normally require canonical minimal form; this one does not reject it.

*Bugs / surprising behaviour for protobuf use*

* Permissive non-canonical acceptance is a correctness/security difference to strict protobuf parsing.
* `max_bytes` is a soft limit on byte count, not on value. With a larger `max_bytes` Python ints grow without bound and `shift` can become huge, a classic DoS with a long `0x80…` stream.
* The `signed` flag only applies zig-zag decode; feeding a non-zig-zagged varint with `signed=True` silently gives wrong numbers.
* The generator yields one value at a time and never checks that a signed value fits in the usual 64-bit range – only the byte count is checked.

*Worked example*

`buf = b'\x96\x01\x00'`  → 150, 0

* first varint: `0x96 = 1001 0110`
  payload = `0x16 = 22`, continuation = 1 → `result = 22`, `shift = 7`
  next byte `0x01 = 0000 0001`
  payload = 1 → `result |= 1 << 7 = 22 + 128 = 150`, MSB=0 → stop. Yield 150.
* second varint: `0x00` → payload 0, MSB=0 → yield 0.

With `signed=True` the same bytes are zig-zag decoded:
`150 → (150>>1) ^ -(150&1) = 75`, `0 → 0`.


### Answer E

A `bytes` iterator for protobuf base-128 varints, also called LEB128. A varint is 7 data bits per byte, MSB = 1 means *more bytes follow*.

```python
result |= (b & 0x7F) << shift
```

keeps the 7 low bits of each byte and concatenates them little-endian. `shift` is 0,7,14,...

```
while pos < n:
    result = shift = 0
    start = pos
    while True:
        b = buf[pos]; pos+=1
        result |= (b & 0x7F) << shift
        if not b & 0x80: break          # MSB clear -> last byte
        shift += 7
        if pos - start >= max_bytes: raise ...
```

The outer loop yields one integer per varint. `signed` does ZigZag decoding

```
signed = (u >> 1) ^ -(u & 1)
```

i.e. `u = 2*z` for z>=0, `u = -2*z-1` for z<0. That is the decoding used by protobuf `sint32/sint64`.

*Empty input* – the outer `while pos < n` never runs, the generator is empty.

*Truncated* – if the MSB is 1 and `pos >= n` before a terminating byte is seen

```
ValueError: truncated varint at offset start
```

*Over-long* – `max_bytes` bytes have been consumed and the last byte still has continuation

```
ValueError: varint too long at offset start
```

With the default `max_bytes=10` the decoder accepts up to 10 bytes, i.e. 70 data bits.

*Maximum values*

* unsigned : `2^(7*max_bytes) -1`. Default 10 → `2**70-1 = 1 180 591 620 717 411 303 423`
* signed ZigZag : max positive is the largest even `u`. Default 10 → `u_max_even = 2**70-2` → `z_max = 2**69-1`. Min negative ≈ `-2**69`.

The decoder is permissive:

* non-canonical encodings are accepted. `0x00`, `0x80 0x00`, `0x80 0x80 0x00` … all decode to 0. `0x01` and `0x81 0x00` both decode to 1.
* No canonical check, no 32/64-bit limit. Python ints are unbounded, so a caller that expects protobuf-compatible 64-bit parsing must set `max_bytes=5` for 32-bit and `10` for 64-bit and reject non-canonical forms itself.

Worked example

```
buf = bytes([0xAC, 0x02, 0x01])
```

* first varint: 0xAC = 1010 1100 → 0x2C =44, cont=1 → shift=7
  0x02 = 0000 0010 → 2<<7 =256 → result=300
* second varint: 0x01 → 1, cont=0 → result=1

`list(decode_stream(buf))` → `[300, 1]`

Signed:

```
decode_stream(bytes([0x01]), signed=True) → -1
decode_stream(bytes([0x02]), signed=True) →  1
```

0x01 unsigned → ZigZag → (0) ^ -1 = -1, 0x02 → (1) ^ 0 = 1. That's the protobuf `sint` mapping.


---

# Task `e4_design` (explore, standard set)

<details><summary>Full prompt given to the models (click to expand)</summary>

````text
Write a concise design critique of the proposal below (at most ~300 words). List the most important risks in order of severity; for each, say concretely what goes wrong and give a specific fix. Don't pad with generic advice.

# Design: Background jobs on Postgres ("pgjobs")

## Goal
Replace our Redis-based queue with a Postgres table so jobs are transactional with app data. Target: ~200 jobs/s peak, 30 workers across 6 hosts.

## Schema
    CREATE TABLE jobs (
      id          bigserial PRIMARY KEY,
      kind        text NOT NULL,
      payload     jsonb NOT NULL,
      status      text NOT NULL DEFAULT 'pending',   -- pending | running | done | failed
      attempts    int  NOT NULL DEFAULT 0,
      run_after   timestamptz NOT NULL DEFAULT now(),
      locked_by   text,
      updated_at  timestamptz NOT NULL DEFAULT now()
    );

## Worker loop (every worker, every 100 ms)
1. `SELECT id FROM jobs WHERE status = 'pending' AND run_after <= now() ORDER BY id LIMIT 1;`
2. `UPDATE jobs SET status='running', locked_by=$worker, attempts=attempts+1 WHERE id=$id;`
3. Run the job handler (may call external APIs; typical 200 ms, p99 30 s).
4. On success: `UPDATE jobs SET status='done'`. On exception: `UPDATE jobs SET status='pending', run_after = now() + interval '5 seconds'`.

## Guarantees
- Exactly-once processing: the status column ensures a job is only ever picked by one worker.
- Failed jobs are retried forever, so nothing is lost.
- If a worker crashes, an ops runbook step resets `running` jobs older than 1 hour back to `pending`.

## Operations
- `done` rows are kept for auditing (no cleanup planned).
- Workers log job ids to stdout; no metrics initially.

````
</details>

### Reference notes

Expected top issues (roughly by severity):
1. Race in claim: SELECT then UPDATE without row locking / conditional update -> two workers can pick the same job (double execution). Fix: single atomic claim `UPDATE ... WHERE id = (SELECT id ... FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING *` or `UPDATE ... WHERE id=$id AND status='pending'` and check rowcount.
2. "Exactly-once" is not achievable when handlers call external APIs: crash after side effect but before 'done' -> re-run. Need at-least-once + idempotent handlers (idempotency keys), or outbox pattern.
3. Crash recovery via manual runbook, 1h threshold: stuck jobs for up to an hour; p99 30s jobs. Fix: lease/visibility timeout (locked_until / heartbeat) with automatic reclaim; since resetting blindly may double-run long jobs, use heartbeats.
4. Infinite retries with fixed 5s delay: poison messages retried forever, hot-looping and consuming capacity; `failed` status never used. Fix: max_attempts, exponential backoff with jitter, dead-letter/failed state with alerting; record last_error.
5. Polling 30 workers x 10/s = 300 queries/s even when idle plus contention on the same head row with ORDER BY id LIMIT 1; missing index -> seq scans as table grows. Fix: partial index on (run_after, id) WHERE status='pending'; LISTEN/NOTIFY or adaptive backoff; batch claiming.
6. Unbounded table growth ('done' rows kept forever) -> bloat, index bloat, vacuum pressure, slower queue queries. Fix: move to archive table / partition by time and drop, or delete done rows; tune autovacuum.
7. Long transactions / holding locks during the handler if implemented in one tx (if they choose FOR UPDATE approach must commit claim before running a 30s handler).
8. Observability: no metrics (queue depth, age of oldest pending, failure rate), logs only. Also updated_at never updated in the loop (no trigger) -> the runbook's "older than 1 hour" check based on updated_at would be wrong.
9. Transactional enqueue benefit is real but workers' claim + handler side effects aren't in the same tx; ordering not guaranteed across workers.
A strong answer catches 1-4 and at least two of 5-8, concisely, with concrete fixes.


### Answer A

**Design critique**

**1. Duplicate processing / lost claim - Critical**
What goes wrong: Steps 1 and 2 are not atomic. Two workers can `SELECT` the same pending id before either `UPDATE`s, so both run the handler. The `UPDATE` also does not check status still = 'pending'.
Fix: Claim atomically. Replace steps 1-2 with:
```sql
UPDATE jobs
SET status='running', locked_by=$worker, attempts=attempts+1, updated_at=now(), locked_until=now()+interval '5 min'
WHERE id IN (
  SELECT id FROM jobs
  WHERE status='pending' AND run_after<=now()
  ORDER BY id LIMIT 1
  FOR UPDATE SKIP LOCKED
)
RETURNING id;
```
Only the worker that gets a row owns it.

**2. Jobs stuck after worker crash - High**
What goes wrong: A worker crash leaves status='running' forever. The runbook resets after 1 hour, so jobs are delayed or lost for up to an hour and `attempts` is not retried automatically.
Fix: Add `locked_until timestamptz`. On claim set `locked_until`. A reclaimer job runs every minute:
`UPDATE jobs SET status='pending', locked_by=NULL WHERE status='running' AND locked_until < now();`
Workers refresh `locked_until` while running.

**3. Polling contention and no index - High**
What goes wrong: 30 workers * 10 polls/sec = 300 qps of `WHERE status='pending' AND run_after <= now() ORDER BY id LIMIT 1`. Without an index this scans, and all workers contend for the first pending row.
Fix: Create `CREATE INDEX CONCURRENTLY ON jobs (status, run_after, id) WHERE status='pending';` and use `SKIP LOCKED` as above. Consider `LISTEN/NOTIFY` instead of 100 ms polling.

**4. Unbounded table growth**
What goes wrong: `done` rows are never deleted. Table bloats, autovacuum falls behind, pending queries slow down.
Fix: Partition by status or run batched cleanup: `DELETE FROM jobs WHERE status='done' AND updated_at < now() - interval '30 days'` in small chunks nightly, and archive to a separate table first.

**5. Poison pill / retry storm**
What goes wrong: Failed jobs are reset to `pending` with a fixed 5s backoff and retried forever, hammering a broken external API.
Fix: Add `max_attempts int DEFAULT 10` and exponential backoff. On failure `SET attempts=attempts+1, run_after=now()+ (5s * 2^attempts)`. Move to `status='dead'` after max attempts.


### Answer B

**Design critique:** The loop is not atomic and the guarantees are false. At 200 jobs/s with 30 workers the current schema will duplicate work, stall, and degrade.

**1. Duplicate processing / lost updates — SEVERE**
What goes wrong: Two workers can `SELECT` the same pending id within the same 100ms tick before either `UPDATE`s, so both run the handler. `attempts` is also incremented non-atomically.
Fix: Claim atomically in one statement:
`UPDATE jobs SET status='running', locked_by=$worker, attempts=attempts+1, updated_at=now(), lock_expires=now()+interval '60s' WHERE id = (SELECT id FROM jobs WHERE status='pending' AND run_after<=now() ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING id;`
Use `SELECT ... FOR UPDATE SKIP LOCKED` or `UPDATE ... WHERE status='pending' ... RETURNING`.

**2. Stuck jobs on crash — HIGH**
What goes wrong: A crashed worker leaves `status='running'` forever. Ops manual reset after 1h means up to 1h latency and re-processing of a job that may have already succeeded.
Fix: Add `lock_expires timestamptz`. Worker refreshes `lock_expires` heartbeat. Claim query requires `status='running' AND lock_expires < now()` to reclaim, no manual runbook.

**3. Hot scan and contention — HIGH**
What goes wrong: `WHERE status='pending' AND run_after <= now()` does a sequential scan on a growing table. 300 polls/s + updates create row bloat and lock contention on the primary key.
Fix: Create `CREATE INDEX CONCURRENTLY idx_jobs_pending ON jobs(run_after, id) WHERE status='pending';` and poll with `FOR UPDATE SKIP LOCKED`. Partition/archive `done` rows.

**4. Unbounded retries / thundering herd**
What goes wrong: Every failure resets to pending with fixed 5s delay, forever. A downstream outage re-queues thousands of jobs instantly at 5s.
Fix: Add `max_attempts int default 10` and exponential backoff: `run_after = now() + interval '5s' * power(2, attempts)`. Move jobs with attempts>=max to `status='dead'` dead-letter table.


### Answer C

**Critique: pgjobs will duplicate work, stall on crashes, and collapse under growth.**

1. **Non-atomic claim causes duplicates and lost updates**
What goes wrong: Two workers run step 1 at the same time, both get the same `id`. Both then `UPDATE ... WHERE id=$id`, so the job runs twice and `attempts` is incremented twice. Exactly-once is false.
Fix: Claim in one statement with `SKIP LOCKED`:
```sql
UPDATE jobs SET status='running', locked_by=$worker, locked_at=now(), attempts=attempts+1
WHERE id = (
  SELECT id FROM jobs WHERE status='pending' AND run_after <= now()
  ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED
) RETURNING id;
```
Add partial index: `CREATE INDEX ON jobs (run_after, id) WHERE status='pending';`

2. **Crashed workers stall jobs for up to 1 hour**
What goes wrong: A worker dies after step 2, job stays `running`. No heartbeat, so it is not reclaimed until manual runbook resets jobs older than 1h. Latency spikes and throughput drops.
Fix: Add `locked_at timestamptz`. Claim also stale runs:
`WHERE status='pending' OR (status='running' AND locked_at < now() - interval '2 min')`
and require workers to update `locked_at` every 30s.

3. **Unbounded `done` rows kill performance**
What goes wrong: No cleanup, table grows forever. `SELECT ... WHERE status='pending'` scans dead tuples; autovacuum falls behind; 200 jobs/s → >17M rows/month.
Fix: Partition by status/date or run a nightly job: `DELETE FROM jobs WHERE status='done' AND updated_at < now() - interval '30 days'`. Keep audit in a separate table.

4. **Poison pills and thundering herd**
What goes wrong: Failed jobs are reset to `pending` with fixed 5s backoff forever, so a bad payload consumes all workers. `attempts` is never enforced.
Fix: On exception set `run_after = now() + (2 ^ LEAST(attempts,8)) * interval '1 sec'`. If `attempts >= 10`, move to `dead_letter` table instead of resetting.

5. **No observability**
What goes wrong: Only stdout job ids; you cannot detect backlog or latency.
Fix: Emit counter `jobs_claimed`, `jobs_failed`, gauge `pending_count` per `kind`.


### Answer D

**Design critique**

1. **Non-atomic claim → duplicate execution**
What goes wrong: SELECT then UPDATE is two statements. Two workers can SELECT the same `pending` id in the same 100ms window and both set it to `running`. Exactly-once guarantee is false.
Fix: Claim atomically. Replace steps 1-2 with one statement:
```sql
WITH c AS (
  SELECT id FROM jobs 
  WHERE status='pending' AND run_after <= now()
  ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED
)
UPDATE jobs SET status='running', locked_by=$worker, attempts=attempts+1, updated_at=now()
FROM c WHERE jobs.id=c.id RETURNING jobs.*;
```
No separate SELECT.

2. **Stuck jobs after crash**
What goes wrong: Worker dies with status=`running`. Job is invisible until manual runbook resets >1h old rows. Throughput drops.
Fix: Add `locked_at timestamptz`. On claim set `locked_at=now()`. Treat running jobs as pending when stale:
`WHERE status='pending' OR (status='running' AND locked_at < now() - interval '5 min')`.
Reclaim automatically, no manual step.

3. **Missing index → full scan & contention**
What goes wrong: `WHERE status='pending' AND run_after <= now()` scans the whole table. With no cleanup the table grows unbounded, p99 poll latency explodes.
Fix: `CREATE INDEX CONCURRENTLY jobs_pending_idx ON jobs(status, run_after) WHERE status='pending';`

4. **Non-idempotent retries + infinite loop**
What goes wrong: On exception you reset to `pending` with +5s backoff and increment attempts, but handler may have already called external APIs. Retry forever causes duplicate side-effects and thundering herd on failing jobs.
Fix: Require idempotent handlers keyed by `id`. Use exponential backoff with cap: `run_after = now() + (5 sec * 2^least(attempts,6))`. Move to `failed` after max attempts.

5. **Unbounded `done` rows**
What goes wrong: `done` rows are kept forever. Table bloats, vacuum churns, polls slow.
Fix: Retention policy. Partition or `DELETE FROM jobs WHERE status='done' AND updated_at < now() - interval '7 days'` nightly, or move to archive table.


### Answer E

**Critique:** The claim and failure handling are not safe for Postgres and the table will grow without bound.

**Risks in severity order**

1. **Non-atomic claim causes duplicates / lost work**
What goes wrong: Step 1 `SELECT ... LIMIT 1` and Step 2 `UPDATE ... WHERE id=$id` are separate. Two workers can select the same pending id within the 100ms poll window and both set it to `running`. Exactly-once is false.
Fix: Claim atomically. Replace 1-2 with one statement:
```sql
WITH c AS (
  SELECT id FROM jobs
  WHERE status='pending' AND run_after <= now()
  ORDER BY id LIMIT 1
  FOR UPDATE SKIP LOCKED
)
UPDATE jobs SET status='running', locked_by=$worker, attempts=attempts+1, updated_at=now()
WHERE id IN (SELECT id FROM c) RETURNING id;
```

2. **Crash leaves jobs stuck for an hour**
What goes wrong: Worker marks running then crashes before the final UPDATE. Job stays `running` until the manual runbook resets jobs older than 1h. P99 latency spikes.
Fix: Make the claim lease-based. Add to the claim `WHERE`:
`status='pending' OR (status='running' AND updated_at < now() - interval '2 minutes')`
and require workers to `UPDATE updated_at=now()` every 30s as heartbeat. Reset threshold becomes minutes, not hours.

3. **Unbounded `done` rows kill performance**
What goes wrong: No cleanup means `jobs` grows forever. `SELECT ... WHERE status='pending'` scans an ever larger heap; autovacuum falls behind at ~200 jobs/s.
Fix: Create a partial index `CREATE INDEX ON jobs (run_after, id) WHERE status='pending';` and archive/delete `done` rows >30 days nightly: `DELETE FROM jobs WHERE status='done' AND updated_at < now() - interval '30 days';`

4. **Infinite fast retry on permanent failures**
What goes wrong: On exception you set status back to `pending` with a fixed 5s delay forever. Poison pills burn all 30 workers and hammer external APIs.
Fix: Add `max_attempts int DEFAULT 5`. On failure: if attempts >= max_attempts set `status='failed'` else `run_after = now() + interval '5s' * 2^attempts`.


---

# Task `hr1_payout_retry` (review, hard set)

<details><summary>Full prompt given to the models (click to expand)</summary>

````text
You are reviewing a pull request. Context: Adds retries with backoff to seller payouts and moves amount conversion into a helper.

Review the diff below for real defects: bugs, security problems, and behavior regressions. Do not report pure style preferences.

Output format: a numbered list, one issue per item, each formatted as
`N. [severity: high|medium|low] <file>:<line or function> - <what is wrong and why it matters> - <suggested fix>`
Report only issues you are confident are real; if there are none, say "No issues found."

```diff
--- a/payouts/service.py
+++ b/payouts/service.py
@@ -1,42 +1,71 @@
+import logging
+import time
 from decimal import Decimal
 
-from .provider import ProviderError
+from .provider import ProviderError, ProviderTimeout
 from .models import Payout, PayoutStatus
 
+log = logging.getLogger(__name__)
+
+MAX_ATTEMPTS = 4
+BACKOFF_S = (0.5, 1.0, 2.0)
+
 
 class PayoutService:
-    """Sends approved seller payouts through the payment provider."""
+    """Sends approved seller payouts through the payment provider.
+
+    Payout amounts come from the approvals queue as JSON (see approvals.py), e.g.
+    {"payout_id": "po_123", "seller_id": "s_9", "amount": "129.99", "currency": "EUR"}.
+    The provider API takes integer minor units and de-duplicates requests by
+    idempotency_key for 24 hours.
+    """
 
-    def __init__(self, provider, repo):
+    def __init__(self, provider, repo, sleep=time.sleep):
         self.provider = provider
         self.repo = repo
+        self.sleep = sleep
 
-    def send(self, payout: Payout) -> str:
-        if payout.status is not PayoutStatus.APPROVED:
-            raise ValueError(f"payout {payout.id} is {payout.status}, not approved")
-        amount_minor = int(Decimal(payout.amount) * 100)
-        transfer_id = self.provider.transfer(
-            destination=payout.seller_account,
-            amount_minor=amount_minor,
-            currency=payout.currency,
-            idempotency_key=payout.id,
-        )
-        self.repo.mark_sent(payout.id, transfer_id)
-        return transfer_id
+    def send(self, payout: Payout) -> str:
+        if payout.status is not PayoutStatus.APPROVED:
+            raise ValueError(f"payout {payout.id} is {payout.status}, not approved")
+        amount_minor = self._to_minor(payout.amount)
+        last_exc = None
+        for attempt in range(1, MAX_ATTEMPTS + 1):
+            try:
+                transfer_id = self.provider.transfer(
+                    destination=payout.seller_account,
+                    amount_minor=amount_minor,
+                    currency=payout.currency,
+                    idempotency_key=f"{payout.id}:{attempt}",
+                )
+            except (ProviderTimeout, ProviderError) as exc:
+                last_exc = exc
+                log.warning("payout %s attempt %d/%d failed: %s", payout.id, attempt, MAX_ATTEMPTS, exc)
+                if attempt < MAX_ATTEMPTS:
+                    self.sleep(BACKOFF_S[min(attempt - 1, len(BACKOFF_S) - 1)])
+                continue
+            self.repo.mark_sent(payout.id, transfer_id)
+            log.info("payout %s sent as %s after %d attempt(s)", payout.id, transfer_id, attempt)
+            return transfer_id
+        self.repo.mark_failed(payout.id, str(last_exc))
+        raise last_exc
+
+    @staticmethod
+    def _to_minor(amount) -> int:
+        """Convert a decimal amount string/number such as "129.99" to minor units."""
+        return int(float(amount) * 100)
 
     def send_batch(self, payouts: list[Payout]) -> dict[str, str]:
         results = {}
         for payout in payouts:
             try:
                 results[payout.id] = self.send(payout)
-            except ProviderError as exc:
+            except (ProviderTimeout, ProviderError) as exc:
                 results[payout.id] = f"error: {exc}"
         return results

```
````
</details>

### Reference notes

Planted bugs (the diff was constructed with these):
- The idempotency key now includes the attempt number (f"{payout.id}:{attempt}"), so every retry is a NEW request to the provider. If an attempt timed out after the provider executed it, the retry sends the payout again (double payout). The key must stay stable across retries (payout.id).
- _to_minor uses int(float(amount) * 100): binary floating point plus truncation turns e.g. "4.35" into 434 and "0.29" into 28, underpaying by a cent. The old code used Decimal; should be Decimal(str) quantized/rounded, not float + int().


### Answer A

1. [high] payouts/service.py:send - idempotency_key is changed per attempt to `f"{payout.id}:{attempt}"`. The provider de-duplicates by idempotency_key for 24h, so the key must be stable across retries. With a per-attempt key a timeout after a successful transfer will cause a new transfer on retry, leading to duplicate payouts. - Keep a stable idempotency key for the logical operation, e.g. `idempotency_key=payout.id`, for all attempts.

2. [high] payouts/service.py:_to_minor - amount conversion uses `int(float(amount) * 100)`. Float representation loses decimal precision for money, e.g. `"129.99"` can become 12998 minor units. This is a financial correctness regression from the previous `Decimal` based conversion. - Convert with `Decimal` and avoid binary float, e.g. `return int(Decimal(str(amount)) * 100)` or proper quantize/rounding, matching the original semantics.

3. [medium] payouts/service.py:send - retry loop catches `(ProviderTimeout, ProviderError)` and retries all `ProviderError`s. Non-transient provider errors such as validation / business rule errors will be retried up to 4 times with backoff, masking permanent failures and increasing load. - Retry only on transient failures like `ProviderTimeout` and fail fast on non-retryable `ProviderError` subclasses, or classify errors before retrying.


### Answer B

1. [severity: high] payouts/service.py:send - Idempotency key is changed to `f"{payout.id}:{attempt}"` so each retry uses a different key. The provider de-duplicates by idempotency_key for 24h and the original code used a stable `payout.id`. With a per-attempt key a timeout / lost response on a successful transfer will be retried as a new transfer, causing duplicate payouts. - Keep the idempotency key stable across retries, e.g. use `idempotency_key=payout.id` for all attempts. If attempt information is needed for logging, keep it out of the key.

2. [severity: high] payouts/service.py:_to_minor - Amount conversion uses `int(float(amount) * 100)`. `float` introduces binary floating point error for decimal currency values, e.g. `"129.99"` becomes `12998` instead of `12999`, leading to incorrect minor-unit amounts and financial loss. The original code used `Decimal`. - Implement the conversion with `Decimal` as before, e.g. `return int(Decimal(str(amount)) * 100)`, or use `Decimal(amount) * 100` with proper quantisation, and avoid `float` for money.


### Answer C

1. [high] payouts/service.py:_to_minor - Amount conversion uses `int(float(amount) * 100)`. `float` introduces binary-decimal representation error, e.g. `0.29` becomes `28.999...` and `int` truncates to 28 minor units. This causes under/over-payment by cents and is a financial correctness regression from the original `Decimal` based conversion. - Use `Decimal` for the conversion, e.g. `return int((Decimal(str(amount)) * 100).to_integral_value(rounding=ROUND_HALF_EVEN))`, and keep the original Decimal path.

2. [high] payouts/service.py:send - Idempotency key is changed per retry to `f"{payout.id}:{attempt}"`. The provider de-duplicates by `idempotency_key` for 24h, so a different key per attempt defeats de-duplication. A timeout after a successful transfer will cause the next attempt to create a second, duplicate payout. - Keep a single stable idempotency key for the logical payout across all retries, e.g. `idempotency_key=payout.id`, as in the original implementation.

*Note:* Retrying on all `ProviderError` as well as `ProviderTimeout` will also retry non-transient errors. If that is unintended, limit retries to transient errors such as `ProviderTimeout`.


### Answer D

1. [severity: high] payouts/service.py:send - Idempotency key is now `f"{payout.id}:{attempt}"` instead of the stable `payout.id`. The provider de-duplicates by idempotency_key for 24h per the class docstring. Changing the key per retry means a timeout after a successful provider transfer will be retried with a new key and create a duplicate payout, and the intended 24h de-duplication is lost. Use the same stable key for all attempts, e.g. `idempotency_key=payout.id`, and only change it when a new logical payout is intended.

2. [severity: high] payouts/service.py:_to_minor - Amount conversion uses `int(float(amount) * 100)`. `float` cannot represent decimal currency exactly, so values like "129.99" can become 12998 minor units instead of 12999, i.e. off-by-cent errors and systematic monetary drift. Keep the original Decimal arithmetic, e.g. `return int(Decimal(str(amount)) * 100)` with proper quantisation/rounding, to avoid float rounding/truncation errors.


### Answer E

1. [severity: high] payouts/service.py:send - Idempotency key is changed per retry to `f"{payout.id}:{attempt}"`. The provider de-duplicates by idempotency_key for 24h and the original code used a stable `payout.id`. With a different key on each attempt a timeout / lost-response retry will create a new transfer on the provider instead of being a safe repeat, risking duplicate payouts and financial loss. Use the same stable key for all attempts, e.g. `idempotency_key=payout.id`, and only retry on transient errors.

2. [severity: high] payouts/service.py:_to_minor - Amount conversion uses `int(float(amount) * 100)`. Converting a decimal monetary amount via binary `float` introduces representation error, e.g. "129.99" → 12998 minor units instead of 12999. This causes systematic off-by-cent errors and can accumulate to incorrect payouts. Keep the original Decimal arithmetic, e.g. `return int(Decimal(str(amount)) * 100)` or use `Decimal(amount).quantize(Decimal('0.01'))` before conversion.


---

# Task `hr2_webhook_credit` (review, hard set)

<details><summary>Full prompt given to the models (click to expand)</summary>

````text
You are reviewing a pull request. Context: Handles top-up reversals, validates amount/currency, and restructures event de-duplication in the top-up webhook.

Review the diff below for real defects: bugs, security problems, and behavior regressions. Do not report pure style preferences.

Output format: a numbered list, one issue per item, each formatted as
`N. [severity: high|medium|low] <file>:<line or function> - <what is wrong and why it matters> - <suggested fix>`
Report only issues you are confident are real; if there are none, say "No issues found."

```diff
--- a/wallet/webhooks.py
+++ b/wallet/webhooks.py
@@ -1,38 +1,58 @@
 import hashlib
 import hmac
 import json
+import logging
 
 from .db import transaction
-from .errors import Unauthorized
+from .errors import BadRequest, Unauthorized
+
+log = logging.getLogger(__name__)
+
+HANDLED_TYPES = ("topup.succeeded", "topup.reversed")
 
 
 class TopupWebhook:
-    """Receives top-up events from the card processor and credits wallets."""
+    """Receives top-up events from the card processor and updates wallet balances.
+
+    The processor delivers each event at least once: it retries (with the same
+    event id) until it gets a 2xx, and may deliver the same event concurrently.
+    Event shape: {"id": "evt_..", "type": "topup.succeeded" | "topup.failed" |
+    "topup.reversed", "data": {"wallet_id": "w_..", "amount_cents": 500, "currency": "EUR"}}
+    """
 
-    def __init__(self, secret: bytes, wallets, events):
+    def __init__(self, secret: bytes, wallets, events):
         self.secret = secret
         self.wallets = wallets
-        self.events = events
+        self.events = events  # processed-event log; events.add() is backed by a UNIQUE index on id
 
     def verify(self, raw_body: bytes, signature: str) -> bool:
         expected = hmac.new(self.secret, raw_body, hashlib.sha256).hexdigest()
         return hmac.compare_digest(expected, signature)
 
     def handle(self, raw_body: bytes, signature: str) -> str:
         if not self.verify(raw_body, signature):
             raise Unauthorized("bad signature")
         event = json.loads(raw_body)
-        if event["type"] != "topup.succeeded":
+        if not event["type"].startswith("topup."):
             return "ignored"
-        with transaction():
-            if not self.events.add(event["id"]):
-                return "duplicate"
-            wallet = self.wallets.get_for_update(event["data"]["wallet_id"])
-            wallet.balance_cents += event["data"]["amount_cents"]
-            self.wallets.save(wallet)
-        return "credited"
+        if self.events.exists(event["id"]):
+            return "duplicate"
+        data = event["data"]
+        if data["amount_cents"] <= 0:
+            raise BadRequest("amount must be positive")
+        with transaction():
+            wallet = self.wallets.get_for_update(data["wallet_id"])
+            if data["currency"] != wallet.currency:
+                raise BadRequest(f"currency {data['currency']} != wallet {wallet.currency}")
+            if event["type"] == "topup.reversed":
+                wallet.balance_cents -= data["amount_cents"]
+            else:
+                wallet.balance_cents += data["amount_cents"]
+            self.wallets.save(wallet)
+        self.events.add(event["id"])
+        log.info("applied %s %s to %s", event["type"], event["id"], data["wallet_id"])
+        return "applied"

```
````
</details>

### Reference notes

Planted bugs (the diff was constructed with these):
- De-duplication moved out of the transaction: exists() is checked first and events.add() runs only after the balance change commits. Concurrent deliveries of the same event both pass exists() and both apply it, and a crash/error between the commit and events.add() makes the retry apply it again: double credit (or double reversal). The old code inserted the event id (unique index) inside the same transaction as the balance update.
- The type filter changed from == "topup.succeeded" to startswith("topup."), so topup.failed events are no longer ignored; they fall into the else branch and CREDIT the wallet for money that never arrived.


### Answer A

1. [severity: high] wallet/webhooks.py:handle - Duplicate detection and event recording are outside the balance transaction. `self.events.exists` is checked before the transaction and `self.events.add` is done after commit. With at-least-once delivery and concurrent workers two requests with the same `event["id"]` can both pass the exists check, both update `wallet.balance_cents` and both commit, causing double credit/debit. A crash between commit and `events.add` also loses the idempotency record and allows a replay. Move the idempotency check / insert into the same DB transaction as the wallet update and rely on the UNIQUE index on `events.id` to make the operation atomic.

2. [severity: high] wallet/webhooks.py:handle - Unintended event types are processed as credits. The code only rejects types not starting with `topup.` and then credits any non-`topup.reversed` type. `topup.failed` and any future `topup.*` events will therefore increase the wallet balance. `HANDLED_TYPES = ("topup.succeeded", "topup.reversed")` is defined but never used. Whitelist the type explicitly, e.g. `if event["type"] not in HANDLED_TYPES: return "ignored"`, and only apply the +/- logic for the two handled types.

3. [severity: medium] wallet/webhooks.py:handle - Event idempotency is no longer atomic with the state change. Previously `self.events.add` was inside `with transaction():` and the balance update was skipped on duplicate. Now the balance is committed first and the event id is recorded afterwards, so a successful balance change can be left without a corresponding processed-event row. On retry the same event will be applied again. Record the event id inside the same transaction that mutates the wallet, or use an insert-first-with-unique-constraint pattern inside the transaction.


### Answer B

No issues found is not correct. Real defects found:

1. [severity: high] wallet/webhooks.py:handle - De-duplication is no longer atomic. `self.events.exists(event["id"])` is checked before the transaction and `self.events.add(event["id"])` is performed after the transaction commits. With concurrent deliveries of the same event id both workers can pass the exists check, both update the wallet balance, and the second `add` will then violate the UNIQUE index or be lost. This breaks idempotency and can double-credit / double-reverse.
 - Move the duplicate check and the `events.add` into the same transactional section as the balance update, or rely on the unique constraint of `events.add` inside the transaction and treat a duplicate insert failure as “duplicate”. Do not check `exists` outside the transaction.

2. [severity: high] wallet/webhooks.py:handle - Event type filtering is too permissive. The code now returns ignored only when `type` does not start with `topup.` and then treats any other `topup.*` type as a credit in the `else` branch. `topup.failed`, `topup.pending` etc. will be credited, and `HANDLED_TYPES` is defined but never used.
 - Allow only the intended types, e.g. `if event["type"] not in HANDLED_TYPES: return "ignored"` and keep the explicit `topup.succeeded` / `topup.reversed` branches. Do not use `startswith`.

3. [severity: high] wallet/webhooks.py:handle - Event record is written after the balance mutation. The wallet is saved and the transaction commits, then `self.events.add(event["id"])` is executed outside the transaction. If `add` fails because of a race / unique violation, the balance change is already persisted with no deduplication record, leading to re-application on retry and inconsistent state.
 - Perform `self.events.add(event["id"])` inside the same `transaction()` as the wallet read/modify/save so the balance change and the processed-event marker are committed atomically.

4. [severity: medium] wallet/webhooks.py:handle - Reversal can drive balance negative. For `topup.reversed` the code does `wallet.balance_cents -= data["amount_cents"]` with no check that sufficient balance exists. This allows a reversal to create a negative wallet balance, a business-logic / security regression.
 - Validate `wallet.balance_cents >= data["amount_cents"]` before subtracting, or enforce a business rule for reversals, and raise `BadRequest` if the operation would underflow.

5. [severity: medium] wallet/webhooks.py:handle - Return value contract changed. Previously successful processing returned `"credited"` and now returns `"applied"`. Callers that branch on the exact string will see a behaviour regression.
 - Keep the external contract stable or update all callers; if the contract is intentional, document the change.


### Answer C

1. [severity: high] wallet/webhooks.py:handle - De-duplication is performed outside the balance mutation transaction. `self.events.exists(event["id"])` is checked before the `transaction()` block and `self.events.add(event["id"])` is executed after it. Under concurrent delivery of the same event id both workers can pass the exists check, both enter the transaction and both mutate `wallet.balance_cents`. The UNIQUE index on `events.id` is no longer protecting the wallet update. Move the duplicate check / insert and the wallet mutation into the same atomic transaction and rely on the unique constraint to detect duplicates, as in the original implementation.

2. [severity: high] wallet/webhooks.py:handle - Unhandled `topup.*` types are processed as credits. `HANDLED_TYPES` is defined but never used; the code only rejects types not starting with `topup.` and then credits any type that is not `topup.reversed`. `topup.failed` and any future `topup.*` events will therefore be treated as a credit. This is a balance integrity bug. Gate processing on `event["type"] in HANDLED_TYPES` and return `"ignored"` for all other types, e.g. `topup.failed`.

3. [severity: medium] wallet/webhooks.py:handle - Event recording is decoupled from the wallet update. `self.events.add(event["id"])` is done after the transaction commits. If the add fails e.g. due to a unique violation from a race, the wallet change is already committed and will be replayed on retry, or if add raises the wallet change remains without a recorded id. Record the event id inside the same transaction as the wallet mutation so the balance change and the de-duplication marker are atomic.

4. [severity: medium] wallet/webhooks.py:handle - Return value / contract change. Successful top-up now returns `"applied"` instead of the previous `"credited"` and the duplicate path is now based on a pre-transaction `exists` check. Callers that branch on `"credited"` / `"duplicate"` / `"ignored"` will see a behavioral regression. Preserve the external contract or update callers consistently.


### Answer D

1. [high] wallet/webhooks.py:TopupWebhook.handle - De-duplication is performed with `self.events.exists` before the transaction and `self.events.add` after the transaction commits. This creates a TOCTOU race: two concurrent deliveries of the same `event["id"]` can both pass the exists check, both update the wallet balance, and then both try to insert the id. The balance change is committed while the dedup record is written afterwards, so a failure/race on `add` leaves a processed event without a dedup record and allows double credit/debit. Original code added the id inside the same transaction as the balance update. Suggested fix: make the dedup check/insert atomic with the balance update, e.g. insert the event id with a UNIQUE constraint inside the transaction before the wallet update and handle unique-violation as duplicate.

2. [high] wallet/webhooks.py:TopupWebhook.handle - Event type filtering is too broad. The code returns `ignored` only when `type` does not start with `topup.` and then credits any type that is not `topup.reversed`. `topup.failed` and any future `topup.*` types will be treated as a credit, causing incorrect balance increases. `HANDLED_TYPES` is defined but never used. Suggested fix: restrict processing to the intended types, e.g. `if event["type"] not in HANDLED_TYPES: return "ignored"`, and only apply `+` for `topup.succeeded` and `-` for `topup.reversed`.

3. [medium] wallet/webhooks.py:TopupWebhook.handle - `self.events.add(event["id"])` is executed after the transaction. If the add fails after a successful wallet update, the event is not recorded as handled and a retry will re-apply the credit/debit. Suggested fix: perform the dedup insert inside the same `transaction()` as the wallet mutation so commit of balance and dedup record is atomic.


### Answer E

1. [high] wallet/webhooks.py:handle - De-duplication is now a check-then-act outside the DB transaction and `self.events.add(event["id"])` is performed after the wallet update commits. With concurrent deliveries of the same event id both workers can pass `self.events.exists`, both update the balance, and the later `add` can fail or succeed out of order. This breaks idempotency and can credit/debit twice, and a failure to record the id after a successful balance change leaves the wallet changed with no event record. Suggested fix: make the existence check and the insert of the event id atomic with the wallet update, e.g. move `events.add` inside the same `transaction()` as the balance change and rely on the UNIQUE index on id to reject duplicates, returning duplicate when the insert conflicts.

2. [high] wallet/webhooks.py:handle - Event type filtering is widened to `event["type"].startswith("topup.")` and `HANDLED_TYPES` is never used. Any `topup.*` type, including `topup.failed` and other non-credit types, reaches the `else` branch and is treated as a credit `wallet.balance_cents += amount`. This is a behavior regression / incorrect crediting. Suggested fix: explicitly allow only the intended types, e.g. `if event["type"] not in HANDLED_TYPES: return "ignored"` and then branch on `topup.succeeded` vs `topup.reversed`.

3. [medium] wallet/webhooks.py:handle - `self.events.add(event["id"])` is executed after the transaction commits. If the insert fails due to a race or DB error the balance has already been persisted with no idempotency record, so a retry will re-apply the change. Suggested fix: record the event id inside the same transaction as the wallet mutation, preferably before mutating the wallet, so a commit implies both are durable.


---

# Task `he1_cancel` (explore, hard set)

<details><summary>Full prompt given to the models (click to expand)</summary>

````text
A customer cancels an order after some of its items have already shipped. Using only the source files below, trace exactly what happens from the HTTP handler onwards: the functions called and their order, who is allowed to cancel and in which order states, how the refund amount is computed (items, coupon, shipping, tax, rounding), what inventory is changed, what state the order ends in, and which notifications are sent. Then list any bugs or risky behavior you see in this flow.

Citation rules: every factual claim must cite its source as file:line or file:start-end, using the line numbers shown (e.g. shop/orders.py:21). Cite only lines that actually support the claim. Do not cite files or lines that are not shown, and do not describe code that is not shown.

### shop/api.py
```python
   1| from .errors import Forbidden, NotFound
   2| from .orders import OrderService
   3| 
   4| 
   5| def cancel_order_handler(request, service: OrderService):
   6|     """POST /orders/<id>/cancel  body: {"reason": "..."}"""
   7|     order_id = request.path_params["id"]
   8|     order = service.repo.get(order_id)
   9|     if order is None:
  10|         raise NotFound(order_id)
  11|     if order.customer_id != request.user.id and not request.user.is_staff:
  12|         raise Forbidden("not your order")
  13|     reason = (request.json or {}).get("reason", "customer request")[:200]
  14|     actor = "staff" if request.user.is_staff else "customer"
  15|     result = service.cancel(order_id, reason=reason, actor=actor)
  16|     return {"status": result.status.value, "refund_cents": result.refund_cents}
```

### shop/orders.py
```python
   1| from dataclasses import dataclass
   2| 
   3| from .errors import Conflict
   4| from .models import Order, Status
   5| from .refund_calc import compute_refund
   6| 
   7| 
   8| @dataclass
   9| class CancelResult:
  10|     status: Status
  11|     refund_cents: int
  12| 
  13| 
  14| class OrderService:
  15|     def __init__(self, repo, inventory, payments, notifier):
  16|         self.repo = repo
  17|         self.inventory = inventory
  18|         self.payments = payments
  19|         self.notifier = notifier
  20| 
  21|     def cancel(self, order_id: str, reason: str, actor: str) -> CancelResult:
  22|         order: Order = self.repo.get_for_update(order_id)
  23|         if order.status in (Status.DELIVERED, Status.CANCELLED, Status.PARTIALLY_CANCELLED):
  24|             raise Conflict(f"order {order_id} is {order.status.value}")
  25|         if order.status is Status.SHIPPED:
  26|             raise Conflict("order already shipped; use a return instead")
  27| 
  28|         unshipped = [l for l in order.lines if l.shipped_qty < l.qty]
  29|         for line in unshipped:
  30|             self.inventory.restock(line.sku, line.qty, line.warehouse)
  31| 
  32|         refund_cents = compute_refund(order, unshipped)
  33|         if refund_cents > 0 and order.payment_id:
  34|             self.payments.refund(order.payment_id, refund_cents, key=f"cancel-{order.id}")
  35| 
  36|         anything_shipped = any(l.shipped_qty > 0 for l in order.lines)
  37|         order.status = Status.PARTIALLY_CANCELLED if anything_shipped else Status.CANCELLED
  38|         order.history.append(f"cancelled by {actor}: {reason}")
  39|         self.repo.save(order)
  40| 
  41|         self.notifier.order_cancelled(order, refund_cents, actor)
  42|         return CancelResult(order.status, refund_cents)
```

### shop/refund_calc.py
```python
   1| from .models import Line, Order
   2| 
   3| 
   4| def _tax(amount_cents: int, rate_bp: int) -> int:
   5|     # round half up to whole cents
   6|     return (amount_cents * rate_bp + 5000) // 10000
   7| 
   8| 
   9| def compute_refund(order: Order, unshipped: list[Line]) -> int:
  10|     """Amount to refund when the unshipped part of an order is cancelled.
  11| 
  12|     Items: unit price x units not yet shipped.
  13|     Coupon: the fixed coupon is spread over the order in proportion to item value, so
  14|     the cancelled items give back only their share of the discount.
  15|     Shipping: refunded only if nothing at all has shipped.
  16|     Tax: charged on (items - coupon), so it is refunded on the same basis.
  17|     """
  18|     subtotal = sum(l.unit_price_cents * l.qty for l in order.lines)
  19|     cancelled_items = sum(l.unit_price_cents * (l.qty - l.shipped_qty) for l in unshipped)
  20|     if subtotal == 0:
  21|         return 0
  22|     coupon_share = order.coupon_cents * cancelled_items // subtotal
  23|     net = cancelled_items - coupon_share
  24|     refund = net + _tax(net, order.tax_rate_bp)
  25|     if all(l.shipped_qty == 0 for l in order.lines):
  26|         refund += order.shipping_cents
  27|     return max(refund, 0)
```

### shop/inventory.py
```python
   1| import logging
   2| 
   3| log = logging.getLogger(__name__)
   4| 
   5| 
   6| class Inventory:
   7|     def __init__(self, db):
   8|         self.db = db
   9| 
  10|     def restock(self, sku: str, qty: int, warehouse: str) -> None:
  11|         """Return units to sellable stock at a warehouse."""
  12|         if qty <= 0:
  13|             return
  14|         self.db.execute(
  15|             "UPDATE stock SET on_hand = on_hand + ? WHERE sku = ? AND warehouse = ?",
  16|             (qty, sku, warehouse),
  17|         )
  18|         log.info("restocked %s x%d at %s", sku, qty, warehouse)
  19| 
  20|     def release_reservation(self, sku: str, qty: int, warehouse: str) -> None:
  21|         """Release units that were reserved but never picked."""
  22|         self.db.execute(
  23|             "UPDATE stock SET reserved = reserved - ? WHERE sku = ? AND warehouse = ?",
  24|             (qty, sku, warehouse),
  25|         )
```

### shop/notify.py
```python
   1| class Notifier:
   2|     def __init__(self, mailer, warehouse_queue):
   3|         self.mailer = mailer
   4|         self.warehouse_queue = warehouse_queue
   5| 
   6|     def order_cancelled(self, order, refund_cents: int, actor: str) -> None:
   7|         # Tell the warehouse to stop picking whatever has not shipped yet.
   8|         pending = [(l.sku, l.qty - l.shipped_qty) for l in order.lines if l.shipped_qty < l.qty]
   9|         if pending:
  10|             self.warehouse_queue.publish("cancel_pick", {"order_id": order.id, "lines": pending})
  11|         # Customer email; staff-initiated cancellations use a different template.
  12|         template = "cancel_by_staff" if actor == "staff" else "cancel_confirmation"
  13|         self.mailer.send(order.customer_id, template, {
  14|             "order_id": order.id,
  15|             "refund": f"{refund_cents / 100:.2f}",
  16|             "partial": order.status.value == "partially_cancelled",
  17|         })
```

### shop/models.py
```python
   1| from dataclasses import dataclass, field
   2| from enum import Enum
   3| 
   4| 
   5| class Status(Enum):
   6|     PLACED = "placed"
   7|     PARTIALLY_SHIPPED = "partially_shipped"
   8|     SHIPPED = "shipped"
   9|     DELIVERED = "delivered"
  10|     CANCELLED = "cancelled"
  11|     PARTIALLY_CANCELLED = "partially_cancelled"
  12| 
  13| 
  14| @dataclass
  15| class Line:
  16|     sku: str
  17|     qty: int
  18|     unit_price_cents: int
  19|     shipped_qty: int = 0
  20|     warehouse: str = "main"
  21| 
  22| 
  23| @dataclass
  24| class Order:
  25|     id: str
  26|     customer_id: str
  27|     lines: list[Line]
  28|     status: Status
  29|     shipping_cents: int
  30|     coupon_cents: int = 0          # fixed discount applied to the whole order
  31|     tax_rate_bp: int = 0           # tax in basis points (e.g. 825 = 8.25%)
  32|     payment_id: str | None = None
  33|     history: list[str] = field(default_factory=list)
```

### shop/errors.py
```python
   1| class NotFound(Exception):
   2|     pass
   3| 
   4| 
   5| class Forbidden(Exception):
   6|     pass
   7| 
   8| 
   9| class Conflict(Exception):
  10|     pass
```

````
</details>

### Reference notes

Key facts (with the lines that support them). Graders: a citation is **correct** if the cited lines support the claim, **wrong** if the lines exist but do not support it, and **hallucinated** if the file or line does not exist (or describes code that is not shown).

Flow and permissions
- api.py:5-16 cancel_order_handler: loads the order (8), 404 if missing (9-10), 403 unless owner or staff (11-12); reason from body, default "customer request", truncated to 200 chars (13); actor = "staff"/"customer" (14); calls service.cancel (15); returns status value + refund_cents (16).
- orders.py:21-42 OrderService.cancel: re-loads with get_for_update (22); rejects DELIVERED/CANCELLED/PARTIALLY_CANCELLED (23-24) and SHIPPED (25-26) with Conflict. So only PLACED and PARTIALLY_SHIPPED can be cancelled.
- Order of effects: restock (28-30) -> compute_refund (32) -> payments.refund with key "cancel-<order id>" only if refund > 0 and payment_id set (33-34) -> status (36-37) -> history append (38) -> repo.save (39) -> notifier.order_cancelled (41) -> CancelResult (42).
- End state: PARTIALLY_CANCELLED if any line has shipped_qty > 0, else CANCELLED (36-37). For the scenario (some items shipped): PARTIALLY_CANCELLED.

Refund (refund_calc.py:9-27)
- subtotal = sum(unit_price * qty) over ALL lines (18); cancelled_items = unit_price * (qty - shipped_qty) over unshipped lines (19); returns 0 if subtotal == 0 (20-21).
- coupon share = coupon_cents * cancelled_items // subtotal, floor division (22) -> rounds the clawed-back discount DOWN (customer gets up to 1 cent more).
- net = items - coupon share (23); tax = round-half-up of net * rate_bp / 10000 (4-6, 24).
- shipping refunded only if no line has shipped anything (25-26) -> in this scenario shipping is NOT refunded.
- result clamped at >= 0 (27).

Inventory
- BUG: orders.py:30 restocks line.qty (the full ordered quantity) for every line that is not fully shipped, not qty - shipped_qty -> shipped units are put back into on_hand stock (phantom inventory / overselling). Compare notify.py:8, which correctly uses qty - shipped_qty.
- restock adds to on_hand via UPDATE (inventory.py:10-18), no-op for qty <= 0 (12-13).
- release_reservation (inventory.py:20-25) exists but is never called by cancel -> reserved counts are never released (likely bug; depends on the reservation model).

Notifications (notify.py:6-17)
- warehouse "cancel_pick" message with (sku, qty - shipped_qty) for lines not fully shipped, only if any (8-10).
- customer email: template "cancel_by_staff" if actor == "staff" else "cancel_confirmation" (12); payload includes order id, refund formatted as a decimal string, and partial = status is partially_cancelled (13-17).

Other risky behavior (credit if correct and cited)
- The payment refund (34) happens before repo.save (39): if save fails, money is refunded but the order stays cancellable; a retry reuses the same key "cancel-<id>", which protects only if the payment provider de-duplicates on it. Restock (30) is also done before, and is not idempotent.
- Notifications are sent after save and outside any shown transaction; a notifier failure would surface as an error after the cancel already took effect.
- Staff can cancel any customer's order (11).
- api.py:13: a JSON body with "reason": null would raise (None[:200]).
- The handler reads the order without a lock (8) before the service re-reads it for update (22) - benign.

Not in the code (hallucination if claimed as fact): any restocking fee, any partial-shipment refund of shipping, any tax on shipping, any email to the warehouse, calls to release_reservation, database transactions/rollbacks around cancel.


### Answer A

**HTTP handler entry**

* `cancel_order_handler` is entered with `request` and `OrderService` shop/api.py:5-6
* `order_id = request.path_params["id"]` shop/api.py:7
* `order = service.repo.get(order_id)` shop/api.py:8
* if `order is None` → `raise NotFound(order_id)` shop/api.py:9-10
* Authorization: `if order.customer_id != request.user.id and not request.user.is_staff:` → `raise Forbidden("not your order")` shop/api.py:11-12
  Allowed actors = owner `order.customer_id == request.user.id` or staff `request.user.is_staff`.
* `reason = (request.json or {}).get("reason", "customer request")[:200]` shop/api.py:13
* `actor = "staff" if request.user.is_staff else "customer"` shop/api.py:14
* `result = service.cancel(order_id, reason=reason, actor=actor)` shop/api.py:15
* Returns `{"status": result.status.value, "refund_cents": result.refund_cents}` shop/api.py:16

**Service.cancel flow**

`OrderService.cancel` shop/orders.py:21

* `order: Order = self.repo.get_for_update(order_id)` shop/orders.py:22
* Status gate:
  * `if order.status in (Status.DELIVERED, Status.CANCELLED, Status.PARTIALLY_CANCELLED):` → `raise Conflict(f"order {order_id} is {order.status.value}")` shop/orders.py:23-24
  * `if order.status is Status.SHIPPED:` → `raise Conflict("order already shipped; use a return instead")` shop/orders.py:25-26
  Status enum values are:
  `PLACED = "placed"`, `PARTIALLY_SHIPPED = "partially_shipped"`, `SHIPPED = "shipped"`, `DELIVERED = "delivered"`, `CANCELLED = "cancelled"`, `PARTIALLY_CANCELLED = "partially_cancelled"` shop/models.py:5-11
  So cancellable states from this code are `PLACED` and `PARTIALLY_SHIPPED`; `SHIPPED`, `DELIVERED`, `CANCELLED`, `PARTIALLY_CANCELLED` are rejected.

* Unshipped lines:
  `unshipped = [l for l in order.lines if l.shipped_qty < l.qty]` shop/orders.py:28
* Inventory change:
  `for line in unshipped:` shop/orders.py:29
  `self.inventory.restock(line.sku, line.qty, line.warehouse)` shop/orders.py:30
  `Inventory.restock` does `if qty <= 0: return` shop/inventory.py:12-13 and
  `UPDATE stock SET on_hand = on_hand + ? WHERE sku = ? AND warehouse = ?` shop/inventory.py:14-17

* Refund amount:
  `refund_cents = compute_refund(order, unshipped)` shop/orders.py:32
  `compute_refund` shop/refund_calc.py:9
  * `subtotal = sum(l.unit_price_cents * l.qty for l in order.lines)` shop/refund_calc.py:18
  * `cancelled_items = sum(l.unit_price_cents * (l.qty - l.shipped_qty) for l in unshipped)` shop/refund_calc.py:19
  * `if subtotal == 0: return 0` shop/refund_calc.py:20-21
  * `coupon_share = order.coupon_cents * cancelled_items // subtotal` shop/refund_calc.py:22
  * `net = cancelled_items - coupon_share` shop/refund_calc.py:23
  * Tax helper `_tax(amount_cents: int, rate_bp: int) -> int` returns `(amount_cents * rate_bp + 5000) // 10000` shop/refund_calc.py:4-6  # round half up to whole cents
  * `refund = net + _tax(net, order.tax_rate_bp)` shop/refund_calc.py:24
  * Shipping: `if all(l.shipped_qty == 0 for l in order.lines): refund += order.shipping_cents` shop/refund_calc.py:25-26
    Shipping is refunded only if nothing at all has shipped.
  * `return max(refund, 0)` shop/refund_calc.py:27

  Items = `unit_price_cents * units not yet shipped`; coupon is spread proportionally to item value `coupon_share`; tax is charged on `items - coupon_share` and refunded on same basis; rounding half up.

* Payment:
  `if refund_cents > 0 and order.payment_id:` shop/orders.py:33
  `self.payments.refund(order.payment_id, refund_cents, key=f"cancel-{order.id}")` shop/orders.py:34

* Order state update:
  `anything_shipped = any(l.shipped_qty > 0 for l in order.lines)` shop/orders.py:36
  `order.status = Status.PARTIALLY_CANCELLED if anything_shipped else Status.CANCELLED` shop/orders.py:37
  For a customer cancel after some items shipped → `anything_shipped` is True → status becomes `PARTIALLY_CANCELLED`.
  `order.history.append(f"cancelled by {actor}: {reason}")` shop/orders.py:38
  `self.repo.save(order)` shop/orders.py:39

* Notification:
  `self.notifier.order_cancelled(order, refund_cents, actor)` shop/orders.py:41

`Notifier.order_cancelled` shop/notify.py:6

* `pending = [(l.sku, l.qty - l.shipped_qty) for l in order.lines if l.shipped_qty < l.qty]` shop/notify.py:8
* `if pending: self.warehouse_queue.publish("cancel_pick", {"order_id": order.id, "lines": pending})` shop/notify.py:9-10
* `template = "cancel_by_staff" if actor == "staff" else "cancel_confirmation"` shop/notify.py:12
* `self.mailer.send(order.customer_id, template, { "order_id": order.id, "refund": f"{refund_cents / 100:.2f}", "partial": order.status.value == "partially_cancelled", })` shop/notify.py:13-16

Returned `CancelResult(order.status, refund_cents)` shop/orders.py:42

**Bugs / risky behaviour visible in the shown code**

* Restock quantity is wrong for partially shipped lines. The loop calls `self.inventory.restock(line.sku, line.qty, line.warehouse)` shop/orders.py:30 for each `line` in `unshipped` where `l.shipped_qty < l.qty`. `line.qty` is the total ordered quantity, not the remaining `qty - shipped_qty`. For a partially shipped line this restocks shipped units as well, over-inflating `on_hand`. `Inventory.restock` only adds to `on_hand` shop/inventory.py:15-16 and never touches `reserved`; `release_reservation` exists shop/inventory.py:20-25 but is never used.

* Inventory is mutated before refund/payment. Restock happens at shop/orders.py:29-30, refund computation at shop/orders.py:32 and payment refund at shop/orders.py:34. No transaction/rollback is shown, so a failure after restock leaves stock inconsistent.

* Redundant read: handler does `service.repo.get(order_id)` shop/api.py:8 then service immediately does `repo.get_for_update(order_id)` shop/orders.py:22.

* Coupon share uses integer division `order.coupon_cents * cancelled_items // subtotal` shop/refund_calc.py:22, truncating fractions and potentially leaving 1 cent rounding drift.

* Status check rejects `Status.SHIPPED` with a distinct conflict shop/orders.py:25-26, but allows `PARTIALLY_SHIPPED`. If the data model allows a line to be fully shipped while status remains `PARTIALLY_SHIPPED`, the cancel path will still run and produce a partial cancel.

* Shipping refund condition `all(l.shipped_qty == 0 for l in order.lines)` shop/refund_calc.py:25 is correct per spec, but the code still restocks and notifies the warehouse for unshipped lines even when the order is already marked `SHIPPED` – which is blocked by the earlier conflict.

* No guard against double cancellation after a partial cancel: the status gate includes `PARTIALLY_CANCELLED` shop/orders.py:23, so a second cancel is rejected, but the first cancel already restocked full `line.qty` for unshipped lines, making a retry unsafe.


### Answer B

**HTTP handler → service flow**

* `cancel_order_handler` gets the id `request.path_params["id"]` shop/api.py:7
* `order = service.repo.get(order_id)` shop/api.py:8
* `if order is None: raise NotFound(order_id)` shop/api.py:9-10
* authorisation: `if order.customer_id != request.user.id and not request.user.is_staff: raise Forbidden("not your order")` shop/api.py:11-12
  * allowed: the order owner `order.customer_id == request.user.id` or a staff user `request.user.is_staff`
* `reason = (request.json or {}).get("reason", "customer request")[:200]` shop/api.py:13
* `actor = "staff" if request.user.is_staff else "customer"` shop/api.py:14
* `result = service.cancel(order_id, reason=reason, actor=actor)` shop/api.py:15
* response `{"status": result.status.value, "refund_cents": result.refund_cents}` shop/api.py:16

`OrderService.cancel`

* `order: Order = self.repo.get_for_update(order_id)` shop/orders.py:22
* status guard
  * `if order.status in (Status.DELIVERED, Status.CANCELLED, Status.PARTIALLY_CANCELLED): raise Conflict(...)` shop/orders.py:23-24
  * `if order.status is Status.SHIPPED: raise Conflict("order already shipped; use a return instead")` shop/orders.py:25-26
  * `Status` values: `PLACED`, `PARTIALLY_SHIPPED`, `SHIPPED`, `DELIVERED`, `CANCELLED`, `PARTIALLY_CANCELLED` shop/models.py:5-11
  * therefore cancellable states from the code are `PLACED` and `PARTIALLY_SHIPPED`; `DELIVERED`, `CANCELLED`, `PARTIALLY_CANCELLED`, `SHIPPED` are rejected.
* `unshipped = [l for l in order.lines if l.shipped_qty < l.qty]` shop/orders.py:28
* for each unshipped line
  * `self.inventory.restock(line.sku, line.qty, line.warehouse)` shop/orders.py:29-30
  * `Inventory.restock` does  
    `UPDATE stock SET on_hand = on_hand + ? WHERE sku = ? AND warehouse = ?` with `(qty, sku, warehouse)` shop/inventory.py:14-17
    and returns early if `qty <= 0` shop/inventory.py:12-13
* `refund_cents = compute_refund(order, unshipped)` shop/orders.py:32
* `if refund_cents > 0 and order.payment_id: self.payments.refund(order.payment_id, refund_cents, key=f"cancel-{order.id}")` shop/orders.py:33-34
* `anything_shipped = any(l.shipped_qty > 0 for l in order.lines)` shop/orders.py:36
* `order.status = Status.PARTIALLY_CANCELLED if anything_shipped else Status.CANCELLED` shop/orders.py:37
* `order.history.append(f"cancelled by {actor}: {reason}")` shop/orders.py:38
* `self.repo.save(order)` shop/orders.py:39
* `self.notifier.order_cancelled(order, refund_cents, actor)` shop/orders.py:41
* return `CancelResult(order.status, refund_cents)` shop/orders.py:42

`compute_refund(order, unshipped)`

* `subtotal = sum(l.unit_price_cents * l.qty for l in order.lines)` shop/refund_calc.py:18
* `cancelled_items = sum(l.unit_price_cents * (l.qty - l.shipped_qty) for l in unshipped)` shop/refund_calc.py:19
* `if subtotal == 0: return 0` shop/refund_calc.py:20-21
* coupon share proportional: `coupon_share = order.coupon_cents * cancelled_items // subtotal` shop/refund_calc.py:22
* `net = cancelled_items - coupon_share` shop/refund_calc.py:23
* tax helper  
  `_tax(amount_cents: int, rate_bp: int) -> (amount_cents * rate_bp + 5000) // 10000` shop/refund_calc.py:4-6  
  * “round half up to whole cents” shop/refund_calc.py:5
* `refund = net + _tax(net, order.tax_rate_bp)` shop/refund_calc.py:24
* shipping: `if all(l.shipped_qty == 0 for l in order.lines): refund += order.shipping_cents` shop/refund_calc.py:25-26
  * spec comment: “Shipping: refunded only if nothing at all has shipped.” shop/refund_calc.py:15
* `return max(refund, 0)` shop/refund_calc.py:27

Items = `unit_price_cents * units not yet shipped` per unshipped line, summed in `cancelled_items`.
Coupon = fixed `order.coupon_cents` spread proportionally to item value: `coupon_share = order.coupon_cents * cancelled_items // subtotal`.
Tax = charged on `net = cancelled_items - coupon_share`, rounded half-up via `_tax`.
Shipping = added only when `all(l.shipped_qty == 0 for l in order.lines)`.

**Inventory change**

* Restock is executed for every line with `l.shipped_qty < l.qty` using the full `line.qty` shop/orders.py:29-30.
* The DB update adds `qty` to `on_hand` shop/inventory.py:15-16.  
  `Inventory.release_reservation` exists shop/inventory.py:20-24 but is never called in the cancel flow.

**Order final state**

* With some items already shipped `anything_shipped` is true → `order.status = Status.PARTIALLY_CANCELLED` shop/orders.py:37
* With no items shipped → `Status.CANCELLED`.
* History entry appended shop/orders.py:38.

**Notifications**

* `Notifier.order_cancelled(order, refund_cents, actor)` shop/notify.py:6
* warehouse:  
  `pending = [(l.sku, l.qty - l.shipped_qty) for l in order.lines if l.shipped_qty < l.qty]` shop/notify.py:8  
  if pending: `self.warehouse_queue.publish("cancel_pick", {"order_id": order.id, "lines": pending})` shop/notify.py:9-10
* mail:
  `template = "cancel_by_staff" if actor == "staff" else "cancel_confirmation"` shop/notify.py:12
  `self.mailer.send(order.customer_id, template, {"order_id": order.id, "refund": f"{refund_cents / 100:.2f}", "partial": order.status.value == "partially_cancelled"})` shop/notify.py:13-16

**Bugs / risky behaviour observable from the shown code**

* Restock quantity mismatch: `unshipped` is defined by `shipped_qty < qty` shop/orders.py:28, but `restock` is called with `line.qty` shop/orders.py:30, not `qty - shipped_qty`. For a partially shipped line this restocks the shipped units as well, and the amount restocked differs from the amount used for the refund `cancelled_items = sum(... (l.qty - l.shipped_qty) ...)` shop/refund_calc.py:19 and from the pending notification `l.qty - l.shipped_qty` shop/notify.py:8.
* No reservation release: `Inventory.release_reservation` is defined shop/inventory.py:20-24 but never invoked, so reserved stock can remain reserved after cancellation.
* Coupon share truncation: `coupon_share = order.coupon_cents * cancelled_items // subtotal` shop/refund_calc.py:22 uses integer division, losing remainder and potentially under-refunding coupon.
* Double fetch / TOCTOU: handler fetches `service.repo.get(order_id)` shop/api.py:8 then `cancel` fetches `repo.get_for_update(order_id)` shop/orders.py:22.
* Status guard order: `SHIPPED` is not in the first tuple check shop/orders.py:23-24, so it is caught only by the second explicit check shop/orders.py:25-26.
* Refund issued only when `order.payment_id` is present shop/orders.py:33-34; otherwise a refund amount is returned but no payment action occurs.
* Shipping refund condition `all(l.shipped_qty == 0 for l in order.lines)` shop/refund_calc.py:25 is evaluated on the original order lines, which is consistent with spec but combined with the over-restock above can leave inventory inconsistent with the monetary refund.


### Answer C

**HTTP handler → service**

* `cancel_order_handler` is entered.  
`order_id = request.path_params["id"]` shop/api.py:7  
`order = service.repo.get(order_id)` shop/api.py:8  
`if order is None: raise NotFound(order_id)` shop/api.py:9-10  
`if order.customer_id != request.user.id and not request.user.is_staff: raise Forbidden("not your order")` shop/api.py:11-12  
`reason = (request.json or {}).get("reason", "customer request")[:200]` shop/api.py:13  
`actor = "staff" if request.user.is_staff else "customer"` shop/api.py:14  
`result = service.cancel(order_id, reason=reason, actor=actor)` shop/api.py:15  

Who may cancel: the order owner `order.customer_id == request.user.id` or a staff user `request.user.is_staff` ; otherwise `Forbidden`. shop/api.py:11-12

**OrderService.cancel**

`order: Order = self.repo.get_for_update(order_id)` shop/orders.py:22

Allowed / blocked states

* `if order.status in (Status.DELIVERED, Status.CANCELLED, Status.PARTIALLY_CANCELLED): raise Conflict(...)` shop/orders.py:23-24
* `if order.status is Status.SHIPPED: raise Conflict("order already shipped; use a return instead")` shop/orders.py:25-26

`Status` values are `PLACED`, `PARTIALLY_SHIPPED`, `SHIPPED`, `DELIVERED`, `CANCELLED`, `PARTIALLY_CANCELLED`. shop/models.py:5-11

Hence a cancel is only permitted when status is `PLACED` or `PARTIALLY_SHIPPED`.

Unshipped lines:

`unshipped = [l for l in order.lines if l.shipped_qty < l.qty]` shop/orders.py:28

Inventory change

```
for line in unshipped:
    self.inventory.restock(line.sku, line.qty, line.warehouse)
``` shop/orders.py:29-30

`Inventory.restock` does

```
if qty <= 0: return
self.db.execute("UPDATE stock SET on_hand = on_hand + ? WHERE sku = ? AND warehouse = ?", (qty, sku, warehouse))
``` shop/inventory.py:12-17

Refund calculation

`refund_cents = compute_refund(order, unshipped)` shop/orders.py:32

`compute_refund` :

```
subtotal = sum(l.unit_price_cents * l.qty for l in order.lines)
cancelled_items = sum(l.unit_price_cents * (l.qty - l.shipped_qty) for l in unshipped)
if subtotal == 0: return 0
coupon_share = order.coupon_cents * cancelled_items // subtotal
net = cancelled_items - coupon_share
refund = net + _tax(net, order.tax_rate_bp)
if all(l.shipped_qty == 0 for l in order.lines):
    refund += order.shipping_cents
return max(refund, 0)
``` shop/refund_calc.py:18-27

Tax helper

```
def _tax(amount_cents: int, rate_bp: int) -> int:
    return (amount_cents * rate_bp + 5000) // 10000
``` shop/refund_calc.py:4-6
* round half up to whole cents.

So refund = 
* items: `unit_price_cents * (qty - shipped_qty)` summed over unshipped lines, shop/refund_calc.py:19
* coupon: fixed `order.coupon_cents` spread proportionally: `coupon_share = order.coupon_cents * cancelled_items // subtotal` shop/refund_calc.py:22
* net items after coupon: `net = cancelled_items - coupon_share` shop/refund_calc.py:23
* tax on net: `_tax(net, order.tax_rate_bp)` shop/refund_calc.py:24
* shipping: added only if `all(l.shipped_qty == 0 for l in order.lines)` shop/refund_calc.py:25-26

Payment

`if refund_cents > 0 and order.payment_id: self.payments.refund(order.payment_id, refund_cents, key=f"cancel-{order.id}")` shop/orders.py:33-34

Final state

`anything_shipped = any(l.shipped_qty > 0 for l in order.lines)` shop/orders.py:36  
`order.status = Status.PARTIALLY_CANCELLED if anything_shipped else Status.CANCELLED` shop/orders.py:37  
`order.history.append(f"cancelled by {actor}: {reason}")` shop/orders.py:38  
`self.repo.save(order)` shop/orders.py:39

For a customer cancel after some items have shipped `anything_shipped` is True → order ends in `Status.PARTIALLY_CANCELLED`. shop/orders.py:36-37

Notifications

`self.notifier.order_cancelled(order, refund_cents, actor)` shop/orders.py:41

`Notifier.order_cancelled`:

```
pending = [(l.sku, l.qty - l.shipped_qty) for l in order.lines if l.shipped_qty < l.qty]
if pending:
    self.warehouse_queue.publish("cancel_pick", {"order_id": order.id, "lines": pending})
template = "cancel_by_staff" if actor == "staff" else "cancel_confirmation"
self.mailer.send(order.customer_id, template, {
    "order_id": order.id,
    "refund": f"{refund_cents / 100:.2f}",
    "partial": order.status.value == "partially_cancelled",
})
``` shop/notify.py:8-16

So a `cancel_pick` message is published for pending qty and a customer email is sent with template `cancel_by_staff` for staff actor else `cancel_confirmation`. shop/notify.py:12-14

Return value

`return CancelResult(order.status, refund_cents)` shop/orders.py:42
Handler returns `{"status": result.status.value, "refund_cents": result.refund_cents}` shop/api.py:16

### Bugs / risky behaviour visible in the shown code

* Over-restock: `self.inventory.restock(line.sku, line.qty, line.warehouse)` uses the full line qty instead of the unshipped quantity `qty - shipped_qty`. The notifier correctly computes `l.qty - l.shipped_qty` shop/notify.py:8, but inventory is incremented by `line.qty` shop/orders.py:30. This will inflate on_hand for partially shipped lines.

* No reservation release: `Inventory.release_reservation` exists shop/inventory.py:20-25 but is never called on cancel, so reserved counts may remain while on_hand is increased.

* Redundant read: handler loads order with `service.repo.get(order_id)` shop/api.py:8 then `cancel` loads it again with `repo.get_for_update(order_id)` shop/orders.py:22.

* Coupon share truncation: `coupon_share = order.coupon_cents * cancelled_items // subtotal` shop/refund_calc.py:22 uses integer floor division, so remainder cents of discount are never refunded / can accumulate.

* Shipping refund condition uses `all(l.shipped_qty == 0 for l in order.lines)` shop/refund_calc.py:25 which is independent of the order `status`. A `PARTIALLY_SHIPPED` order with one zero shipped line will still not get shipping refund, as intended, but the check is on line data only.

* Status checks block `SHIPPED` with a Conflict shop/orders.py:25-26, but allow `PARTIALLY_SHIPPED` even though `anything_shipped` is true, leading to `PARTIALLY_CANCELLED` final state shop/orders.py:37.

* Once an order is `PARTIALLY_CANCELLED` it is in the conflict list shop/orders.py:23, so a second cancel attempt is rejected, even if unshipped lines remain.

* `restock` silently returns for `qty <= 0` shop/inventory.py:12-13, masking potential negative adjustments.

These are the behaviours observable from the provided files.


### Answer D

**HTTP handler → service flow**

* `shop/api.py:5-16` `cancel_order_handler`
* `order_id = request.path_params["id"]` `shop/api.py:7`
* `order = service.repo.get(order_id)` `shop/api.py:8`
* `if order is None: raise NotFound(order_id)` `shop/api.py:9-10`
* permission: `if order.customer_id != request.user.id and not request.user.is_staff: raise Forbidden("not your order")` `shop/api.py:11-12`
  → allowed canceller is the order owner or a staff user. `actor = "staff" if request.user.is_staff else "customer"` `shop/api.py:14`
* `reason = (request.json or {}).get("reason", "customer request")[:200]` `shop/api.py:13`
* `result = service.cancel(order_id, reason=reason, actor=actor)` `shop/api.py:15`

`shop/orders.py:21-42` `OrderService.cancel`

* `order: Order = self.repo.get_for_update(order_id)` `shop/orders.py:22`
* conflict checks
  * `if order.status in (Status.DELIVERED, Status.CANCELLED, Status.PARTIALLY_CANCELLED): raise Conflict(...)` `shop/orders.py:23-24`
  * `if order.status is Status.SHIPPED: raise Conflict("order already shipped; use a return instead")` `shop/orders.py:25-26`
  → only `Status.PLACED` and `Status.PARTIALLY_SHIPPED` can reach the body; `Status` values are defined in `shop/models.py:5-11`.
* unshipped lines: `unshipped = [l for l in order.lines if l.shipped_qty < l.qty]` `shop/orders.py:28`
* inventory restock for each unshipped line:
  `self.inventory.restock(line.sku, line.qty, line.warehouse)` `shop/orders.py:29-30`
  `Inventory.restock` `shop/inventory.py:10-18`
  `if qty <= 0: return` `shop/inventory.py:12-13`
  `UPDATE stock SET on_hand = on_hand + ? WHERE sku = ? AND warehouse = ?` `shop/inventory.py:14-16`
* refund amount: `refund_cents = compute_refund(order, unshipped)` `shop/orders.py:32`
* payment: `if refund_cents > 0 and order.payment_id: self.payments.refund(order.payment_id, refund_cents, key=f"cancel-{order.id}")` `shop/orders.py:33-34`
* final status:
  `anything_shipped = any(l.shipped_qty > 0 for l in order.lines)` `shop/orders.py:36`
  `order.status = Status.PARTIALLY_CANCELLED if anything_shipped else Status.CANCELLED` `shop/orders.py:37`
* `order.history.append(f"cancelled by {actor}: {reason}")` `shop/orders.py:38`
* `self.repo.save(order)` `shop/orders.py:39`
* notification: `self.notifier.order_cancelled(order, refund_cents, actor)` `shop/orders.py:41`
* return `CancelResult(order.status, refund_cents)`

**Refund computation** `shop/refund_calc.py`

* tax helper: `return (amount_cents * rate_bp + 5000) // 10000` → round half up to cents `shop/refund_calc.py:4-6`
* `subtotal = sum(l.unit_price_cents * l.qty for l in order.lines)` `shop/refund_calc.py:18`
* `cancelled_items = sum(l.unit_price_cents * (l.qty - l.shipped_qty) for l in unshipped)` `shop/refund_calc.py:19`
* `if subtotal == 0: return 0` `shop/refund_calc.py:20-21`
* coupon share proportional: `coupon_share = order.coupon_cents * cancelled_items // subtotal` `shop/refund_calc.py:22`
* `net = cancelled_items - coupon_share` `shop/refund_calc.py:23`
* `refund = net + _tax(net, order.tax_rate_bp)` `shop/refund_calc.py:24`
* shipping refund only if nothing shipped at all: `if all(l.shipped_qty == 0 for l in order.lines): refund += order.shipping_cents` `shop/refund_calc.py:25-26`
* `return max(refund, 0)` `shop/refund_calc.py:27`

Items = unit_price_cents × units not yet shipped, summed over unshipped lines.
Coupon = fixed `order.coupon_cents` spread proportionally to `cancelled_items / subtotal` with integer floor division.
Tax = computed on `net` with basis-point rate and half-up rounding.
Shipping = refunded only when `all(l.shipped_qty == 0 for l in order.lines)`.

**Inventory change**

`Inventory.restock` increments `on_hand` by the qty passed in `shop/inventory.py:15-16`.
In the current flow the call is `restock(line.sku, line.qty, line.warehouse)` `shop/orders.py:29-30`, i.e. the full line quantity is added back for every line where `shipped_qty < qty`.

**Order end state**

* `Status.PARTIALLY_CANCELLED` if `any(l.shipped_qty > 0 for l in order.lines)` else `Status.CANCELLED` `shop/orders.py:36-37`.
With some items already shipped the order ends as `PARTIALLY_CANCELLED`.

**Notifications** `shop/notify.py:6-17` `Notifier.order_cancelled`

* pending pick list: `pending = [(l.sku, l.qty - l.shipped_qty) for l in order.lines if l.shipped_qty < l.qty]` `shop/notify.py:8`
* `if pending: self.warehouse_queue.publish("cancel_pick", {"order_id": order.id, "lines": pending})` `shop/notify.py:9-10`
* email template: `template = "cancel_by_staff" if actor == "staff" else "cancel_confirmation"` `shop/notify.py:12`
* `self.mailer.send(order.customer_id, template, {"order_id": order.id, "refund": f"{refund_cents / 100:.2f}", "partial": order.status.value == "partially_cancelled"})` `shop/notify.py:13-16`

**Bugs / risky behaviour**

* Restock quantity is wrong. The service passes `line.qty` `shop/orders.py:29-30` while the pending pick calculation correctly uses `l.qty - l.shipped_qty` `shop/notify.py:8`. For a partially shipped line the code restocks the full `qty`, over-stocking the warehouse; it should restock only `qty - shipped_qty`.
* Inventory reservation is never released. `Inventory.release_reservation` exists `shop/inventory.py:20-25` but is never called; unshipped reserved stock remains reserved after cancel.
* Two reads of the order: handler fetches with `repo.get` `shop/api.py:8` then service re-fetches with `repo.get_for_update` `shop/orders.py:22`. Race window between permission check and actual cancel.
* Coupon share uses integer floor division `order.coupon_cents * cancelled_items // subtotal` `shop/refund_calc.py:22`, truncating remainder and potentially under-refunding.
* Shipping refund condition `all(l.shipped_qty == 0 for l in order.lines)` `shop/refund_calc.py:25` is evaluated after the order may already be partially shipped; the logic is correct per spec but combined with the restock bug it can refund shipping while still restocking partially shipped lines.
* Conflict check for shipped uses `is` `shop/orders.py:25` rather than `==`; fragile for enum identity.
* No check that `unshipped` list is non-empty before restocking/refunding; restock will still run for lines where `shipped_qty < qty` but with the qty bug above it will add stock even when only one unit is unshipped.
* Refund is issued even if the order has no `payment_id`; the guard is `if refund_cents > 0 and order.payment_id` `shop/orders.py:33`, so a zero-payment order will still have inventory changes and status change.

These observations are derived solely from the shown files.


### Answer E

**HTTP handler → service flow**

* `cancel_order_handler`  
  * `order_id = request.path_params["id"]` shop/api.py:7  
  * `order = service.repo.get(order_id)` shop/api.py:8  
  * `if order is None: raise NotFound(order_id)` shop/api.py:9-10  
  * `if order.customer_id != request.user.id and not request.user.is_staff: raise Forbidden("not your order")` shop/api.py:11-12  
  * `reason = (request.json or {}).get("reason", "customer request")[:200]` shop/api.py:13  
  * `actor = "staff" if request.user.is_staff else "customer"` shop/api.py:14  
  * `result = service.cancel(order_id, reason=reason, actor=actor)` shop/api.py:15  

Allowed canceller: the order owner `order.customer_id == request.user.id` or a staff user `request.user.is_staff`. shop/api.py:11-12

`OrderService.cancel`

* `order: Order = self.repo.get_for_update(order_id)` shop/orders.py:22  
* Conflict checks  
  * `if order.status in (Status.DELIVERED, Status.CANCELLED, Status.PARTIALLY_CANCELLED): raise Conflict` shop/orders.py:23-24  
  * `if order.status is Status.SHIPPED: raise Conflict("order already shipped; use a return instead")` shop/orders.py:25-26  
  Status values defined: `PLACED`, `PARTIALLY_SHIPPED`, `SHIPPED`, `DELIVERED`, `CANCELLED`, `PARTIALLY_CANCELLED` shop/models.py:5-11

Hence cancel is possible only when status is not DELIVERED / CANCELLED / PARTIALLY_CANCELLED / SHIPPED, i.e. in practice `PLACED` or `PARTIALLY_SHIPPED`.

* `unshipped = [l for l in order.lines if l.shipped_qty < l.qty]` shop/orders.py:28  
* `for line in unshipped: self.inventory.restock(line.sku, line.qty, line.warehouse)` shop/orders.py:29-30  
  `Inventory.restock` does `UPDATE stock SET on_hand = on_hand + ? WHERE sku = ? AND warehouse = ?` shop/inventory.py:14-16 and returns early if `qty <= 0` shop/inventory.py:12-13

* `refund_cents = compute_refund(order, unshipped)` shop/orders.py:32  
* `if refund_cents > 0 and order.payment_id: self.payments.refund(order.payment_id, refund_cents, key=f"cancel-{order.id}")` shop/orders.py:33-34

* `anything_shipped = any(l.shipped_qty > 0 for l in order.lines)` shop/orders.py:36  
* `order.status = Status.PARTIALLY_CANCELLED if anything_shipped else Status.CANCELLED` shop/orders.py:37  
* `order.history.append(f"cancelled by {actor}: {reason}")` shop/orders.py:38  
* `self.repo.save(order)` shop/orders.py:39  
* `self.notifier.order_cancelled(order, refund_cents, actor)` shop/orders.py:41  
* returns `CancelResult(order.status, refund_cents)`

**Refund computation – `compute_refund`**

* `subtotal = sum(l.unit_price_cents * l.qty for l in order.lines)` shop/refund_calc.py:18  
* `cancelled_items = sum(l.unit_price_cents * (l.qty - l.shipped_qty) for l in unshipped)` shop/refund_calc.py:19  
* `if subtotal == 0: return 0` shop/refund_calc.py:20-21  
* `coupon_share = order.coupon_cents * cancelled_items // subtotal` shop/refund_calc.py:22  
* `net = cancelled_items - coupon_share` shop/refund_calc.py:23  
* `_tax(amount_cents, rate_bp) = (amount_cents * rate_bp + 5000) // 10000` – round half up shop/refund_calc.py:4-6  
* `refund = net + _tax(net, order.tax_rate_bp)` shop/refund_calc.py:24  
* Shipping: `if all(l.shipped_qty == 0 for l in order.lines): refund += order.shipping_cents` shop/refund_calc.py:25-26  
  comment: “Shipping: refunded only if nothing at all has shipped.” shop/refund_calc.py:15  
* `return max(refund, 0)` shop/refund_calc.py:27

Items = unit_price_cents × units not yet shipped `l.qty - l.shipped_qty` for unshipped lines.  
Coupon = fixed `order.coupon_cents` spread proportionally to item value, share = `order.coupon_cents * cancelled_items // subtotal`.  
Tax = charged on `items - coupon_share`, refunded on same basis with half-up rounding.  
Shipping refunded only when `all(l.shipped_qty == 0 for l in order.lines)`.

**Inventory change**

For each line with `l.shipped_qty < l.qty` the code calls `inventory.restock(line.sku, line.qty, line.warehouse)`. shop/orders.py:29-30  
`restock` adds `qty` to `on_hand` shop/inventory.py:14-16.  
`release_reservation` exists in `Inventory` shop/inventory.py:20-24 but is never invoked.

**Final order state**

* `Status.PARTIALLY_CANCELLED` if `anything_shipped` is true, else `Status.CANCELLED` shop/orders.py:37

**Notifications**

`Notifier.order_cancelled`

* `pending = [(l.sku, l.qty - l.shipped_qty) for l in order.lines if l.shipped_qty < l.qty]` shop/notify.py:8  
* if pending: `self.warehouse_queue.publish("cancel_pick", {"order_id": order.id, "lines": pending})` shop/notify.py:9-10  
* `template = "cancel_by_staff" if actor == "staff" else "cancel_confirmation"` shop/notify.py:12  
* `self.mailer.send(order.customer_id, template, {"order_id": order.id, "refund": f"{refund_cents / 100:.2f}", "partial": order.status.value == "partially_cancelled"})` shop/notify.py:13-16

**Bugs / risky behaviour visible in the shown code**

* Restock amount is wrong: unshipped lines are restocked with `line.qty` instead of the unshipped quantity `line.qty - line.shipped_qty`. shop/orders.py:30 vs correct unshipped amount used in refund `l.qty - l.shipped_qty` shop/refund_calc.py:19 and in notifier pending `l.qty - l.shipped_qty` shop/notify.py:8. This over-restock when a line is partially shipped.
* For a partially shipped line the code still restocks the full `line.qty`, so shipped units are added back to `on_hand`.
* No call to `inventory.release_reservation`; reserved stock is never released.
* Coupon share uses integer division `//` shop/refund_calc.py:22, truncating cents and potentially under-refunding the customer.
* Refund is computed after inventory has already been mutated; if `payments.refund` fails there is no rollback shown.
* Permission check is performed on a stale read `service.repo.get(order_id)` shop/api.py:8 before the `get_for_update` in `cancel`; a race window exists.
* `SHIPPED` status is rejected with “use a return instead” shop/orders.py:26, but a `PARTIALLY_SHIPPED` order with some lines still unshipped can be cancelled, leading to `PARTIALLY_CANCELLED` state while shipped items remain in the order.
* Shipping refund condition `all(l.shipped_qty == 0 for l in order.lines)` shop/refund_calc.py:25 means shipping is never refunded once any unit has shipped, even if the shipped portion is tiny.


---

# Task `he2_timeouts` (explore, hard set)

<details><summary>Full prompt given to the models (click to expand)</summary>

````text
We had an outage where a worker hung forever on a network call. Audit the source files below. (1) List every network operation that can block indefinitely with the default configuration (no environment variables set). For each, give file:line, the call, and why it is unbounded (trace where the timeout value comes from if it is passed in). (2) Then list the network calls that ARE bounded and where the bound comes from. Consider the library defaults of requests, httpx, urllib, socket and asyncio.

Citation rules: every factual claim must cite its source as file:line or file:start-end, using the line numbers shown (e.g. svc/config.py:8). Cite only lines that actually support the claim. Do not cite files or lines that are not shown, and do not describe code that is not shown.

### svc/config.py
```python
   1| import os
   2| from dataclasses import dataclass
   3| 
   4| 
   5| @dataclass
   6| class HttpSettings:
   7|     connect_timeout: float = 3.0
   8|     read_timeout: float | None = None   # None = wait as long as the server takes
   9|     retries: int = 2
  10| 
  11| 
  12| def load() -> HttpSettings:
  13|     s = HttpSettings()
  14|     if "SVC_READ_TIMEOUT" in os.environ:
  15|         s.read_timeout = float(os.environ["SVC_READ_TIMEOUT"])
  16|     return s
```

### svc/clients/github.py
```python
   1| import requests
   2| 
   3| API = "https://api.github.com"
   4| 
   5| 
   6| class GitHubClient:
   7|     def __init__(self, token: str, settings):
   8|         self.session = requests.Session()
   9|         self.session.headers["Authorization"] = f"Bearer {token}"
  10|         self.settings = settings
  11| 
  12|     def get_repo(self, name: str) -> dict:
  13|         r = self.session.get(f"{API}/repos/{name}", timeout=10)
  14|         r.raise_for_status()
  15|         return r.json()
  16| 
  17|     def list_issues(self, name: str) -> list:
  18|         r = self.session.get(f"{API}/repos/{name}/issues",
  19|                              timeout=(self.settings.connect_timeout, self.settings.read_timeout))
  20|         r.raise_for_status()
  21|         return r.json()
  22| 
  23|     def download_archive(self, name: str, dest) -> None:
  24|         with self.session.get(f"{API}/repos/{name}/tarball", stream=True) as r:
  25|             r.raise_for_status()
  26|             for chunk in r.iter_content(1 << 16):
  27|                 dest.write(chunk)
```

### svc/clients/billing.py
```python
   1| import json
   2| import urllib.request
   3| 
   4| import httpx
   5| 
   6| BILLING = "https://billing.internal"
   7| 
   8| 
   9| class BillingClient:
  10|     def __init__(self, timeout: float | None = None):
  11|         self.timeout = timeout
  12|         self.http = httpx.Client(base_url=BILLING)
  13| 
  14|     def invoice(self, invoice_id: str) -> dict:
  15|         return self.http.get(f"/invoices/{invoice_id}").json()
  16| 
  17|     def charge(self, payload: dict) -> dict:
  18|         return self.http.post("/charges", json=payload, timeout=None).json()
  19| 
  20|     def legacy_balance(self, account: str) -> dict:
  21|         req = urllib.request.Request(f"{BILLING}/v0/balance?account={account}")
  22|         with urllib.request.urlopen(req, timeout=self.timeout) as resp:
  23|             return json.load(resp)
  24| 
  25|     def health(self) -> bool:
  26|         with urllib.request.urlopen(f"{BILLING}/health", timeout=2) as resp:
  27|             return resp.status == 200
```

### svc/workers/fetch.py
```python
   1| import asyncio
   2| import socket
   3| 
   4| import requests
   5| 
   6| 
   7| def fetch_all(urls: list[str], **kwargs) -> list[bytes]:
   8|     out = []
   9|     for url in urls:
  10|         out.append(requests.get(url, **kwargs).content)
  11|     return out
  12| 
  13| 
  14| def ping_smtp(host: str) -> bool:
  15|     sock = socket.create_connection((host, 25))
  16|     try:
  17|         return sock.recv(3) == b"220"
  18|     finally:
  19|         sock.close()
  20| 
  21| 
  22| def ping_redis(host: str) -> bool:
  23|     sock = socket.create_connection((host, 6379), timeout=1.5)
  24|     try:
  25|         sock.sendall(b"PING\r\n")
  26|         return sock.recv(7) == b"+PONG\r\n"
  27|     finally:
  28|         sock.close()
  29| 
  30| 
  31| async def read_banner(host: str, port: int) -> bytes:
  32|     reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)
  33|     try:
  34|         return await reader.readline()
  35|     finally:
  36|         writer.close()
  37| 
  38| 
  39| async def post_metrics(host: str, payload: bytes) -> None:
  40|     reader, writer = await asyncio.open_connection(host, 8125)
  41|     writer.write(payload)
  42|     await writer.drain()
  43|     writer.close()
```

### svc/workers/sync.py
```python
   1| from ..clients.billing import BillingClient
   2| from ..clients.github import GitHubClient
   3| from ..config import load
   4| from .fetch import fetch_all
   5| 
   6| 
   7| def nightly(token: str, repos: list[str], mirrors: list[str]) -> None:
   8|     settings = load()
   9|     gh = GitHubClient(token, settings)
  10|     billing = BillingClient(timeout=settings.read_timeout)
  11|     for name in repos:
  12|         gh.get_repo(name)
  13|         gh.list_issues(name)
  14|     billing.legacy_balance("ops")
  15|     fetch_all(mirrors, timeout=(settings.connect_timeout, 30))
  16|     fetch_all(["https://status.internal/ping"])
```

````
</details>

### Reference notes

Ground truth for the default configuration (SVC_READ_TIMEOUT unset). Scoring: recall over U1-U8; each S-item claimed as unbounded is a false alarm; citations checked as correct / wrong (line exists but does not support the claim) / hallucinated (file or line not shown).

Unbounded (8):
- U1 svc/clients/github.py:18-19 list_issues: timeout=(connect_timeout, read_timeout); read_timeout defaults to None (svc/config.py:8, only set from env at 14-15) -> the READ can hang forever (connect is bounded by 3.0 s, config.py:7).
- U2 svc/clients/github.py:24 download_archive: session.get(..., stream=True) with no timeout; requests has no default timeout (the Session sets none, 8-9) -> connect and every read of iter_content (26) can hang.
- U3 svc/clients/billing.py:18 charge: timeout=None explicitly disables httpx's default 5 s timeout -> unbounded.
- U4 svc/clients/billing.py:22 legacy_balance: urlopen(timeout=self.timeout); self.timeout defaults to None (10-11) and nightly passes settings.read_timeout, which is None by default (svc/workers/sync.py:10, svc/config.py:8). Passing timeout=None explicitly makes the socket blocking (it does NOT fall back to the global default) -> unbounded.
- U5 svc/workers/fetch.py:15 (and recv at 17) ping_smtp: socket.create_connection without timeout -> connect and recv can block forever (unless a global socket default timeout is set elsewhere, which is not shown).
- U6 svc/workers/fetch.py:40-42 post_metrics: asyncio.open_connection without wait_for, and drain() unbounded.
- U7 svc/workers/fetch.py:10 via svc/workers/sync.py:16: fetch_all called with no timeout kwarg -> requests.get with no timeout.
- U8 svc/workers/fetch.py:34 read_banner: wait_for bounds only the connect (32); reader.readline() has no timeout -> can hang forever after connecting.

Bounded (claiming these as unbounded is a false alarm):
- S1 svc/clients/github.py:13 get_repo timeout=10.
- S2 svc/clients/billing.py:15 invoice: httpx.Client has a default 5 s timeout (client built at 12 without overriding it) -> bounded.
- S3 svc/clients/billing.py:26 health: timeout=2.
- S4 svc/workers/fetch.py:23-26 ping_redis: create_connection(timeout=1.5) sets the socket timeout, which also bounds sendall/recv.
- S5 svc/workers/fetch.py:32 the connect in read_banner (wait_for timeout=5) - but see U8 for the read.
- S6 svc/workers/sync.py:15 fetch_all(mirrors, timeout=(3.0, 30)) -> bounded (connect 3 s from settings, read 30 s).
Nuance worth credit: requests timeouts are per socket operation, not total wall time, so a slow-drip server can still exceed them; U1/U4 become bounded if SVC_READ_TIMEOUT is set (config.py:14-15).


### Answer A

**Default configuration**
* `HttpSettings.connect_timeout` default `3.0` svc/config.py:7
* `HttpSettings.read_timeout` default `None`  `# None = wait as long as the server takes` svc/config.py:8
* `load()` creates `s = HttpSettings()` svc/config.py:13 and only overrides `read_timeout` if `SVC_READ_TIMEOUT` is in `os.environ` svc/config.py:14-15. With no env vars `read_timeout` stays `None`.
* `BillingClient.__init__` `self.timeout = timeout` with `timeout: float | None = None` svc/clients/billing.py:10-11

### Network operations that can block indefinitely with the default config

* **svc/clients/github.py:18-19 `list_issues`**
  `r = self.session.get(f"{API}/repos/{name}/issues", timeout=(self.settings.connect_timeout, self.settings.read_timeout))` svc/clients/github.py:18-19
  Timeout comes from `self.settings`. `connect_timeout` = 3.0 from `HttpSettings` default svc/config.py:7. `read_timeout` = `None` from `HttpSettings` default svc/config.py:8, unchanged by `load()` svc/config.py:13-16. `requests` tuple `(connect, read)` with read=`None` → read side is unbounded.

* **svc/clients/github.py:24 `download_archive`**
  `with self.session.get(f"{API}/repos/{name}/tarball", stream=True) as r:` svc/clients/github.py:24
  No `timeout` argument is passed. `requests.Session.get` therefore uses the requests library default = no timeout → connect and read can block forever.

* **svc/clients/billing.py:18 `charge`**
  `return self.http.post("/charges", json=payload, timeout=None).json()` svc/clients/billing.py:18
  `timeout=None` is passed explicitly, overriding the `httpx.Client` default created at svc/clients/billing.py:12. `httpx` with `timeout=None` is unbounded.

* **svc/clients/billing.py:22 `legacy_balance`**
  `with urllib.request.urlopen(req, timeout=self.timeout) as resp:` svc/clients/billing.py:22
  `self.timeout` is set from `BillingClient(timeout=settings.read_timeout)` svc/workers/sync.py:10. `settings.read_timeout` is `None` by default svc/config.py:8. `urllib.request.urlopen` with `timeout=None` → no socket timeout, can block indefinitely.

* **svc/workers/fetch.py:15 `ping_smtp`**
  `sock = socket.create_connection((host, 25))` svc/workers/fetch.py:15
  No timeout argument → `socket.create_connection` uses the library default `None`. The subsequent `sock.recv(3)` svc/workers/fetch.py:17 is on a socket with no timeout.

* **svc/workers/fetch.py:10 + svc/workers/sync.py:16 `fetch_all` without timeout**
  `out.append(requests.get(url, **kwargs).content)` svc/workers/fetch.py:10
  Called as `fetch_all(["https://status.internal/ping"])` svc/workers/sync.py:16 with no `timeout` kwargs. `requests.get` receives no timeout → unbounded.

* **svc/workers/fetch.py:34 `read_banner` read**
  `return await reader.readline()` svc/workers/fetch.py:34
  Connection is bounded by `await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)` svc/workers/fetch.py:32, but `reader.readline()` is awaited with no timeout → can block forever if the peer never sends a newline.

* **svc/workers/fetch.py:40 `post_metrics`**
  `reader, writer = await asyncio.open_connection(host, 8125)` svc/workers/fetch.py:40
  `asyncio.open_connection` is called with no timeout argument → the TCP connect can block indefinitely.

### Network calls that are bounded and where the bound comes from

* **svc/clients/github.py:13 `get_repo`**
  `r = self.session.get(f"{API}/repos/{name}", timeout=10)` svc/clients/github.py:13
  Explicit `timeout=10` → both connect and read bounded to 10 s.

* **svc/clients/billing.py:26 `health`**
  `with urllib.request.urlopen(f"{BILLING}/health", timeout=2) as resp:` svc/clients/billing.py:26
  Explicit `timeout=2` → urllib socket timeout 2 s.

* **svc/workers/fetch.py:23 `ping_redis` connect**
  `sock = socket.create_connection((host, 6379), timeout=1.5)` svc/workers/fetch.py:23
  Explicit `timeout=1.5` → connect bounded to 1.5 s; the socket is created with that timeout.

* **svc/workers/fetch.py:32 `read_banner` connect**
  `reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)` svc/workers/fetch.py:32
  `asyncio.wait_for` with `timeout=5` bounds the `open_connection` handshake to 5 s.

* **svc/workers/sync.py:15 `fetch_all` with timeout**
  `fetch_all(mirrors, timeout=(settings.connect_timeout, 30))` svc/workers/sync.py:15
  `requests.get` in `fetch_all` receives `timeout=(settings.connect_timeout, 30)`. `settings.connect_timeout` = 3.0 from default svc/config.py:7, read timeout literal 30 → connect ≤3 s, read ≤30 s.

* **svc/clients/billing.py:15 `invoice`**
  `return self.http.get(f"/invoices/{invoice_id}").json()` svc/clients/billing.py:15
  `self.http = httpx.Client(base_url=BILLING)` svc/clients/billing.py:12 with no per-request timeout. Bounded by httpx `Client` library default timeout.

* **svc/workers/sync.py:15 connect part of `list_issues`**
  The same `timeout=(self.settings.connect_timeout, self.settings.read_timeout)` used in svc/clients/github.py:18-19 gives a bounded connect of `settings.connect_timeout` = 3.0 svc/config.py:7, even though the read side is unbounded as above.


### Answer B

**Default configuration – no environment variables**

`svc/config.py:7` `connect_timeout: float = 3.0`
`svc/config.py:8` `read_timeout: float | None = None   # None = wait as long as the server takes`
`svc/config.py:12-15` `load()` returns an `HttpSettings()` with the defaults above; `SVC_READ_TIMEOUT` is not set so `read_timeout` stays `None`.

### Network operations that can block indefinitely

* `svc/clients/github.py:19`
  `self.session.get(f"{API}/repos/{name}/issues", timeout=(self.settings.connect_timeout, self.settings.read_timeout))`
  `list_issues`. Timeout tuple comes from `settings`. `self.settings.connect_timeout` is `3.0` from `svc/config.py:7`. `self.settings.read_timeout` is `None` from `svc/config.py:8`. In `requests` a `None` read element means no read timeout → unbounded read, connect is bounded 3 s.

* `svc/clients/github.py:24`
  `with self.session.get(f"{API}/repos/{name}/tarball", stream=True) as r:`
  `download_archive`. No `timeout` argument is passed. `requests.Session.get` with no timeout uses the requests library default of no timeout → unbounded.

* `svc/clients/billing.py:18`
  `return self.http.post("/charges", json=payload, timeout=None).json()`
  `charge`. `timeout=None` is passed explicitly → httpx disables timeout for this request → unbounded.

* `svc/clients/billing.py:22`
  `with urllib.request.urlopen(req, timeout=self.timeout) as resp:`
  `legacy_balance`. `BillingClient.__init__` `self.timeout = timeout` `svc/clients/billing.py:10-11` with default `None`. Usage `svc/workers/sync.py:10` `billing = BillingClient(timeout=settings.read_timeout)` and `settings = load()` `svc/workers/sync.py:8`. With no env var `settings.read_timeout` is `None` `svc/config.py:8`. `urllib.request.urlopen` with `timeout=None` blocks indefinitely → unbounded.

* `svc/workers/fetch.py:10`
  `out.append(requests.get(url, **kwargs).content)`
  `fetch_all` internal call. Call site `svc/workers/sync.py:16` `fetch_all(["https://status.internal/ping"])` passes no `timeout` kwargs. `requests.get` with no timeout uses the requests library default of no timeout → unbounded.

* `svc/workers/fetch.py:15`
  `sock = socket.create_connection((host, 25))`
  `ping_smtp`. `socket.create_connection` is called without a `timeout` argument. Library default is `socket.getdefaulttimeout()` which is `None` → connection can block indefinitely.

* `svc/workers/fetch.py:34`
  `return await reader.readline()`
  `read_banner`. Connection is created with `await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)` `svc/workers/fetch.py:32`, so connect is bounded 5 s, but the subsequent `reader.readline()` `svc/workers/fetch.py:34` has no timeout → unbounded read.

* `svc/workers/fetch.py:40`
  `reader, writer = await asyncio.open_connection(host, 8125)`
  `post_metrics`. `asyncio.open_connection` is called with no timeout. The connection attempt can block indefinitely; `writer.drain()` is also unbounded.

### Network operations that are bounded with the default configuration

* `svc/clients/github.py:13`
  `r = self.session.get(f"{API}/repos/{name}", timeout=10)`
  `get_repo`. Explicit `timeout=10` → bounded 10 s.

* `svc/clients/github.py:19` connect part
  Same call as above, connect element of the tuple is `self.settings.connect_timeout` = `3.0` `svc/config.py:7`. Read is unbounded as noted.

* `svc/clients/billing.py:26`
  `with urllib.request.urlopen(f"{BILLING}/health", timeout=2) as resp:`
  `health`. Explicit `timeout=2` → bounded 2 s.

* `svc/clients/billing.py:15`
  `return self.http.get(f"/invoices/{invoice_id}").json()`
  `invoice`. `self.http = httpx.Client(base_url=BILLING)` `svc/clients/billing.py:12` with no per-request timeout, so the request uses the httpx `Client` default timeout. Library default timeout is finite → bounded by httpx defaults.

* `svc/workers/fetch.py:23`
  `sock = socket.create_connection((host, 6379), timeout=1.5)`
  `ping_redis`. Explicit `timeout=1.5` → bounded 1.5 s.

* `svc/workers/fetch.py:32`
  `reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)`
  `read_banner` connection. `asyncio.wait_for(..., timeout=5)` bounds the connection establishment to 5 s.

* `svc/workers/sync.py:15`
  `fetch_all(mirrors, timeout=(settings.connect_timeout, 30))`
  `fetch_all` with explicit kwargs. Connect timeout comes from `settings.connect_timeout` = `3.0` `svc/config.py:7`; read timeout is `30` explicit. Both bounds are finite → bounded.

* `svc/workers/sync.py:12`
  `gh.get_repo(name)` → resolves to `svc/clients/github.py:13` `timeout=10` bounded.

The unbounded cases above are the ones that can hang forever with the default, env-var-free configuration.


### Answer C

**Default configuration used for the audit**
`HttpSettings.read_timeout` defaults to `None` `svc/config.py:8` and `connect_timeout` defaults to `3.0` `svc/config.py:7`.
`load()` only overrides `read_timeout` when `SVC_READ_TIMEOUT` is in the environment `svc/config.py:14-15`. No environment variables are set, so `read_timeout` stays `None`.

### 1. Network operations that can block indefinitely with the defaults

* `svc/clients/github.py:19` – `self.session.get(..., timeout=(self.settings.connect_timeout, self.settings.read_timeout))`
  * Called from `GitHubClient.list_issues` `svc/clients/github.py:18-19`.
  * Timeout tuple is built from settings: `connect_timeout = 3.0` `svc/config.py:7`, `read_timeout = None` `svc/config.py:8`.
  * `requests` timeout tuple = `(connect, read)`. Connect is bounded 3 s, read is `None` → read can wait forever.

* `svc/clients/github.py:24` – `self.session.get(f"{API}/repos/{name}/tarball", stream=True)`
  * `GitHubClient.download_archive` `svc/clients/github.py:23-27`.
  * No `timeout` argument is passed. `requests.Session.get` default timeout is `None` → connect and read are unbounded. `r.iter_content` `svc/clients/github.py:26` can then block forever.

* `svc/clients/billing.py:18` – `self.http.post("/charges", json=payload, timeout=None)`
  * `BillingClient.charge` `svc/clients/billing.py:17-18`.
  * Explicit `timeout=None` overrides the httpx client default → unbounded.

* `svc/clients/billing.py:22` – `urllib.request.urlopen(req, timeout=self.timeout)`
  * `BillingClient.legacy_balance` `svc/clients/billing.py:20-23`.
  * `self.timeout` is initialised as `timeout: float | None = None` `svc/clients/billing.py:10-11`.
  * In the nightly job `billing = BillingClient(timeout=settings.read_timeout)` `svc/workers/sync.py:10`. With defaults `settings.read_timeout` is `None` `svc/config.py:8`.
  * `urllib.request.urlopen` with `timeout=None` blocks indefinitely.

* `svc/workers/fetch.py:15` – `socket.create_connection((host, 25))`
  * `ping_smtp` `svc/workers/fetch.py:14-19`.
  * No timeout argument → `socket.create_connection` uses `socket.getdefaulttimeout()` which is `None` by default → connection and subsequent `sock.recv(3)` `svc/workers/fetch.py:17` can block forever.

* `svc/workers/fetch.py:10` used via `svc/workers/sync.py:16`
  * `fetch_all` does `requests.get(url, **kwargs).content` `svc/workers/fetch.py:10`.
  * Nightly call `fetch_all(["https://status.internal/ping"])` `svc/workers/sync.py:16` passes no `timeout` kwargs.
  * `requests.get` with no timeout → default `None` → unbounded.

* `svc/workers/fetch.py:34` – `await reader.readline()`
  * `read_banner` `svc/workers/fetch.py:31-36`.
  * Connection is bounded by `asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)` `svc/workers/fetch.py:32`.
  * The subsequent read `await reader.readline()` `svc/workers/fetch.py:34` has no timeout → can block forever if the peer never sends a line.

* `svc/workers/fetch.py:40` – `await asyncio.open_connection(host, 8125)`
  * `post_metrics` `svc/workers/fetch.py:39-43`.
  * No `asyncio.wait_for`/timeout is applied to the `open_connection` call → connection attempt is unbounded. `writer.drain()` `svc/workers/fetch.py:42` is also unbounded.

### 2. Network calls that are bounded and where the bound comes from

* `svc/clients/github.py:13` – `self.session.get(f"{API}/repos/{name}", timeout=10)`
  * `GitHubClient.get_repo` `svc/clients/github.py:12-15`.
  * Explicit `timeout=10` → requests connect + read bounded to 10 s.

* `svc/clients/github.py:19` connect component
  * Same call as above, `timeout=(self.settings.connect_timeout, self.settings.read_timeout)`.
  * Connect part is bounded by `self.settings.connect_timeout` = `3.0` `svc/config.py:7`. Read part is unbounded as noted.

* `svc/workers/fetch.py:23` – `socket.create_connection((host, 6379), timeout=1.5)`
  * `ping_redis` `svc/workers/fetch.py:22-28`.
  * Explicit `timeout=1.5` → connection bounded to 1.5 s.

* `svc/clients/billing.py:26` – `urllib.request.urlopen(f"{BILLING}/health", timeout=2)`
  * `BillingClient.health` `svc/clients/billing.py:25-27`.
  * Explicit `timeout=2` → bounded to 2 s.

* `svc/workers/fetch.py:32` – `asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)`
  * `read_banner` connection phase `svc/workers/fetch.py:32`.
  * Connection attempt bounded to 5 s by `asyncio.wait_for`.

* `svc/workers/sync.py:15` – `fetch_all(mirrors, timeout=(settings.connect_timeout, 30))`
  * `fetch_all` `svc/workers/fetch.py:7-11` receives `**kwargs`.
  * Timeout tuple supplied in the call: connect = `settings.connect_timeout` = `3.0` `svc/config.py:7`, read = `30` literal.
  * Requests connect bounded 3 s, read bounded 30 s.

* `svc/clients/billing.py:15` – `self.http.get(f"/invoices/{invoice_id}")`
  * `BillingClient.invoice` `svc/clients/billing.py:14-15`.
  * No per-request timeout, but `self.http = httpx.Client(base_url=BILLING)` `svc/clients/billing.py:12` uses httpx library default timeout ≈ 5 s for connect/read/write/pool. Bounded by httpx client default.

The unbounded operations above are the ones that can hang forever under the default, no-environment-variable configuration.


### Answer D

**Default configuration = no `SVC_READ_TIMEOUT` in the environment**

`HttpSettings` defaults

* `connect_timeout: float = 3.0`  svc/config.py:7
* `read_timeout: float | None = None   # None = wait as long as the server takes` svc/config.py:8

`load()` only overrides `read_timeout` when the env var is present:

```
if "SVC_READ_TIMEOUT" in os.environ:          svc/config.py:14
    s.read_timeout = float(os.environ["SVC_READ_TIMEOUT"])   svc/config.py:15
```
With no env var `settings.read_timeout` stays `None`.

### Network operations that can block indefinitely

* **svc/clients/github.py:18-19**  
  `self.session.get(f"{API}/repos/{name}/issues", timeout=(self.settings.connect_timeout, self.settings.read_timeout))`  
  Timeout is `(settings.connect_timeout, settings.read_timeout)`.  
  `connect_timeout` comes from `HttpSettings.connect_timeout = 3.0` svc/config.py:7, so connect is bounded to 3 s.  
  `read_timeout` comes from `HttpSettings.read_timeout = None` svc/config.py:8 and is not overridden by `load()` svc/config.py:14-15.  
  In `requests` a `None` read timeout means wait forever → unbounded read.

* **svc/clients/github.py:24**  
  `with self.session.get(f"{API}/repos/{name}/tarball", stream=True) as r:`  
  No `timeout` argument is passed. `requests.Session.get` defaults to timeout `None` → unbounded connect and read.

* **svc/clients/billing.py:18**  
  `return self.http.post("/charges", json=payload, timeout=None).json()`  
  Explicit `timeout=None` overrides the `httpx.Client` default. With `timeout=None` httpx will wait indefinitely.

* **svc/clients/billing.py:22**  
  `with urllib.request.urlopen(req, timeout=self.timeout) as resp:`  
  `self.timeout` is set in `__init__`:
  `def __init__(self, timeout: float | None = None):` svc/clients/billing.py:10
  `self.timeout = timeout` svc/clients/billing.py:11
  In `svc/workers/sync.py`:
  `billing = BillingClient(timeout=settings.read_timeout)` svc/workers/sync.py:10
  `settings.read_timeout` is `None` per `HttpSettings.read_timeout = None` svc/config.py:8.  
  `urllib.request.urlopen(..., timeout=None)` → library default is no timeout → unbounded.

* **svc/workers/fetch.py:10** used via `svc/workers/sync.py:16`  
  `out.append(requests.get(url, **kwargs).content)` svc/workers/fetch.py:10  
  Call site:
  `fetch_all(["https://status.internal/ping"])` svc/workers/sync.py:16  
  No `timeout` kwarg is supplied, `**kwargs` is empty, so `requests.get` is invoked with no timeout → `requests` default `None` → unbounded.

* **svc/workers/fetch.py:15**  
  `sock = socket.create_connection((host, 25))`  
  No timeout argument. `socket.create_connection(host,port,timeout=None)` uses `socket.getdefaulttimeout()` which is `None` by default → connect can block forever. Subsequent `sock.recv(3)` svc/workers/fetch.py:17 is on a socket with no timeout.

* **svc/workers/fetch.py:34**  
  `return await reader.readline()`  
  Connection is established with:
  `reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)` svc/workers/fetch.py:32  
  The 5 s `wait_for` bounds only the TCP connect. `StreamReader.readline()` has no timeout → unbounded read.

* **svc/workers/fetch.py:40**  
  `reader, writer = await asyncio.open_connection(host, 8125)`  
  No `asyncio.wait_for` / timeout is applied. `asyncio.open_connection` can block indefinitely establishing the TCP connection.

### Network operations that are bounded with the default config

* **svc/clients/github.py:13**  
  `r = self.session.get(f"{API}/repos/{name}", timeout=10)`  
  Explicit `timeout=10` → connect + read bounded to 10 s.

* **svc/clients/billing.py:26**  
  `with urllib.request.urlopen(f"{BILLING}/health", timeout=2) as resp:`  
  Explicit `timeout=2` → bounded to 2 s.

* **svc/workers/fetch.py:23**  
  `sock = socket.create_connection((host, 6379), timeout=1.5)`  
  Explicit `timeout=1.5` → connect bounded to 1.5 s.

* **svc/workers/fetch.py:32**  
  `reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)`  
  Connect phase bounded by `asyncio.wait_for(..., timeout=5)` → 5 s bound for TCP connect.

* **svc/workers/sync.py:15** → `svc/workers/fetch.py:10`  
  `fetch_all(mirrors, timeout=(settings.connect_timeout, 30))` svc/workers/sync.py:15  
  `requests.get(url, **kwargs)` receives `timeout=(settings.connect_timeout,30)`.  
  Connect timeout comes from `HttpSettings.connect_timeout = 3.0` svc/config.py:7 → 3 s.  
  Read timeout is explicit 30 s → bounded.

* **svc/clients/github.py:18-19** connect part  
  Same call as above, `timeout=(self.settings.connect_timeout, self.settings.read_timeout)`.  
  Connect timeout = `HttpSettings.connect_timeout = 3.0` svc/config.py:7 → connect bounded to 3 s; read is unbounded as noted.

* **svc/clients/billing.py:15**  
  `return self.http.get(f"/invoices/{invoice_id}").json()`  
  Client created as:
  `self.http = httpx.Client(base_url=BILLING)` svc/clients/billing.py:12  
  No per-request timeout is supplied, so the request uses the `httpx.Client` library default timeout. The library default is a finite connect/read/write/pool timeout → bounded by httpx defaults.

These are the operations whose timeout source is traceable in the shown files and whose unbounded/bounded nature follows from the defaults of `requests`, `httpx`, `urllib.request`, `socket` and `asyncio`.


### Answer E

**Default configuration**

* `HttpSettings.read_timeout` default is `None` → “wait as long as the server takes” `svc/config.py:8`
* `HttpSettings.connect_timeout` default is `3.0` `svc/config.py:7`
* `load()` only overrides `read_timeout` when `SVC_READ_TIMEOUT` is in the environment `svc/config.py:14-15`
With no environment variables set `settings.read_timeout` stays `None` and `settings.connect_timeout` stays `3.0`.

### 1. Network operations that can block indefinitely with the default config

* **GitHubClient.list_issues – read side unbounded**
  `self.session.get(f"{API}/repos/{name}/issues", timeout=(self.settings.connect_timeout, self.settings.read_timeout))` `svc/clients/github.py:18-19`
  Timeout is built from `settings.connect_timeout` = 3.0 `svc/config.py:7` and `settings.read_timeout` = `None` `svc/config.py:8`. With `read_timeout=None` requests will wait indefinitely for data. Used in `nightly` as `gh.list_issues(name)` `svc/workers/sync.py:13`.

* **GitHubClient.download_archive – no timeout at all**
  `with self.session.get(f"{API}/repos/{name}/tarball", stream=True) as r:` `svc/clients/github.py:24`
  No `timeout` argument is passed. `requests` default is no timeout → unbounded connect/read.

* **BillingClient.charge – explicit `timeout=None`**
  `return self.http.post("/charges", json=payload, timeout=None).json()` `svc/clients/billing.py:18`
  Explicit `timeout=None` overrides the `httpx.Client` default → unbounded.

* **BillingClient.legacy_balance – urllib with `timeout=None`**
  `with urllib.request.urlopen(req, timeout=self.timeout) as resp:` `svc/clients/billing.py:22`
  `self.timeout` is the `BillingClient` init argument `self.timeout = timeout` `svc/clients/billing.py:10-11` default `None`.
  In `nightly`:
  `billing = BillingClient(timeout=settings.read_timeout)` `svc/workers/sync.py:10`
  `settings.read_timeout` is `None` by default `svc/config.py:8`. `urllib.request.urlopen` with `timeout=None` blocks indefinitely.

* **fetch_all without timeout – requests default**
  `out.append(requests.get(url, **kwargs).content)` `svc/workers/fetch.py:10`
  Called in `nightly` as `fetch_all(["https://status.internal/ping"])` `svc/workers/sync.py:16` with no `kwargs`. `requests.get` with no `timeout` argument uses the library default `None` → unbounded.

* **ping_smtp – socket.create_connection with no timeout**
  `sock = socket.create_connection((host, 25))` `svc/workers/fetch.py:15`
  No timeout argument → `socket.create_connection` uses the library default socket timeout which is `None` → connect can block forever.

* **read_banner – unbounded read after bounded connect**
  Connect is bounded:
  `reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)` `svc/workers/fetch.py:32`
  Read is unbounded:
  `return await reader.readline()` `svc/workers/fetch.py:34`
  `asyncio.StreamReader.readline()` has no timeout, so the coroutine can hang forever waiting for a line.

* **post_metrics – asyncio open_connection with no timeout**
  `reader, writer = await asyncio.open_connection(host, 8125)` `svc/workers/fetch.py:40`
  `asyncio.open_connection` has no timeout argument → connect can block indefinitely. Subsequent `writer.drain()` is also unbounded.

### 2. Network calls that are bounded and where the bound comes from

* **GitHubClient.get_repo – explicit 10 s**
  `r = self.session.get(f"{API}/repos/{name}", timeout=10)` `svc/clients/github.py:13`
  Bound = 10 s literal.

* **GitHubClient.list_issues – connect bounded**
  Same call as above `svc/clients/github.py:18-19`. Connect part is `self.settings.connect_timeout` = 3.0 `svc/config.py:7`. Read part is unbounded as shown above.

* **fetch_all with explicit timeout**
  `fetch_all(mirrors, timeout=(settings.connect_timeout, 30))` `svc/workers/sync.py:15`
  Passed to `requests.get(url, **kwargs)` `svc/workers/fetch.py:10`. Connect = `settings.connect_timeout` = 3.0 `svc/config.py:7`, read = 30 s literal.

* **BillingClient.health – urllib with 2 s**
  `with urllib.request.urlopen(f"{BILLING}/health", timeout=2) as resp:` `svc/clients/billing.py:26`
  Bound = 2 s literal.

* **ping_redis – socket.create_connection with timeout**
  `sock = socket.create_connection((host, 6379), timeout=1.5)` `svc/workers/fetch.py:23`
  Bound = 1.5 s for connect.

* **read_banner connect – asyncio.wait_for**
  `await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)` `svc/workers/fetch.py:32`
  Bound = 5 s for the TCP connect.

* **BillingClient.invoice – httpx.Client library default**
  `self.http = httpx.Client(base_url=BILLING)` `svc/clients/billing.py:12`
  `return self.http.get(f"/invoices/{invoice_id}").json()` `svc/clients/billing.py:15`
  No per-request timeout is supplied, so the bound is the `httpx.Client` library default timeout ≈ 5 s.

These are the only bounded operations under the default, no-env configuration; all others listed in section 1 can hang forever.

