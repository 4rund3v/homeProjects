# Learn 01: flash sale inventory mechanism

[Back](../README.md)

## Why

The first lesson for flash sale inventory is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: 10K requests, 1,000 units, 10% retries.**
- Without buckets: measure timeouts, oversell count
- With 10 buckets: measure p99, oversell count (should be 0)
- Verify: exactly 1,000 successes, 0 oversell

```text
raw:    2,000 timeouts, oversell possible
buckets: 0 timeouts, 0 oversell, p99 = 2 s
```
