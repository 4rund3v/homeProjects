# HyperLogLog

[Back](../../README.md)

## Why

Distinct counting needs a set, and a set of billions of identifiers is expensive. HyperLogLog estimates cardinality with a fixed number of small registers.

## How

```text
hash(value) → register index from prefix
            → rank = leading-zero count of remaining bits
register[index] = max(register[index], rank)
estimate from harmonic mean of 2^register values
```

## Under the hood

With `m` registers, the standard error is approximately `1.04 / sqrt(m)`. More registers lower error but use more memory. Small-cardinality corrections improve behavior when many registers are still zero; large-range corrections handle hash-space saturation.

HLL is mergeable: take the element-wise maximum of registers across shards. It cannot recover the actual members, and it cannot answer membership queries.

Hash quality matters. Biased or inconsistent hashes bias the estimate. Hash version belongs in the data contract.

## Production use cases

Unique users, distinct search queries, unique IP estimates, and cardinality aggregations over large streams.

## Failure modes

- Different hash functions make merged sketches invalid.
- Register resets misalign time windows.
- Approximate distinct counts are treated as exact billing numbers.

## Lab

Count distinct IDs from 1 million to 1 billion using exact sets and HLL. Compare memory and relative error. Merge four per-shard sketches and compare with a single global sketch.

## Worked examples

**Situation: 10M daily unique visitors, ±1% error target.**
```text
m = 4,096 (2^12) registers, 6-bit each → 3 KB
std error = 1.04 / √4,096 = 1.6% → ±3.2% at 95% CI
on 10M: ±320,000
```
To get ±1%: `m = (1.04/0.01)² = 108,164` → next power of 2 = 131,072 (12 KB).

Register math: 10M inserts. Each register's value is the max leading-zero count. Expected max ≈ `log2(4,096 × 10,000,000 / 2^52) + 1 ≈ 5-6`. The estimate inverts the harmonic mean of `2^register`.

Small-range correction: at < 100 inserts, ~15% of registers are still 0. The harmonic-mean estimator over-counts. The correction `n_hat ≈ m/ln(m/z)` applies. At 10M inserts, zero registers ≈ 0 → correction is irrelevant.

Merge: 100 shards × 3 KB = 300 KB vs 80 MB of raw IDs. Merge is O(m) = O(4,096) element-wise max. The result is the union's cardinality, not per-shard breakdown.

```text
4,096 regs: 3 KB, 1.6% error, ±320K on 10M
131,072:    12 KB, 0.81% error, ±81K on 10M
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
