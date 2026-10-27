# Basics: pessimistic locking

[Back](README.md)

## Why

Learn pessimistic locking by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: 1,000 hot reservations

```text
seat A10 = 1 seat
arrival  = 1,000 concurrent reservations
lock hold = 2 ms
```

Throughput ceiling = `1 / 0.002 s` = 500 reservations/second on that row. The first 1,000 requests queue; total drain = `1,000 × 2 ms = 2 s`. p50 ≈ 1 s, p99 ≈ 2 s.

If the critical section is 20 ms (a payment call inside the lock), the ceiling drops to 50/second and drain is 20 s. The payment call must move outside the lock; the invariant is protected only while the row is locked.

Scaled: 100 hot SKUs spread over 100 rows → each row carries ~1,000/100 = 10 reservations → 20 ms each → 200 ms drain per row. Same total work, 10× better tail latency.
