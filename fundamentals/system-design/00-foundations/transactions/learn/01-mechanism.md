# Learn 01: transactions mechanism

[Back](../README.md)

## Why

The first lesson for transactions is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: crash recovery, fund transfer.**
- 1,000 transfers/s, kill process after 30 s
- Count: committed transfers = ?
- Expected: floor(30 × 1,000 / fsync_batch) × fsync_batch
- Replay time: 30,000 entries at 10K/s = 3 s

```text
committed: ~30,000
recovery:  3 s
```
