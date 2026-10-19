# 04 — Alerting on SLOs, not on symptoms

## The two alert styles

**Symptom alert**: "p95 > 500 ms." Fires when a *number* crosses a *threshold*. The engineer must then diagnose *why*.

**SLO alert**: "error budget burn rate > 14.4×." Fires when the *SLO itself* is at risk. The engineer knows the *what* (we are burning budget) and only has to find the *why*.

The SLO alert is the senior one. It is in `latency-percentiles/03`. This doc is about the *engineering* of making it work.

## The 2-window burn-rate alert

```
# Fast burn: 5m window, 1h window
(1 - (sli[5m] / sli[1h])) > 14.4 * (1 - slo)

# Slow burn: 6h window, 3d window
(1 - (sli[6h] / sli[3d])) > 6 * (1 - slo)
```

Two alerts, not one:

- **Fast burn** pages a human. "We are going to blow the budget *today*."
- **Slow burn** is a *ticket*. "We are on pace to blow the budget *this month*." No page; a Slack #slo-channel message.

The 14.4 and 6 are the SRE-book multipliers for a 30-day / 99.9% SLO. For a 99.5% SLO the numbers change (look them up; do not guess).

## Why not alert on the raw SLI

`p95 > 500 ms` fires on *every* p95 spike, including the ones that are not SLO-relevant (a 10-second blip, a deploys-caused bump, a batch job). The burn-rate alert *integrates* over a window, so a blip that lasts 5 m does not consume the 30-day budget and does not page.

The raw SLI is a *panel*, not an *alert*. The burn rate is the alert. The panel tells you the shape; the alert tells you the consequence.

## The `for` clause

```
alert: SloburnFast
expr: (1 - (sli[5m] / sli[1h])) > 14.4 * (1 - slo)
for: 2m
```

`for: 2m` means "the condition must hold for 2 consecutive evaluation intervals before the alert fires." It is a *dedup* on the alert side. Without it, a single bad evaluation interval pages. With it, a 2-minute sustained problem pages.

The rule of thumb: `for` should be ~50% of the *fastest* window. For a 5m window, `for: 2m`. For a 6h window, `for: 30m`.

## The recorded rule

The `sli[5m]` and `sli[1h]` in the alert are *recorded* rules, not raw expressions:

```
record: sli:5m
expr: sum(rate(http_requests_good[5m])) / sum(rate(http_requests_total[5m]))
```

The recorded rule is computed *once* on every evaluation interval, and the alert reads the precomputed value. This keeps the alert expression short and the dashboard and the alert *consistent* (they read the same recorded rule).

The anti-pattern is a dashboard that computes the SLI inline and an alert that computes it a *different* way. The two numbers disagree, and the engineer does not know which one to trust.

## The alert must name the *unit*

```
annotations:
  summary: "Fast SLO burn: p95 budget consumed at 14.4x rate"
  description: "sli[5m]=0.981, sli[1h]=0.995. Budget consumed in ~2h at this rate."
```

The description should *compute the consequence* in the annotation. "Budget consumed in ~2h" is actionable. "SLI is low" is not.
