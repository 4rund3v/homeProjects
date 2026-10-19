# 01 — pg_stat_statements: the query ledger

`pg_stat_statements` is a shared-memory table that aggregates every statement executed on the instance. One row per *normalized* query (literals replaced with `$1`, `$2`, ...).

Columns you will actually read:

| Column | Meaning | What to do with it |
|---|---|---|
| `calls` | How many times this query ran. | High + low mean_exec_time = hot path. High + high mean_exec_time = expensive hot path, fix first. |
| `total_exec_time` | Sum of exec time across all calls. | The real "cost" of this query. Sort by it, not by mean. |
| `mean_exec_time` | `total_exec_time / calls`. | A *mean*. Use it to *find* the slow queries, not to *measure* the tail. |
| `rows` | Average rows returned. | A high-rows query is expensive even at low exec time. |
| `shared_blks_hit` / `shared_blks_read` | Cache hits vs disk reads. | `shared_blks_read` > 0 means the working set does not fit in shared_buffers. |

## The exporter

`postgres-exporter` (sidecar on the PG pod, or a separate deployment) scrapes `pg_stat_statements` and exports it as Prometheus metrics:

```
pg_stat_statements_calls{queryid="abc", query="SELECT $1, $2 FROM products WHERE ..."}  12345
pg_stat_statements_total_exec_time{queryid="abc", ...}                                   4567.8
pg_stat_statements_mean_exec_time{queryid="abc", ...}                                   0.37
pg_stat_statements_rows{queryid="abc", ...}                                              2.3
```

## The cardinality trap

`queryid` is a 64-bit hash. In a busy service, `pg_stat_statements` can hold *thousands* of distinct queryids (the default `pg_stat_statements.max` is 10000). Exporting every one of them as a Prometheus series multiplies your series count by the queryid count.

The exporter has a `topqueries` filter: only export the top N by `total_exec_time`. Set N to 10–20. Beyond that, the cardinality is not worth it.

```
-- topqueries filter (exporter flag)
--topqueries=20
```

This is the "cardinality traps are a real incident" example from `observability/02`.

## Reading it like a senior engineer

For each of the top 10 queries by `total_exec_time`:

1. What is the `calls` rate? (Is it a hot path or a one-off?)
2. What is the `mean_exec_time`? (Per-call cost.)
3. What is the `rows`? (Returning 100k rows is a bug, not a query.)
4. What is the `shared_blks_read`? (0 = all in cache. >0 = hitting disk, look at the PVC.)

If `mean_exec_time` for a hot query is 50 ms and `rows` is 1, the query itself is slow — likely a missing index. If `rows` is 50000, the query is *by design* expensive — fix the application, not the query.
