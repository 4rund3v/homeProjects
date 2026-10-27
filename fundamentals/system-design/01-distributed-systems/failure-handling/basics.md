# Basics: failure handling

[Back](README.md)

## Why

Learn failure handling by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: circuit breaker with 20% failure rate

```text
dependency SLO: p99 < 200 ms, availability > 99.9%
actual: 20% failures, p99 = 5,000 ms
breaker: 100 requests, 20 failures open it
```

Without a breaker: each request waits 5 s before timing out. 1,000 requests/second → 1,000 in-flight. The calling pool saturates, queue grows unbounded.

With the breaker open: 1,000 requests/second fail immediately in ~1 ms. The dependency gets 1 probe request per 5 s. If it recovers, the probe succeeds and the breaker half-opens, admitting 10% of traffic.

Scaled math: half-open admission is `10% × 1,000 = 100 rps`. If the dependency can only sustain 50 rps, it takes `100 / 50 = 2` cycles to settle. Alert when the breaker stays open > 60 s.
