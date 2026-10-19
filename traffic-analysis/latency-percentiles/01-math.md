# 01 — Percentiles, the math, and the shapes you will see

## The shape, drawn

The *tail* peels off in a fixed order as load rises. This is the *one* diagram to keep in your head for this whole topic:

```mermaid
linechart
    title "p50 / p95 / p99 vs load — the tail peels off in order"
    x-axis "load (VU)" 0, 50, 100, 200, 400, 800
    y-axis "latency (ms)" 0, 50, 100, 200, 500, 1000
    "p50" 8, 14, 28, 80, 200, 300
    "p95" 10, 22, 60, 300, 800, 1500
    "p99" 12, 40, 150, 1200, 4000, 8000
```

- **p50** (the median) climbs *last* and *gently*. It is the *typical* user.
- **p95** climbs in the *middle*. It is the *slow* user.
- **p99** climbs *first* and *fastest*. It is the *tail*, and it is where the *queue* shows up.

Below the knee (left side), all three are *close together*. Past the knee, they *fan out* by orders of magnitude. The *fan-out* is the *queueing signature* — the *work* is not slow, the *wait* is. See `capacity/01` for the theory and `capacity/03` for where the wait lives.

## Definition

Sort N latencies. `p50` is the value at position `0.50 * N`. `p95` at `0.95 * N`. `p99` at `0.99 * N`. With N = 1000, p95 is the 950th-smallest value.

## Histogram vs summary vs quantile

| Shape | What it stores | Cost | What you can compute |
|---|---|---|---|
| Mean | sum, count | 1 sample | mean only |
| Summary | pre-computed p50/p95/p99 | 3–5 samples | those 3 only, no others |
| Histogram | bucket counts per range | 10–50 samples | *any* quantile, but only within bucket resolution |

Prometheus stores **histograms** from `*Histogram` collectors. You get p50, p95, p99, p999 out of one histogram. You do *not* get p92.3 out of it — that is the resolution limit, covered in `02`.

## Bucket choice

The Go app's `httpHistogram` uses buckets `{.005, .01, .025, .05, .1, .25, .5, 1.0, 2.5, 5.0, 10.0}`. The buckets are *not* evenly spaced — they are chosen so each bucket spans roughly a 2–3× range of the previous. That is what makes p99 fall into a bucket instead of being the +Inf bucket.

If your p99 always lands in +Inf, the histogram has no bucket above your p99. The fix is not "add more buckets" — the fix is that your SLO is in a different range than your buckets.

## The tail-shape you will see in this project

At idle, all percentiles collapse to one number. As load rises, in order:

1. p99 rises first (the tail is where contention shows).
2. p95 rises next.
3. p50 is last — the median user is *fine* while 1% of users are dead.

That ordering is the signature of a queueing system under saturation. The theory is `capacity/01-littles-law`.

## The anti-shape

p50 rises before p99. That means *every* request is slow. That is not queueing — that is a systemic problem: CPU saturation, a bad code path, a DB that is slow for everyone.
