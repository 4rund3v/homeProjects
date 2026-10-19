# 00 — Why percentiles, not averages

An average is a single number that a single slow request can make look great. A p95 is the value below which 95% of requests fall — the customer who lands in the top 5% is the one who tweets.

Enterprise services are judged on percentiles, not means, for one reason: the *tail* is where your users are. A mean of 200 ms is fine. A p95 of 2 s with 4% of requests in the 1–2 s bucket is not fine, even though the mean looks better than the p95.

## Where percentiles live in this repo

- App: `http_request_duration_seconds_bucket` (Prometheus histogram from the Go app).
- NGINX Ingress: `nginx_ingress_controller_request_duration_seconds_bucket` (L7 view, includes TLS + upstream + proxy time).
- Postgres: `pg_stat_statements` has `mean_exec_time` (a *mean*, not a histogram — you compute percentiles by bucketing `total_exec_time / calls` yourself; see `database-latency/01`).

## The rule you will keep re-learning

You can only compute a percentile *from* a histogram (or a summary). A mean you computed by hand is not a percentile. `pg_stat_statements_mean_exec_time` is a mean — the *most misleading* number in this whole stack if you read it as a p95.

## SLO shape

An enterprise SLO is a *rate-based* SLI:

```
error rate      = 1 - (good requests / all requests)
good request    = 2xx AND duration < 300ms
window         = 30 days, 1-week burn rate
```

The 300 ms threshold is itself a p95-ish number. How to pick it is `03-slo-errortrate`.
