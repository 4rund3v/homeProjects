# Probabilistic data structures overview

[Back](../../README.md)

## Why

Exact sets, frequency maps, and cardinality sets become too large when traffic and key space grow. Probabilistic structures answer approximate questions with a small, fixed memory budget.

## How

| Structure | Answers | Error direction |
|---|---|---|
| Bloom filter | might contain key? | false positives, no false negatives (if used correctly) |
| Count-Min Sketch | approximate frequency | overestimate, no underestimate |
| HyperLogLog | approximate distinct count | statistical estimate |

The application must use the guarantee correctly. A Bloom positive requires an authoritative lookup; a negative can often skip one. A Count-Min estimate is an upper bound. HyperLogLog is not a membership set.

## Under the hood

All three use hashes:

- Bloom: bit array + multiple positions.
- CMS: rows of counters; each row hashes the key to one counter.
- HLL: hash prefix selects a register; remaining bits determine a leading-zero rank.

They are mergeable when built with compatible dimensions, hash functions, and parameters. This enables per-shard aggregation without shipping raw events.

## Senior decisions

State acceptable error and cost. Size from workload, not from a default. Define reset windows, version hash functions, and monitor drift against a sampled exact computation.

## Worked examples

**Situation: 100M visitor IDs, unique-visitor counter, 1% error.**
```text
exact set:   100M × 8 bytes = 800 MB
HLL m=4096:  3 KB, 1.6% error → ±320K on 10M/day
Bloom 1%:    100M × 11 bits ≈ 140 MB
CMS ε=0.01:  272 × 5 × 8 bytes ≈ 10.9 KB
```
The decision is which question you need to answer:
- "is this visitor new?" → Bloom (140 MB, 1% FP)
- "how many unique visitors?" → HLL (3 KB, 1.6% error)
- "top 100 IP addresses by hit count?" → CMS (10.9 KB, 1% overestimate)

The exact set is the fallback when the approximate structure gives a positive/near-boundary answer. A Bloom FP means "might be in the set" → check the authoritative store. An HLL estimate means "about N" → use for dashboards, not billing.

```text
HLL: 3 KB for 10M uniques at 1.6% error
CMS: 10.9 KB for top-K at 1% overestimate
exact: 800 MB for zero error
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
