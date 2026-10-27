# Basics: spatial index choice

[Back](README.md)

## Why

Learn spatial index choice by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: 1 million points, 3 km radius

Query region area = π × 3² ≈ 28.3 km². Assume 100 points/km² uniform → ~2,830 expected candidates.

| Index | Cells visited | Candidate overhead |
|---|---|---|
| Geohash p6 (1.2 × 0.6 km) | ~5–7 | ~20% over |
| H3 res 8 (~0.37 km²) | ~10 | ~50% over |
| S2 level 15 (~4.8 km) | ~3–4 | ~10% over |

The overhead matters because every candidate is a haversine (CPU ~10 ns) and a sort key. 2,830 candidates → ~28 µs distance work; 4,245 (50% overhead) → ~42 µs. At 5,000 queries/second, the difference is 0.22 s/s vs 0.14 s/s CPU.

Scaled: 10× data (10M points), same density. Geohash p6 now returns ~28,000 candidates; the exact filter dominates. Moving to p7 (0.3 × 0.15 km) keeps candidate count in the same band but increases the index size ~4×. The decision is index size vs per-query CPU.
