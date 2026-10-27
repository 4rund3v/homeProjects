# Learn 01: concurrency fundamentals mechanism

[Back](../README.md)

## Why

The first lesson for concurrency fundamentals is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: build a sharded counter.**
- 8 threads × 100K increments = 800K total
- Global atomic: ~1M/s ceiling, ~80 ms for 80K increments
- Sharded (8 per-thread counters): ~8M/s ceiling
- Merge cost: 8 additions × 100 ns = 0.8 µs every 100K

Measure: final value, p50/p95 latency, CPU. Verify final = 800K exactly.

```text
global:  80K in 80 ms → 1M/s
sharded: 80K in 10 ms → 8M/s
```
