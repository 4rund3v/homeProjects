# Learn 01: bm25 mechanism

[Back](../README.md)

## Why

The first lesson for bm25 is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: 2 docs, k1/b grid.**
- k1 ∈ {0.5, 1.2, 2.0}, b ∈ {0, 0.5, 0.75, 1.0}
- Measure: doc A vs doc B score at each combo
- Expected: b=0 gives A the biggest advantage, b=0.75 balances

```text
k1=1.2,b=0.75: A=0.30, B=0.22
k1=2.0,b=0.5:  A=0.33, B=0.25
```
