# Learn 01: optimistic locking mechanism

[Back](../README.md)

## Why

The first lesson for optimistic locking is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: 100 concurrent writers, 1 document.**
- 100 writers, version check, 50 ms backoff
- Measure: success rate, p50/p99 retry time
- Expected: 1% success, p99 = 25 s
- Compare: pessimistic 1,000 × 2 ms = 2 s

```text
optimistic p99: 25 s
pessimistic p99: 2 s
```
