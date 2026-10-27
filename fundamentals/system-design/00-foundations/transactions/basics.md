# Basics: transactions

[Back](README.md)

## Why

Learn transactions by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: transfer that must be atomic

```text
A.balance = 100
B.balance = 100
transfer amount = 40
```

A crash after `A.balance = 60` but before `B.balance = 140` destroys conservation of money. The WAL records both intended changes before commit:

```text
LSN 101  A -40
LSN 102  B +40
LSN 103  COMMIT
```

On restart, either the commit marker exists and replay applies both, or it does not and the changes are undone. At 1,000 transfers/second and 200 bytes/entry, WAL generation is about 200 KB/s.

A 5 ms update plus 10 ms fsync puts the p99 budget in danger when log IO spikes. Measure fsync separately from lock wait.
