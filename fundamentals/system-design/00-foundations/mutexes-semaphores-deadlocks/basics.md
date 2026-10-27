# Basics: mutexes semaphores deadlocks

[Back](README.md)

## Why

Learn mutexes semaphores deadlocks by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: database pool of 50

Assume an API can run 200 goroutines and the database permits 50 concurrent sessions.

```text
pool permits = 50
queue limit  = 100
average hold  = 20 ms
max throughput = 50 / 0.020 = 2,500 transactions/second
```

A semaphore bound prevents all 200 goroutines from opening sessions. Without it, the 151st–200th requests produce database connection errors or process exhaustion.

For a 10 ms p99 transaction target, average wait plus execution must fit the SLO. If p99 execution is 8 ms, queue time has only 2 ms. Little's law says `queue ≈ arrival_rate × wait_time`; an overload that holds 100 waiters for 20 ms produces 2,000 queued slots at peak.

Deadlock example:

```text
T1 locks customer C
T2 locks inventory I
T1 wants I
T2 wants C
```

If both requests hold one lock while waiting for the other, no progress occurs. Fix by always acquiring `C` then `I`, or by using a single transaction scope with an explicit lock order.
