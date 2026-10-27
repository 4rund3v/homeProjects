# Basics: optimistic locking

[Back](README.md)

## Why

Learn optimistic locking by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: editing a shared document

```text
document v=3, two editors save at t=0
```

First writer: `UPDATE doc SET body=?, version=4 WHERE version=3` → 1 row. Second writer: same → 0 rows → conflict detected.

Expected value of the update: `P(success) = 1/n` for `n` concurrent writers on one document. For n = 100, the success probability per attempt is 1%. With exponential backoff (50 ms, ×2, cap 2 s, 8 retries), expected retry ≈ `0.05 × (1 + 2 + 4 + … + 128) ≈ 4 s` — still inside a human editing session, and no lock held.

Comparison with pessimistic: a 1 ms row lock at n = 100 means 100 × 1 ms queue = 100 ms drain; optimistic means no waiting but 99% of attempts conflict.
