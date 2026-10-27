# Learn 01: geospatial introduction mechanism

[Back](../README.md)

## Why

The first lesson for geospatial introduction is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: nearby search, 5 km radius.**
- 2,000 rest/100 km², 10K queries
- Naive scan: measure p95
- Geohash index: measure p95
- Expected: naive = ~2 ms, index = ~8 µs

```text
naive: 2 ms
index: 8 µs (130× faster)
```
