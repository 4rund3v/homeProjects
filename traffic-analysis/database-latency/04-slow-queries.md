# 04 — Lock waits and slow-query thresholds

## The two "DB is slow" stories

When the DB is slow, it is almost always one of two things:

1. **The query is slow.** No index, a full-table scan, a huge `IN (...)` list. Fix: the query, the index, the application.
2. **The DB is locked.** Another session holds a row lock (or a table lock) and is waiting. The second session queues. Fix: the first session, the transaction, the isolation level.

The two look *very* different in the metrics.

## Query-slow signature

- `pg_stat_statements_mean_exec_time` for a specific `queryid` rises.
- `pg_stat_activity` shows the session in `active` state, not `waiting`.
- `pg_stat_user_tables.n_tup_read` (rows scanned) is high relative to `n_tup_fetched` (rows returned). Scan-to-fetch ratio > 100 = the query is scanning too much.

## Lock-wait signature

- `pg_stat_activity.wait_event` = `Lock` (a specific lock, not I/O).
- The session is in `waiting` state, not `active`.
- Another session holds the lock: `pg_locks` shows the granting session.
- `pg_stat_statements` for the *waiting* query has a short `mean_exec_time` (the query itself is fast) — the wait is *outside* the query.

The lab in `database-latency/labs/lock-wait.md` drives both and reads the two signatures off `pg_stat_activity`.

## The slow-query threshold

The conventional "slow query" threshold is 500 ms. It is a *policy* number, not a *physical* one. Pick it from your SLO:

```
SLO: p95 < 300 ms, 30 days
     → the DB must answer in < 200 ms for 95% of queries (leave headroom for the app)
     → the slow-query threshold is 200 ms, not 500 ms
```

The exporter does not know your SLO. It reports `mean_exec_time`. You set the threshold in the alert:

```
sum(rate(pg_stat_statements_calls{queryid=~".+"} [5m]) * on(queryid) group_left
    (pg_stat_statements_mean_exec_time > 0.2)) > 0
```

Read: "over the last 5 m, at least one query with mean exec time > 200 ms was called." This is a *count*, not a mean. The mean of all queries can be 50 ms while one query is 2 s — the count catches it.

## The threshold is per-query, not global

Never alert on "mean exec time of all queries > X." That is a smeared number. Always alert on "the count of queries above X, in the last window." The `topk(10, pg_stat_statements_mean_exec_time)` panel in the dashboard shows the top 10 slow queries — that is the *shaping* view. The alert is on the *count* above threshold.
