# 02 — Cardinality, and why it is the #1 observability incident

## What cardinality is

The number of distinct *series* in a Prometheus metric. A series is a metric name + one unique combination of all its label values.

```
http_request_duration_seconds_bucket{endpoint="/api/products", status="200", le="0.05"}
http_request_duration_seconds_bucket{endpoint="/api/products", status="200", le="0.1"}
...
```

Each `(endpoint, status, le)` combination is one series. Add a *user* label and the count multiplies by the number of users.

## The trap

A label that takes one of a *small* set of values is fine (`endpoint`, `status`, `method`). A label that takes one of a *large* set of values is a cardinality bomb:

- `user_id` — 1M users × 10 buckets = 10M series per histogram.
- `trace_id` — one per request. Infinite.
- `queryid` (from `pg_stat_statements`) — thousands in a busy service.
- `ip` — every client IP that ever hits the service.

The `pg_stat_statements` example in `database-latency/01` is the working one: the exporter's `TOP_QUERIES=20` guard keeps the `queryid` label to 20 values. Without it, a busy service exports 10000 queryids, each with its own `calls`/`mean_exec_time`/`total_exec_time`/`rows` series, and the Prometheus series count doubles.

## How to measure it

```
# Total series count
count({__name__=~"__all__"})

# Series per metric
count by (__name__) ({__name__=~".+"})

# Top 10 label values by series count
topk(10, count by (user_id) ({__name__="http_request_duration_seconds_count"}))
```

The last query answers "which user_id values are adding the most series." If it is a small set, fine. If it is "the top 10 user_ids are each adding 1M series," you have a per-user label and the metric is unqueryable.

## The senior-engineer rules

1. **No per-request labels.** No `request_id`, no `trace_id`, no `correlation_id` in a metric. Those belong in logs and traces.
2. **No per-user labels.** No `user_id`, no `tenant_id` (unless the tenant count is small, < 100).
3. **No per-IP labels.** No `client_ip`, no `peer_ip`.
4. **Histogram labels are multiplied by the bucket count.** A histogram with 12 buckets and 50 label combinations = 600 series per metric. Add a 1000-value label and you are at 600k.
5. **The `le` label is not optional on histograms.** The `histogram_quantile` function needs it. You cannot drop it.

## The incident shape

A service adds a `version` label to a request counter. The version is *meant* to be one of 10 values. In production, it is the *image tag*, and the image tag is built per commit. 5000 commits a month → 5000 version values → 5000 series per counter → the counter is unqueryable, and Prometheus starts to OOM.

The alert on cardinality:

```
# Any metric with more than 10000 series is a problem
count by (__name__) ({__name__=~".+"}) > 10000
```

The fix is not "add more RAM." The fix is "find the label that exploded and remove it." The *diagnosis* is `topk(10, count by (some_label) ({__name__="the_metric"}))`.

## The lab

`observability/labs/cardinality-trap.md` adds a `user_id` label to the app's request counter and watches the series count climb.
