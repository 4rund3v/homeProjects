# Learn 01: consistency models mechanism

[Back](../README.md)

## Why

The first lesson for consistency models is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: cart read-your-writes test.**
- 100K reads/s, 50 ms replication lag
- Eventual: count "empty cart after add" events in first 50 ms
- Session routing: count same events
- Expected: eventual = ~5% miss, session = 0

```text
eventual: ~5% stale reads
session:  0
```
