# Learn 01: failure handling mechanism

[Back](../README.md)

## Why

The first lesson for failure handling is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: circuit breaker fault injection.**
- Dependency: 20% failures, 5 s p99
- Without breaker: measure blocked time (5,000 s/s)
- With breaker: measure blocked time (1 s/s)
- Measure: breaker open/close cycle count, probe success rate

```text
no breaker: 5,000 s/s blocked
breaker:    1 s/s blocked
```
