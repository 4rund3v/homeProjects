# Basics: distributed transactions

[Back](README.md)

## Why

Learn distributed transactions by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: 2PC in-doubt window

```text
coordinator → participants A, B
A.prepare, B.prepare succeed
coordinator crashes here
```

Participants A and B are in-doubt: they hold locks and cannot commit. They must hold until the coordinator recovers and sends commit/abort, or until a timeout promotes a recovery path.

Lock-hold time = `coordinator MTBF + recovery time`. If coordinator MTBF = 30 days and recovery = 5 minutes, in-doubt lock hold is p99 ≈ 5 min. At 1,000 rps with 0.001% 2PC transaction failure, expected in-doubt locks = `1,000 × 0.00001 × 300 s ≈ 3` concurrent in-doubt rows — manageable.

With a 60-second 2PC timeout, if a participant drops to 10% availability, in-doubt rate rises ~10×.
