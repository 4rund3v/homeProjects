# 01 — Little's law, and how to use it for capacity

## The formula

```
L = λW
```

- **L** — the average number of *concurrent* requests in the system (the queue length).
- **λ** — the arrival rate (RPS).
- **W** — the average time a request spends in the system (mean latency).

Rearranged, it is a *capacity* formula:

```
max RPS (λ) = L_max / W
```

`L_max` is the maximum number of concurrent requests the system can hold (the pool size, the worker-connection limit, the thread count). `W` is the mean latency *at that load*.

## Worked example

The app's pool is 25 connections. A request holds a connection for W = 50 ms (DB query + handler).

```
L_max = 25
W     = 0.05 s
λ_max = 25 / 0.05 = 500 RPS
```

The app can sustain 500 RPS *at 50 ms mean latency*. If the DB slows to W = 200 ms:

```
λ_max = 25 / 0.20 = 125 RPS
```

The *same* pool, *four times* less capacity, because the *latency* quadrupled. The pool size did not change. The capacity did.

That is the senior-engineer insight: **capacity is not a fixed number. It is L_max / W, and W moves with the system.**

## Where L_max lives in this project

| Resource | L_max | W |
|---|---|---|
| App pool | `poolMaxConns` = 25 | mean request-to-response time |
| NGINX workers | `worker_connections` × workers | mean proxy time |
| DB | `pg_max_connections` = 100 | mean query time |
| PVC | I/O queue depth (kernel) | mean I/O time |

Each one has its own `L_max / W`. The system's capacity is the *minimum* of all of them. The pool is usually the minimum, which is why `database-latency/02` is the most important doc in the whole repo.

## The shape you will plot

For the lab, plot λ (x-axis, RPS) against W (y-axis, mean latency) and against L (z, the *implied* concurrent requests = λ × W). At low load, W is flat (the resource is not saturated), so L grows linearly with λ. At the knee, W starts to climb, so L grows *faster* than linearly. The knee is where the curve bends.

```
W
│                                ╱  (saturation: W climbs with λ)
│                              ╱
│                            ╱
│   _________________      ╱
│   (idle: W flat)   ╱─────
│                   ╱
└──────────────────────────── λ
        knee
```

The lab in `capacity/labs/load-test-ramp.md` drives λ up and reads the knee.

## The common mistake

"Scale to handle X RPS" where X was measured at *idle* latency. At idle, W is 5 ms, so λ_max = 25 / 0.005 = 5000 RPS. Under real load, W is 50 ms, and λ_max is 500 RPS. The "5000 RPS" number is *the idle number*, and it is *wrong* at real load.

The senior-engineer habit: **state the W at which the RPS number was measured.** "5000 RPS at 5 ms mean latency" is a real statement. "5000 RPS" is not.
