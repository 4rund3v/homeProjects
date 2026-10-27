# Basics: distributed locks

[Back](README.md)

## Why

Learn distributed locks by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: 5-second lease, 400 ms pause

```text
lease           = 5 s
renew deadline  = 3 s
GC pause        = 0.4 s
network RTT     = 200 ms
```

Worker A renews at 3 s, spends 0.4 s in a pause, and sends at 3.4 s. Worker B can acquire at 5 s. A resumes and tries to renew at 3.4 s; the service says "not owner."

Without fencing, A may still issue writes to the protected resource after B took over. With fencing:

```text
A token = 7
B token = 8
store accepts writes only if last_fence < token
```

A's late write fails because `last_fence = 8`.

Throughput impact: a long-running 10-minute job needs `600 s / 3 s = 200` renewals. Each renewal is one round trip. A lost renew packet costs one retry; a paused owner costs ownership until expiry.
