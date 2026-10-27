# Learn 01: geohash mechanism

[Back](../README.md)

## Why

The first lesson for geohash is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: precision sweep, 1 km radius.**
- 1M points, 100 pts/km²
- Precision 5/6/7: measure candidates, FP rate, p95
- Expected: p6 = 360 candidates/15% FP, p7 = 40/10%

```text
p6: 360 candidates, 15% FP
p7: 40 candidates, 10% FP
```
