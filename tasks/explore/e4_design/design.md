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
