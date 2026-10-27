# Learn 01: mutexes semaphores deadlocks mechanism

[Back](../README.md)

## Why

The first lesson for mutexes semaphores deadlocks is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: DB pool sizing.**
- Pool of 50, 200 goroutines, 20 ms hold
- Measure p50/p99 transaction latency
- Increase pool to 100: measure again
- Expected: p99 drops from 100 ms to 40 ms

```text
50 permits: p99 = 100 ms
100 permits: p99 = 40 ms
```
