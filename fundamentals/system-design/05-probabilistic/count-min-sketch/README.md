# Count-Min Sketch

[Back](../../README.md)

## Why

Counting every key exactly requires memory proportional to the key space. Count-Min Sketch estimates item frequency with fixed memory, useful for heavy hitters and rate observations.

## How

```text
add(key, c): increment one counter in each hash row
estimate(key): return the minimum counter across rows
```

The minimum matters because collisions only add counts. The estimate is therefore an upper bound.

## Under the hood

With width `w` and depth `d`, memory is `w × d` counters. For error `epsilon` and failure probability `delta`, common sizing is:

```text
w ≈ e / epsilon
 d ≈ ln(1 / delta)
```

A sketch is mergeable by element-wise addition when dimensions and hash seeds match. Counter width determines overflow behavior; saturating counters avoid wraparound but bias large estimates.

## Production use cases

Top queries, API abuse detection, per-key traffic estimation, and streaming frequency analytics.

## Failure modes

- Hash collision causes overestimation.
- Counter overflow corrupts estimates.
- Resetting one shard at a different time makes merged windows meaningless.

## Lab

Stream a Zipf-distributed workload. Compare exact counts to CMS for different widths. Plot error for heavy and rare keys.

## Worked examples

**Situation: top-IP abuse detection, 10M distinct IPs, 100M events/day.**
```text
ε = 0.01, δ = 0.01
width = e/ε = 272, depth = ln(1/δ) = 5
memory = 272 × 5 × 8 = 10.9 KB
```
Exact map: 10M × 8 = 80 MB. CMS: 10.9 KB → 7,300× smaller.

Collision error: a heavy key (1M hits) inflates a rare key's estimate by ~`1,000,000 × 5/272 ≈ 18,000`. With 100 heavy keys, the top heavy key's estimate ≈ `50,000 + 99 × 50,000/272 ≈ 68,000` vs true 50,000. The top-10 result is correct in ordering; the absolute counts are inflated.

Counter overflow: 32-bit counters overflow at 4.3B. At 100M events/day, a hot key at 1% of traffic sees 3.6M/day → safe for 1,000 days. At 10%, 36M/day → safe for 118 days. Use 64-bit counters or saturating increment.

Merge: 100 shards × 10.9 KB = 1.09 MB to ship vs 80 MB of raw counts. Merge is O(width × depth) = O(1,360) element-wise max.

```text
exact: 80 MB
CMS:   10.9 KB, 7,300× smaller
merge: 1.09 MB from 100 shards
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
