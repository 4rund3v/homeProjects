# Basics: flash sale inventory

[Back](README.md)

## Why

Learn flash sale inventory by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: 10,000 requests, 1,000 units, 10% retries

```text
inventory = 1,000
arrival   = 10,000 unique requests (qty=1 each)
retries   = 1,000 duplicates (10% of clients retry after timeout)
```

Expected: exactly 1,000 successes, 9,000 "sold out," and 0 oversells.

Without idempotency, the 1,000 retries re-decrement 1,000 rows and the final inventory reads -1,000 (the invariant broke on the 901st successful response). With an idempotency key scoped to `(customer, sku, session)`, each retry returns the same reservation.

Scaled math: 50,000 rps against one SKU. A hot-row DB supports ~5,000 conditional updates/second. Token buckets help: split into 10 buckets of 100 units. Throughput scales 10×. Reconciliation: every `10 × 100 = 1,000` allocations, cross-check `sum(bucket_used) == total_sold - 0`. A drift of 1 unit triggers an audit job.
