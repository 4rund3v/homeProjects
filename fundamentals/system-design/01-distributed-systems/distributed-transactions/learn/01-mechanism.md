# Learn 01: distributed transactions mechanism

[Back](../README.md)

## Why

The first lesson for distributed transactions is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: saga outbox lag test.**
- 1,000 rps, 0.1% step failure
- Measure outbox lag every 10 s for 60 s
- Expected: 60K rows without batch fix, 0 with 500-row batch

```text
before fix: 60K rows lag
after fix:  ~0
```
