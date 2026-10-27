# Learn 01: introduction mechanism

[Back](../README.md)

## Why

The first lesson for introduction is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: 3-hop request with fault injection.**
- Inject: 10% timeouts, 5% duplicates, 2% reordering
- Measure: duplicate business ops without vs with idempotency key
- Expected: 100 duplicates/s without, 0 with

```text
without key: 100 duplicates/s
with key:    0
```
