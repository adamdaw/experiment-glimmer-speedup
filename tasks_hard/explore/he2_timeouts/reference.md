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
