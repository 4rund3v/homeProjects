# Learn 01: cap pacelc mechanism

[Back](../README.md)

## Why

The first lesson for cap pacelc is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: 3-replica partition test.**
- W=2, R=2, partition east from west+eu for 5 min
- Count writes during partition (CP: east = 0, AP: east = local)
- On heal: count conflicts (AP) or verify no data loss (CP)

```text
CP: east = 0 writes, 0 conflicts
AP: east = ~300 writes, 550 total to reconcile
```
