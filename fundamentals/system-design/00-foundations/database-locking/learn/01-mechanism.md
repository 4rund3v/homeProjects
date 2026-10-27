# Learn 01: database locking mechanism

[Back](../README.md)

## Why

The first lesson for database locking is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

## How

Draw the smallest system that exhibits the problem. Run one control case, then vary one input: concurrency, data size, failure rate, or freshness requirement.

## Under the hood

Trace one operation through memory, network, storage, and recovery. Write down every durable boundary and every point where a duplicate or stale result can appear.

## Exercise

Implement or simulate the smallest example from the topic README. Record workload, expected invariant, observed result, and the change that makes the invariant hold.

## Senior checkpoint

- Which assumption is load-bearing?
- What is the saturation knee?
- What is the safe recovery action?

## Worked numbers

**Exercise: lock footprint, 10M-row table.**
- UPDATE 1 row with no index: count lock rows (pg_stat_activity or innodb_locks)
- Add index on order_id: count lock rows
- Expected: 10M vs 1

```text
no index: ~10M locks
with idx:  1 lock
```
