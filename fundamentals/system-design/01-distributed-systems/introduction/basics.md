# Basics: introduction

[Back](README.md)

## Why

Learn introduction by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: one HTTP request, three network hops

```text
client → CDN (10 ms) → API (5 ms compute) → DB (3 ms)
total ≈ 18 ms p50
```

Now the API↔DB link has a transient blip: RTT 50 ms on 10% of calls. The request p50 stays 18 ms; the p90 becomes 18 + 40 = 58 ms; p99 can be 18 + 200 = 218 ms. The tail is all network.

Retry without an idempotency key: client times out at 500 ms, retries, but the first request actually completed at 480 ms. Result: two charges for one payment. Adding `X-Idempotency-Key` makes the second request a no-op.

Scaled: 10,000 requests/second with 1% transient network errors. Without dedup: 100 duplicate business operations/second. With dedup: 100 no-ops, 0 duplicates.
