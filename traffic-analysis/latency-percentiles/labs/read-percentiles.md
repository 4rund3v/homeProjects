# Lab: read the percentiles off a running system

Run after `project/labs/baseline.md`.

## Prereqs

- App + NGINX + Postgres up and generating load (50 VU for 5 minutes).
- Grafana open, main dashboard.

## Step 1 — raw queries in Prometheus

Open `Prometheus / Graph`. For each, read out loud: *what is this number, and which pod(s) does it come from?*

```
# Per-endpoint p50/p95/p99, 5m window
histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint))
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint))
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint))

# The raw buckets for /api/orders
http_request_duration_seconds_bucket{endpoint="/api/orders"}

# RPS and mean
sum(rate(http_request_duration_seconds_count[5m])) by (endpoint)
sum(rate(http_request_duration_seconds_sum[5m])) by (endpoint)
/
sum(rate(http_request_duration_seconds_count[5m])) by (endpoint)
```

## Step 2 — compare L7 vs L4

The NGINX L7 view includes TLS + proxy + upstream. Compare:

```
# App view (what the app measured, before response went back through nginx)
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint))

# NGINX L7 view (includes proxy time)
histogram_quantile(0.95, sum(rate(nginx_ingress_controller_request_duration_seconds_bucket[5m])) by (le, ingress, service, target))
```

Note the difference. It should be small under 50 VU. Under 200 VU, it grows — the L7 layer adds its own latency.

## Step 3 — find a bucket-straddling p99

Pick the bucket that contains the p99 position (where cumulative count crosses 0.99 of total). Compute:

```
# Total requests
sum(rate(http_request_duration_seconds_count[5m]))

# Cumulative count below each bucket
sum(rate(http_request_duration_seconds_bucket{endpoint="/api/orders", le="0.25"}[5m]))
sum(rate(http_request_duration_seconds_bucket{endpoint="/api/orders", le="0.5"}[5m]))
```

The p99 position is between the two buckets that bracket 99% of total. The `histogram_quantile` number is a *linear interpolation* in that range. Ask: is my p99 "real" or just the midpoint of two buckets?

## Step 4 — p999

```
histogram_quantile(0.999, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint))
```

If this returns the +Inf bucket's value (or is very close to your max finite bucket), the histogram has no resolution at p999. The shape of the tail *beyond* your max bucket is invisible.

## Follow-up questions

- You measured p50 = 14 ms, p95 = 22 ms, p99 = 40 ms at 50 VU. Which one is the SLO candidate? Why not p50?
- At 200 VU the NGINX p95 is 380 ms and the app p95 is 210 ms. Where is the other 170 ms? (Read `load-balancing/02`.)
- If you set an alert on `histogram_quantile(0.95, ...) > 0.5` with `for: 5m`, what is the *earliest* you will be paged after a real incident? (Answer: 5 m after the p95 first crossed 0.5 s, plus the 5 m window, plus the alert evaluation interval. ~11 m total. Is that enough?)
