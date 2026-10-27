# Learn 01: h3 mechanism

[Back](../README.md)

## Why

The first lesson for h3 is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: resolution sweep, 1 km radius.**
- Res 7/8/9: measure candidate count, FP rate, lookup count
- Expected: res 7 = 5,920 candidates/89% FP, res 9 = 3,150/0.5%

```text
res 7: 5,920 candidates, 89% FP
res 9: 3,150 candidates, 0.5% FP
```
