import random
from datetime import datetime, timedelta
random.seed(7)
t = datetime(2026, 9, 14, 13, 59, 0)
lines = []
active, idle, POOL = 3, 17, 20
leaked = 0
gc_fail = 0
def emit(dt, lvl, svc, msg):
    lines.append(f"{dt.strftime('%Y-%m-%dT%H:%M:%S.')}{dt.microsecond//1000:03d}Z {lvl:<5} [{svc}] {msg}")
deploy_at = datetime(2026, 9, 14, 14, 1, 10)
restart_at = datetime(2026, 9, 14, 14, 9, 40)
reqn = 1000
last_stats = t
emit(t, "INFO", "checkout-svc", "starting checkout-svc version=2.13.4 pid=41 pool.max=20 pool.acquire_timeout_ms=5000")
emit(t, "WARN", "metrics-exporter", "TLS certificate for metrics.internal expires in 29 days (2026-10-13)")
deployed = False
restarted = False
while len(lines) < 297:
    t += timedelta(milliseconds=random.randint(1500, 4200))
    if not deployed and t >= deploy_at:
        deployed = True
        emit(t, "INFO", "deployer", "rollout checkout-svc 2.13.4 -> 2.14.0 complete (changes: gift card balance check at checkout, new payment retry config, log format tweaks)")
        emit(t, "INFO", "checkout-svc", "starting checkout-svc version=2.14.0 pid=57 pool.max=20 pool.acquire_timeout_ms=5000")
        active, idle, leaked = 2, 18, 0
        continue
    if not restarted and t >= restart_at:
        restarted = True
        emit(t, "WARN", "kubelet", "liveness probe failed for checkout-svc-7c9d (GET /healthz timeout 3s) x3, restarting container")
        emit(t, "INFO", "checkout-svc", "starting checkout-svc version=2.14.0 pid=12 pool.max=20 pool.acquire_timeout_ms=5000")
        active, idle, leaked = 2, 18, 0
        continue
    if (t - last_stats).total_seconds() >= 30:
        last_stats = t
        busy = min(POOL, leaked + random.randint(1, 3))
        emit(t, "INFO", "sqlpool", f"pool stats active={busy} idle={POOL-busy} waiting={max(0, leaked + random.randint(0,4) - 17) if leaked > 15 else 0} max={POOL}")
        continue
    r = random.random()
    reqn += 1
    rid = f"r{reqn:05d}"
    if leaked >= 19 and r < 0.55:
        path = random.choice(["/checkout", "/checkout", "/orders", "/cart"])
        emit(t, "ERROR", "checkout-svc", f"req={rid} path={path} error=\"sqlpool: timeout acquiring connection after 5000ms (active=20 idle=0)\" status=503 dur={5000+random.randint(1,40)}ms")
        continue
    if deployed and r < 0.22:
        # gift card path
        card = f"****{random.randint(1000, 9999)}"
        if random.random() < 0.6:
            emit(t, "WARN", "giftcard-client", f"req={rid} balance lookup card={card} -> 404 card_not_found (dur={random.randint(40,90)}ms)")
            emit(t, "INFO", "checkout-svc", f"req={rid} path=/checkout giftcard=rejected status=402 dur={random.randint(60,140)}ms")
            leaked += 1
        else:
            emit(t, "INFO", "checkout-svc", f"req={rid} path=/checkout giftcard=applied status=200 dur={random.randint(120,380) + (leaked*40 if leaked>12 else 0)}ms")
        continue
    if 0.22 <= r < 0.25:
        emit(t, "WARN", "runtime", f"gc pause {random.randint(80,160)}ms (heap 71%)")
        continue
    if 0.25 <= r < 0.265:
        emit(t, "WARN", "redis", f"slow command GET session:* {random.randint(30,70)}ms")
        continue
    if 0.265 <= r < 0.275:
        emit(t, "WARN", "node", f"disk usage /var/log 8{random.randint(1,3)}%")
        continue
    if deployed and leaked >= 8 and 0.275 <= r < 0.31:
        emit(t, "WARN", "sqlpool", f"connection pg-{random.randint(1,20)} held for {random.randint(61, max(62, int((t - (restart_at if restarted else deploy_at)).total_seconds())))}s by giftcard.balance_lookup (leak detection threshold 60s)")
        continue
    path = random.choice(["/checkout", "/cart", "/cart", "/orders", "/products", "/products", "/products"])
    base = random.randint(20, 160) if path != "/checkout" else random.randint(120, 350)
    if leaked > 14:
        base += random.randint(200, 2500)
    emit(t, "INFO", "checkout-svc", f"req={rid} path={path} status=200 dur={base}ms")
emit(t + timedelta(seconds=2), "ERROR", "gateway", "upstream checkout-svc: 5xx rate 38% over 1m (threshold 5%) -> paging on-call")
emit(t + timedelta(seconds=3), "WARN", "payments", "retry config: max_attempts=4 backoff=exp (new in 2.14.0) - payment-provider latency p99 410ms (normal)")
emit(t + timedelta(seconds=5), "INFO", "dns", "resolver cache refreshed (2 upstreams healthy)")
open(__file__.replace("gen.py", "service.log"), "w").write("\n".join(lines) + "\n")
print(len(lines))
