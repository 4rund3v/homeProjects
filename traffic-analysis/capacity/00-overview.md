# 00 — Capacity is a shape, not a number

A senior engineer does not answer "what is our capacity?" with a number. They answer with a *curve*: RPS vs latency, at 25%, 50%, 75%, 100% of max load. The curve has a *knee* — the point where p99 starts to climb a cliff instead of a slope. The knee is the capacity.

## Why not a number

"Capacity is 5000 RPS" is wrong, because it depends on the mix (how many `/api/products` vs `/api/orders`), the data (how big is the product catalog), and the dependencies (is the DB on the same node as the app?). The *curve* captures all of that. The number is a *slice* of the curve, at one mix, on one day.

## The three tools

1. **Little's law** (`capacity/01`) — the relationship between RPS, latency, and concurrent connections. The single most useful formula in capacity.
2. **The saturation curve** (`capacity/02`) — RPS vs p99, plotted. The knee is the capacity.
3. **The queue** (`capacity/03`) — where the latency goes when the system is saturated. The pool, the DB, the L7 layer.

## Where in this project

The app is the queue. The DB pool is the *resource* the queue waits on. NGINX has its own queue (worker connections). The PVC has an I/O queue. Every one of them has a Little's-law relationship, and the knee of the *whole* system is the minimum of the knees of its parts.

The lab in `capacity/labs/load-test-ramp.md` drives the system and reads the knee off the curve. The lab in `capacity/labs/pool-full.md` isolates the pool's knee from the rest.

## The rule

You do not *measure* capacity. You *map* it: at 25 / 50 / 75 / 100% of the max load you can sustain, record RPS, p50, p95, p99, CPU, and the relevant queue length. The *shape* of that table is the answer. A single "max RPS" number is a lie.
