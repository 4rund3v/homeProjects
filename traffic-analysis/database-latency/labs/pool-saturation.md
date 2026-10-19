# Lab: drive the pool to saturation, read the signature

## Prereqs

- App + DB up.
- `pg_stat_activity_numbackends` panel open.
- The app's `pool_in_use` / `pool_idle` gauges visible (the reference app exports them).

## Step 1 — baseline

50 VU. Record for 60 s:
- `pg_stat_activity_numbackends`.
- `pool_in_use` (max across pods).
- `pool_idle`.
- App p95, p99.
- `pg_stat_statements_mean_exec_time` for the two hot queries.

## Step 2 — raise load to 400 VU

Watch the pool:
- `pool_in_use` climbs toward 25.
- `pool_idle` drops to 0.
- `pg_stat_activity_numbackends` climbs toward 25 (the app's pool size).
- App p50 stays near 14 ms.
- App p99 climbs a cliff — that is the queue.

## Step 3 — read the gap

```
# The gap is the queue time
app_p99 - pg_stat_statements_mean_exec_time
```

If the gap is 500 ms, the request waited 500 ms in the pool before it could get a connection. The DB itself is fine. The *pool* is the bottleneck.

## Step 4 — shrink the pool

Set `poolMaxConns: 4`. Re-load at 200 VU.

Watch:
- `pool_in_use` pinned at 4.
- App p99 *higher* than the 25-pool case at the same load.
- `pg_stat_activity_numbackends` pinned at 4.
- New errors in app logs: `pool acquire timeout`.

**Question:** why does a *smaller* pool have a *worse* p99 at the same load? (Fewer conns in flight → each conn is held longer → the queue grows faster. The pool size sets the *throughput ceiling*, not the latency floor.)

## Step 5 — the DB-side view

`pg_stat_activity` should show 4 active sessions, not 25. The DB *thinks* it is lightly loaded. The app is the one queuing.

**Question:** if you only looked at the DB, you would conclude "the DB is fine." What metric on the *app* side tells the truth? (`pool_in_use` pinned, `pool_idle` = 0, p99 cliff.)

## Restore

```
kubectl -n shop set deploy/shop-api env POOL_MAX_CONNS=25
kubectl -n shop rollout status deploy/shop-api
```

Re-run the baseline. Pool returns to 2–3 in use, idle returns to 22–23.
