# Learn 01: spatial index choice mechanism

[Back](../README.md)

## Why

The first lesson for spatial index choice is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: 3-way comparison, 1M points, 3 km radius.**
- Geohash p6, H3 res 8, S2 level 15
- Measure: candidate count, p95 latency, index size
- Expected: S2 best CPU, geohash smallest index

```text
geohash: 3,396 candidates, 170 ms/s CPU
S2:      3,113 candidates, 155 ms/s CPU
```
