# Learn 01: count min sketch mechanism

[Back](../README.md)

## Why

The first lesson for count min sketch is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: top-IP, 10M distinct, 100M events.**
- CMS (272×5): measure top-10 vs exact map
- Measure: memory, overestimate factor
- Expected: 10.9 KB, top-10 correct, counts inflated ~1%

```text
CMS: 10.9 KB, 1% over
exact: 80 MB, 0% error
```
