# Lab: the load-test ramp, read the knee

## Prereqs

- App + DB + NGINX up.
- `k6` on the host.
- The tail-ratio query ready: `histogram_quantile(0.99, ...)/histogram_quantile(0.50, ...)`.

## The k6 script

A ramp: 10 → 50 → 100 → 200 → 400 → 800 VU, 60 s each. The reference is in `capacity/examples/k6-ramp.js` (learning shape). Each step is a new VU level held for 60 s so the percentiles stabilize.

## The table to fill

For each step, record after 30 s (let it settle):

| Step | target RPS | delivered RPS | p50 | p95 | p99 | p99/p50 | pool_in_use | CPU (app pod) |
|---|---|---|---|---|---|---|---|---|
| 10 VU | ~5 | ~5 | 8 ms | 10 ms | 12 ms | 1.5 | 2 | 5% |
| 50 VU | ~25 | ~25 | 14 ms | 22 ms | 40 ms | 2.9 | 6 | 12% |
| 100 VU | ~50 | ~50 | 28 ms | 60 ms | 150 ms | 5.4 | 12 | 25% |
| 200 VU | ~100 | ~95 | 80 ms | 300 ms | 1.2 s | 15 | 24 | 60% |
| 400 VU | ~200 | ~120 | 200 ms | 800 ms | 4 s | 20 | 25 (pinned) | 90% |
| 800 VU | ~400 | ~115 | 300 ms | 1.5 s | 8 s | 27 | 25 (pinned) | 95% |

Numbers will differ. The *shape* is the lesson.

## Read the knee

The tail ratio (p99/p50) is ~1.5–3× through 100 VU. At 200 VU it crosses ~10. **That is the knee.** Past it:

- `pool_in_use` is pinned at 25 (`pool_idle` = 0).
- Delivered RPS *flattens* (400 VU and 800 VU both deliver ~115–120 RPS).
- p99 climbs a cliff.

The *capacity* is ~200 target RPS, at which the pool saturates and delivered RPS flattens at ~120.

## The pool is the constraint

At the knee, `pool_in_use` is pinned. The DB `mean_exec_time` is *flat* (the work is fine). The *gap* between app p99 and DB mean is the *queue*. Raise the pool to 50 and re-run: the knee moves to ~400 target RPS. The *shape* is the same; the *location* of the knee moves. That is the pool-size knob, measured.

## The CPU co-constraint

At 800 VU, CPU is 95%. The pool is *also* pinned. Two constraints at once. The senior-engineer read: "we are pool-bound *and* CPU-bound at 800 VU. Raising the pool alone will not help past ~600 RPS, because CPU saturates first. The fix is both: a bigger pool *and* more CPU (or faster queries to reduce per-request CPU)."

## Restore

Stop the k6 run. Wait for load to drain. Re-read the idle baseline. `pool_in_use` returns to 2–3. p99 returns to ~12 ms.

## Follow-up

- If the pool were *infinite*, where would the next knee be? (CPU, or the PVC I/O. Read `capacity/03`.)
- If the queries were 4× faster, where would the knee move? (λ_max = L_max / W. W drops 4×, so λ_max rises 4×. The knee moves *right*.)
