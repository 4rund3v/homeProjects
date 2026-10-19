# 02 — The saturation curve: RPS vs latency, and where the knee is

## The test

Drive λ (RPS) up in steps: 10, 50, 100, 200, 400, 800, ... At each step, hold for 60 s, record:

- λ (the target RPS, and the *actual* delivered RPS — they differ once the system is saturated).
- p50, p95, p99 (from the app histogram).
- CPU on the app pod and the node.
- The relevant queue: `pool_in_use` / `pool_max`, or NGINX `worker_connections` in use, or the DB `backends`.

## The shape, expected

```
p99
│                                          ╱ saturation
│                                        ╱
│                                      ╱
│                                    ╱
│                                 ╱
│                              ╱
│                          ╱────  ← the knee
│                     ╱────
│                ╱────
│           ╱────
│      ╱────
│   ╱────
└────────────────────────────── λ (RPS)
```

Below the knee, p99 climbs gently (the system has headroom). At the knee, p99 bends up. Past the knee, p99 climbs *steeply* — a doubling of λ more than doubles p99. That steep part is the *queuing* region; it is where `L = λW` starts to bite, because W is no longer constant.

## Finding the knee

The knee is not a single point; it is the *region* where the curve changes from gentle to steep. A practical test: plot **p99 / p50** (the *tail ratio*) against λ. Below the knee, the ratio is ~1.5–3× (the tail is not much worse than the middle). Past the knee, the ratio climbs to 10×, 50×, 100×. The *jump in the ratio* is the knee, more reliable than the jump in p99 alone.

```
p99/p50
│
│                                          ╱ (ratio explodes)
│                                        ╱
│                                   ╱────  ← knee: ratio crosses ~5
│                              ╱────
│                         ╱────
│                    ╱────
│   _____________   ╱
│   (ratio ~2)  ╱────
└──────────────────────────── λ
```

## The *delivered* RPS

Below the knee, *delivered* RPS ≈ *target* RPS (the system keeps up). Past the knee, delivered RPS *flattens* — the system cannot keep up, and requests are queuing or timing out. The delivered-RPS curve is *flatter* than the target-RPS curve past the knee. That flattening is the capacity limit.

```
RPS
│
│                        ────────── delivered (flattens at capacity)
│                     ╱
│                  ╱
│               ╱
│            ╱
│         ╱
│      ╱──────────── target (keeps climbing)
│   ╱
└──────────────────────────── λ_target
```

The gap between target and delivered, past the knee, is the *backlog*. It is what customers feel as "the site is slow."

## The lab

`capacity/labs/load-test-ramp.md` runs this exact test and reads the knee off the tail-ratio curve. The lab in `capacity/labs/pool-full.md` repeats it with the pool *pinned* at its max, so the knee is *forced* at a known λ.

## The senior-engineer read

When someone asks "what is our capacity?", the answer is:

> "At the current data size and mix, the knee is at ~600 RPS (target). Past 600 RPS, p99 climbs a cliff and delivered RPS flattens at ~700 RPS. The pool is the constraint: at the knee, `pool_in_use` is pinned at 25 and `pool_idle` is 0. If we raise the pool to 50, the knee moves to ~1100 RPS, but the *shape* is the same — the pool is still the first thing to saturate."

The number *with its W and its constraint* is the real answer. The bare number is not.
