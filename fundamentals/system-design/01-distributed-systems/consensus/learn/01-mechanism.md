# Learn 01: consensus mechanism

[Back](../README.md)

## Why

The first lesson for consensus is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: 5-node Raft, partition test.**
- Partition F3+F4 from L+F1+F2
- Measure: commit latency during partition (L+F1+F2 = quorum)
- Kill F1: L+F2 = 2/5, no quorum → writes blocked
- Heal: measure catch-up time

```text
partition: 3 s catch-up
no quorum: 0 commits
```
