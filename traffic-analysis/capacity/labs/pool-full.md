# Lab: force the pool to saturate, isolate its knee

The ramp lab finds the knee *empirically*. This lab *forces* the pool to its limit at a known load, so the pool's knee is isolated from the CPU and disk.

## Prereqs

- The pool-settable app (the reference app reads `POOL_MAX_CONNS` from env).
- `k6` available.

## Step 1 — pin the pool at 4

```
kubectl -n shop set deploy/shop-api env POOL_MAX_CONNS=4
kubectl -n shop rollout status deploy/shop-api
```

## Step 2 — load 200 VU

Watch for 90 s:
- `pool_in_use` — pinned at 4. `pool_idle` = 0.
- `pg_stat_activity_numbackends` — pinned at 4 (the app's pool is the limit, not the DB's).
- App p50 — near idle (~14 ms). The *work* is fine.
- App p99 — a cliff. The *wait* is the whole story.
- DB `mean_exec_time` — *flat*, near idle.

## Step 3 — read the gap

```
gap = app_p99 - pg_stat_statements_mean_exec_time
```

At 200 VU with a 4-conn pool, p99 is ~2 s and the DB mean is ~6 ms. The gap is ~2 s. **That 2 s is pure queue time.** The DB is not slow. The *queue in front of it* is.

## Step 4 — compare to the ramp

In the ramp lab, the knee was at ~200 target RPS with a 25-conn pool. Here, with a 4-conn pool, the knee is at ~200 VU *much earlier* (the pool saturates at a lower λ). Same *shape*, different *location*. The pool size moved the knee.

## Step 5 — the Little's-law check

```
L_max = 4 (the pool)
W     = 6 ms (the DB mean, the work)
λ_max = 4 / 0.006 = ~660 RPS
```

At 660 RPS the pool should be full. But the *measured* delivered RPS at 200 VU is ~115 RPS, *well below* 660. Why the gap?

Because W is *not* 6 ms at 200 VU. At 200 VU, W has climbed (the queue is part of W, and Little's law counts *all* time in the system, including the wait). The W in `λ_max = L_max / W` is the *mean time in the system at that load*, not the idle work time. The idle-work W gives an *upper bound* on capacity; the *actual* W at load is higher, so the actual capacity is lower.

That is the subtlety: **Little's law with idle W overestimates capacity.** The knee in the ramp lab is *below* the idle-W prediction, because the queue time inflates W.

## Restore

```
kubectl -n shop set deploy/shop-api env POOL_MAX_CONNS=25
kubectl -n shop rollout status deploy/shop-api
```

Re-read the baseline. `pool_in_use` back to 2–3.
