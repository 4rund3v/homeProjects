# Basics: hyperloglog

[Back](README.md)

## Why

Learn hyperloglog by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: daily unique visitors

```text
m = 4,096 registers (2^12), 6-bit each → 3 KB
std error ≈ 1.04 / √4,096 = 1.04/64 ≈ 1.6%
```

At 1.6% standard error, 95% of estimates land within ±3.2% of the true count. For 10 million unique visitors/day, that is ±320,000. If the business requirement is "±1%", bump to `m = 16,384` (12 KB) → error 0.81% → ±81,000.

Register math: each value's hash uses the first 12 bits to pick a register and the remaining 52 bits to count leading zeros. A register's value is the maximum leading-zero count seen. At 10 million inserts, expected max per register ≈ `log_2(4,096 × 10,000,000 / 2^52) + 1 ≈ 5–6`. The estimate inverts the harmonic mean of `2^register` values.

Small-range correction: if ~15% of registers are still 0, the harmonic-mean estimator over-counts. The correction `n_hat ≈ m/ln(m/z)` (where z = zero registers) applies. At 10M inserts this regime is irrelevant; at <100 inserts it is the dominant error source.

Merge: 100 shards × 3 KB = 300 KB of registers to ship vs 10M × 8 bytes = 80 MB of raw IDs. Merge is `O(m)` element-wise max; the result is the union's cardinality estimate, not a per-shard breakdown.
