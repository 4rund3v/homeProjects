# Learn 01: bloom filters mechanism

[Back](../README.md)

## Why

The first lesson for bloom filters is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: 1M URLs, 1% FP target.**
- Build filter (m=9.6M bits, k=7)
- Query 1M unseen keys: count FPs
- Insert 2M keys: re-measure FP rate
- Expected: 1M = ~1%, 2M = ~23%

```text
1M: ~1% FP
2M: ~23% FP
```
