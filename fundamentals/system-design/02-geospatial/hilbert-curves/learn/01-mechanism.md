# Learn 01: hilbert curves mechanism

[Back](../README.md)

## Why

The first lesson for hilbert curves is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: row-major vs Hilbert, 10×10 window.**
- 1024×1024 grid, 1M points
- Measure: cells scanned, I/O bytes, query time
- Expected: row-major = 160 KB, Hilbert = 6.4 KB

```text
row-major: 160 KB
hilbert:   6.4 KB (25× less)
```
