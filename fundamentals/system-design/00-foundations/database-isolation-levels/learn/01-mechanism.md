# Learn 01: database isolation levels mechanism

[Back](../README.md)

## Why

The first lesson for database isolation levels is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: oversell test, 1,000 concurrent reservations.**
- 100 tickets, 1,000 concurrent requests
- Read Committed: count successes → expect ~1,000 (oversell)
- Serializable: count successes → expect exactly 100
- Measure: p99 latency, abort count, retry count

```text
RC:  1000 successes, p99 = 2 ms
SER: 100 successes, p99 = 15 ms
```
