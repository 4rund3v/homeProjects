# Learn 01: distributed locks mechanism

[Back](../README.md)

## Why

The first lesson for distributed locks is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

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

**Exercise: stale owner fencing test.**
- Worker A acquires (token 7), pause 4 s
- Worker B acquires (token 8) at 5 s
- A resumes, writes token 7 → rejected
- Without fencing: A's write succeeds → corrupts B's state
- Measure: fencing rejection count, corruption count

```text
with fencing:  0 corruptions
without:        B's state overwritten
```
