# Lab: lock wait vs slow query, two signatures

## Prereqs

- App + DB up.
- A second terminal on `kubectl -n shop exec -it postgres-0 -- psql`.
- The `pg_stat_activity` panel open (wait_event, state, query).

## Scenario A — slow query

Run a deliberately slow query on the DB:

```
kubectl -n shop exec -it postgres-0 -- psql -c "SELECT pg_sleep(2); SELECT * FROM products LIMIT 1000;"
```

Watch:
- `pg_stat_activity` for that session: `state = active`, `wait_event = ` (blank), `query` shows the `SELECT *`.
- `pg_stat_statements_mean_exec_time` for the `SELECT * FROM products` queryid — rises (the 2 s sleep is *inside* the query).
- The query itself is slow. No lock involved.

## Scenario B — lock wait

Open two psql sessions.

Session 1:
```
BEGIN; UPDATE products SET price = price + 1 WHERE id = 1; -- do not commit
```

Session 2:
```
UPDATE products SET price = price + 1 WHERE id = 1;
```

Session 2 *hangs*. Watch:
- `pg_stat_activity` for session 2: `state = active`, `wait_event = Lock`, `wait_event_type = Lock`.
- `pg_locks` shows the grant: session 1 holds `RowExclusiveLock` on `products`, session 2 is waiting.
- `pg_stat_statements_mean_exec_time` for the UPDATE queryid is *short* — the query itself is fast. The wait is *outside* the query.

Commit session 1. Session 2 completes instantly. The p99 of the app (if it is hitting that row) spiked during the wait, but the DB's `mean_exec_time` did not.

## Read the two signatures side by side

| | Slow query | Lock wait |
|---|---|---|
| `pg_stat_activity.state` | `active` | `active` |
| `pg_stat_activity.wait_event` | blank or `IO` | `Lock` |
| `pg_stat_statements.mean_exec_time` for the query | **high** | **low** |
| `pg_locks` | no waiters | **waiter present** |

The `wait_event = Lock` is the single field that separates the two. Alert on it:

```
sum(pg_stat_activity_wait_events{wait_event="Lock"}) > 0 for 1m
```

A *count* of lock waits, not a mean. A mean of lock waits is meaningless — either a session is waiting or it is not.

## Restore

```
kubectl -n shop exec -it postgres-0 -- psql -c "COMMIT; SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE query LIKE '%pg_sleep%'"
```

Re-check `pg_stat_activity`. No lock waits, no active slow queries.
