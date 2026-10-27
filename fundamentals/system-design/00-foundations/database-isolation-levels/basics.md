# Basics: database isolation levels

[Back](README.md)

## Why

Learn database isolation levels by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: two concurrent bookings

```text
seat = "A10", 1 ticket available, 2 buyers race
```

Under **Read Committed**, both readers see 1 ticket. Both write. Total sold = 2. Oversell.

Under **Repeatable Read**, each transaction sees a snapshot: still both may start from the "1 ticket" view, so write skew survives unless the engine detects the conflict (PostgreSQL serializable uses predicate locking to catch this and aborts one transaction).

Under **Serializable**, one transaction is aborted and must retry:

```text
T1: BEGIN → read 1 ticket → write sold=1 → commit
T2: BEGIN → read 1 ticket → write sold=1 → aborted
T2 retries: BEGIN → read sold=1 → write sold=2 → commit
```

Retry probability. If 200 concurrent requests target one SKU and each holds the row lock ~1 ms, expected abort fraction ≈ `1 - exp(-λt)` where λ is arrival rate and t is lock hold. At λ = 100 req/ms and t = 1 ms, ~63% of requests would need to retry. Scaled: at 10,000 rps the lock hold would need to be < 100 µs to keep retry rate under 10%.
