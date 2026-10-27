# Learn 01: probabilistic overview mechanism

[Back](../README.md)

## Why

The first lesson for probabilistic overview is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: 100M IDs, structure selection.**
- HLL m=4096: measure error vs exact set
- CMS ε=0.01: measure top-10 vs exact
- Bloom 1%: measure FP rate on 1M unseen keys
- Expected: HLL ±1.6%, CMS 1% over, Bloom 1% FP

```text
HLL: ±1.6%
CMS: 1% over
Bloom: 1% FP
```
