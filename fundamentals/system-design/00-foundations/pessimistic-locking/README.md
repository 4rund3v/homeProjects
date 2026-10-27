# Pessimistic locking strategies

[Back](../../README.md)

## Why

Pessimistic locking assumes conflicts are common or expensive to recover from. It blocks a competing writer before it can make a conflicting decision.

## How

```sql
BEGIN;
SELECT available FROM inventory
WHERE sku = ?
FOR UPDATE;
-- validate and decrement while lock is held
UPDATE inventory SET available = available - ? WHERE sku = ?;
COMMIT;
```

The lock starts before the business decision and ends at commit or rollback.

## Under the hood

The lock manager records ownership and queues waiters. A lock timeout or deadlock aborts the transaction. The protected record must be found through a selective index; otherwise the database may lock a broad range.

Pessimistic locking is strongest when the critical section is short and the owner is reliable. Never hold it across network calls, user input, or unbounded queue waits.

## Production use cases

- Seat assignment where conflicts are frequent.
- Single-row inventory decrement during a hot sale.
- Sequential number allocation.
- Worker claim where the database is the source of truth.

## Trade-offs

| Benefit | Cost |
|---|---|
| Simple conflict semantics | waiting and lock contention |
| No failed optimistic retries | deadlocks and lock timeouts |
| Immediate protection | hot-row bottleneck |

## Lab

Run 100 concurrent reservations against one SKU with a row lock. Measure successful reservations, lock wait p99, and throughput. Compare one hot SKU with 1,000 evenly distributed SKUs.

## Worked examples

**Situation: 1,000 concurrent reservations, 1,000 rps on one row.**
Row lock hold = 2 ms. Throughput ceiling = 1 / 2 ms = 500 rps. The first 500 requests drain in 1 second; the remaining 500 queue. p50 ≈ 0.5 s, p99 ≈ 1 s. With a payment call (100 ms) inside the lock, the hold becomes 102 ms → ceiling = 9.8 rps. 1,000 requests drain in ~102 s. Move the payment call outside the lock: hold returns to 2 ms, ceiling returns to 500 rps.

```text
lock inside:  1,000 × 102 ms = 102 s
lock outside: 1,000 × 2 ms   = 2 s
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
