# 00 — What a senior engineer watches in a database

A database is the slowest resource in most enterprise services. It is also the one that *never lies* about its own state — `pg_stat_*` is the source of truth. The problem is that it exposes *means*, not percentiles, so the senior engineer has to build percentiles from the means.

## The four things to watch

1. **Connection count** — `pg_stat_activity_numbackends`. When it hits the pool limit, everything queues.
2. **Query latency** — `pg_stat_statements` has `mean_exec_time` (a *mean*, not a histogram). You compute a "p95-ish" by bucketing queries.
3. **Lock waits** — `pg_stat_activity.wait_event`. When it spikes, the DB is not slow, it is *blocked*.
4. **Replication lag** — `pg_stat_replication` (primary) and `pg_stat_wal_receiver` (replica). When it spikes, reads on the replica are stale.

## The rule

`pg_stat_statements_mean_exec_time` is the most misleading number in this stack. A mean of 5 ms looks fine while one query is 500 ms and 99 others are 4 ms. Always pair the mean with the *count* of slow queries, not the mean itself.

The alert in `project/examples/alert-rules.yaml` (`PgSlowQueries`) does exactly that: alert on a *count* of queries above a threshold, not on a mean.

## Where in the stack

```
  app pod  ──►  pool (25 conns)  ──►  postgres pod  ──►  PVC
```

The pool is in the app. The DB is the pod. The PVC is the disk. Each layer has its own failure mode, covered in the docs that follow.
