# Learn 01: race conditions mechanism

[Back](../README.md)

## Why

The first lesson for race conditions is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: two workers, one job, CAS guard.**
- 10,000 jobs, 2 workers polling at 100 rps
- No guard: count duplicates over 60 s
- With `UPDATE ... WHERE state='new'`: count duplicates (should be 0)

Measure: duplicate count, extra latency per claim, total time to drain 10,000 jobs.

```text
no guard:  ~200 duplicates in 1 s
with CAS:  0 duplicates, +0.5 ms per claim
```
