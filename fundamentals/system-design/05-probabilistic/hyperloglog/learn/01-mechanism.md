# Learn 01: hyperloglog mechanism

[Back](../README.md)

## Why

The first lesson for hyperloglog is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: 10M uniques, m=4096 vs m=131,072.**
- Measure: estimated vs actual, error %
- Expected: m=4096 = ±1.6%, m=131,072 = ±0.81%
- Merge 100 shards: measure merge time
- Expected: O(4,096) element-wise max ≈ 1 ms

```text
m=4096: ±1.6%
m=131K: ±0.81%
```
