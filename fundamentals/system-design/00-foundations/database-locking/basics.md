# Basics: database locking

[Back](README.md)

## Why

Learn database locking by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: scan vs point lookup lock scope

An `UPDATE` with no matching index scans the whole table:

```text
table rows      = 10,000,000
match condition = 1 row (order_id = 48291)
without index   → touches ~10M rows, locks 10M
with index      → touches 1 row, locks 1
```

The difference between lockable units is 10,000,000×. Each locked row consumes memory in the lock manager; at 16 bytes/entry, a 10M-row scan holds ~160 MB of lock metadata.

Lock convoy at 1 rps is benign; at 1,000 rps on the same 10M-row scan, p99 wait = `10,000,000 / (1,000 × 60,000 rows/s)` ≈ 167 minutes. With the index, p99 ≈ 1 ms.
