# 02 — Connection pool saturation

The app's pool is the single most important saturation point in the stack. When the pool is full, new requests *queue in the app*, and the queue time shows up in the app's p99 — not in the DB.

## The numbers

| Setting | Default in this project | What it means |
|---|---|---|
| `poolMaxConns` | 25 | Max simultaneous connections the app can hold. |
| `poolMaxIdle` | 25 | Max idle conns kept warm. |
| `poolTimeout` | 30 s | How long a request waits for a free conn before erroring. |
| `pg_max_connections` | 100 | DB-side limit. The app's pool must be < this, with headroom for admin + replication. |

## What to watch

- `pg_stat_activity_numbackends` — the DB-side count. When it hits `pg_max_connections`, *new connections are rejected*, and the app's pool cannot open new ones.
- The app's own `pool_in_use` / `pool_idle` gauges (if the Go app exports them — the reference app in `project/examples/` does). When `pool_in_use` is pinned at `poolMaxConns` and `pool_idle` is 0, the pool is saturated.
- App p99 vs DB `mean_exec_time` — the gap *is* the queue.

## The saturation signature

```
Idle:        pool_in_use=2,  pool_idle=23, p50=8ms,  p99=12ms
Light load:  pool_in_use=15, pool_idle=10, p50=9ms,  p99=15ms
Saturation:  pool_in_use=25, pool_idle=0,  p50=14ms, p99=890ms
```

The p50 stays near idle. The p99 explodes. That is the queueing signature from `latency-percentiles/01`. The DB is fine — the *queue in the app* is not.

## How to fix

1. **Increase `poolMaxConns`.** Easy, but only works until `pg_max_connections` is hit.
2. **Faster queries.** The real fix. If the query takes 5 ms, 25 conns can serve 5000 RPS. If it takes 50 ms, only 500 RPS.
3. **Connection pooling in the DB layer.** PgBouncer between app and PG. The app holds many short-lived connections; PgBouncer holds few long-lived ones to PG. The pool limit moves from "per app pod" to "global."

The lab in `database-latency/labs/pool-saturation.md` drives the pool to saturation and reads the signature off the panels.
