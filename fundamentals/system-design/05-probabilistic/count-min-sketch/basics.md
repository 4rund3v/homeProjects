# Basics: count min sketch

[Back](README.md)

## Why

Learn count min sketch by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: top-IP abuse detection

```text
ε = 0.01 (error bound), δ = 0.01 (failure probability)
width  = e/ε = 272 counters
depth  = ln(1/δ) = 4.6 → 5 rows
memory = 272 × 5 × 8 bytes ≈ 10.9 KB
```

5 KB of memory replaces an exact map that would need `distinct IPs × 8 bytes`. For 10 million distinct IPs, that is 80 MB → 10 KB.

Collision error: each of 5 rows hashes a key to one counter. For a rare key, a heavy key (say 1 million hits) collides with it in roughly `1/272` of rows → expected inflation ≈ `1,000,000 × 5/272 ≈ 18,000`. The top-K result is a *heavier-than-true* estimate for rare keys. The heavy key's own estimate is inflated by other heavy keys' collisions; with 100 heavy keys, each of ~50K hits, the top heavy key's estimate ≈ `50,000 + 99 × 50,000/272 ≈ 68,000`.

Counter overflow: if a counter is 32-bit and a heavy key exceeds 4 billion, the counter wraps to 0. Use 64-bit counters or saturating increment. At 100M events/second over 1 hour, a single hot key at 1% of traffic sees 3.6M events — safe at 32-bit. At 10% of traffic, 36M events — still safe. Overflow is a real concern only when one key is >1% of total *and* traffic is >100M events/second.

Scaled: 100 shards, each with its own 10.9 KB sketch, merge by element-wise addition → global view in ~1 MB total.
