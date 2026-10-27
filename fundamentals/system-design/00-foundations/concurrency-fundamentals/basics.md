# Basics: concurrency fundamentals

[Back](README.md)

## Why

Learn concurrency fundamentals by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: 100 requests, one SKU, 100 units

Assume 100 simultaneous reservations for 1 unit. The database supports 2,000 conditional updates/second on this row, but row-lock queuing makes p50 5 ms and p99 40 ms.

```text
throughput = 2,000 rps
arrival   = 100 requests at t = 0
queue age ≈ 100 / 2,000 = 50 ms worst case
```

The first 100 units may succeed, but only if the decrement is atomic. Without a critical section, 100 requests can read 100 available and all decrement from the old value, leaving 0 and overselling by 99.

Scaled: 1 million requests and 10,000 units. One hot row is unlikely to sustain 1 million rapid updates. Split into 100 buckets of 100 units. Each request chooses a bucket; every 100 allocations require one cross-bucket audit. Throughput scales roughly with the number of buckets until the audit or lock table becomes the bottleneck.

