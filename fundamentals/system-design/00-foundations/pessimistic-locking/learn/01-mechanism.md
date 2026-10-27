# Learn 01: pessimistic locking mechanism

[Back](../README.md)

## Why

The first lesson for pessimistic locking is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: hot row, 1,000 concurrent reservations.**
- 1 SKU, 1,000 rps, 2 ms lock hold
- Measure: p50, p99, successful reservations
- Add 100 ms payment call inside lock: measure again
- Expected: p99 jumps from 1 s to ~102 s

```text
lock in:  p99 = 102 s
lock out: p99 = 1 s
```
