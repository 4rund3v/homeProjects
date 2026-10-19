# 03 — SLOs and error-rate, and why p95 alone is not an SLO

## SLI vs SLO vs SLA

- **SLI** (Service Level Indicator): a *measurement*. `p95 latency over 30 days`.
- **SLO** (Service Level Objective): a *target*. "p95 < 300 ms, 30 days, 99.9% of weeks."
- **SLA** (Service Level Agreement): a *contract* with a penalty. Customer-facing.

Enterprise teams set SLOs and alert on **burn rate** (error budget consumed faster than the window allows), not on the raw SLI.

## The 30-day / 1-week SLO shape

```
good_req  = 2xx AND duration < 300ms
total_req = all requests
sli       = good_req / total_req
slo       = 99.9% over 30 days
budget    = 1 - 0.999 = 0.001 (0.1% of requests can be bad)
```

Alerting on burn rate:

```
# Multi-window burn-rate alert:
(1 - (sli_over_5m / sli_over_30d)) > 14.4 * (1 - 0.999)
   and
(1 - (sli_over_1h / sli_over_6h)) > 14.4 * (1 - 0.999)
```

The "14.4" is the SRE-book burn-rate multiplier for a 30-day / 99.9% SLO. The meaning: you are consuming the 30-day budget at 14.4× the allowed rate, *and* the 6-hour budget at the same rate. Both windows must agree, or you get false positives from a single 5-minute blip.

## Why "p95 < 300 ms" is not an SLO by itself

p95 is a *statistic*, not a *rate*. An SLO is a rate of *bad things* over a window. `p95 < 300ms` is a healthy-shape check; it tells you nothing about "how many users are affected right now." The SLO formulation above (good_req / total_req) tells you both.

In practice, teams keep **both**:

- `p95/p99` panels for *shaping* — is the tail growing?
- `good_req ratio` for *alerting* — are we burning budget?

## A concrete SLO for this project

```
SLI:  p95 of http_request_duration_seconds{endpoint="/api/orders"} < 500ms
Window: 30 days, computed every 5m
SLO:    99.5% of 5-minute windows meet the target
Budget:  0.5% * (30d / 5m) = 0.5% * 8640 windows ≈ 43 windows
```

43 windows of 5 minutes is ~3.5 hours over a month. If you burn 43 windows in the first week, you are already in trouble.

## Burn-rate alert for this SLO

```
# 2-window burn rate, 14.4×:
( (1 - (sum(rate(http_requests_good[5m])) / sum(rate(http_requests_total[5m]))))
  > (14.4 * (1 - 0.995)) )
and
( (1 - (sum(rate(http_requests_good[1h])) / sum(rate(http_requests_total[1h]))))
  > (14.4 * (1 - 0.995)) )
```

`http_requests_good` is a recorded rule:

```
http_requests_good:rate5m = sum(rate(http_request_duration_seconds_count{status=~"2.."}[5m])) by (endpoint)
http_requests_good_duration_ok:rate5m = ...
```

In practice you record the *combined* SLI once, and every alert and dashboard reads the recorded rule. One source of truth.
