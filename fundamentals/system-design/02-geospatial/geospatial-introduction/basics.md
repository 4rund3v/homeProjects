# Basics: geospatial introduction

[Back](README.md)

## Why

Learn geospatial introduction by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: nearby restaurants, 5 km radius

```text
city density = 2,000 restaurants per 100 km²
query        = 5 km circle, area ≈ 78.5 km²
expected     = 78.5 × 20 = 1,570 candidates
```

A naive scan of the whole city (say 200,000 restaurants) is O(n). A geohash index at precision 5 (~5 km cells) reduces it to ~4 lookups × ~200 points × exact haversine = fast.

If the city holds 200,000 points and a query returns 1,570, the index must have at least `200,000 / 1,570 ≈ 127` effective buckets per query region. Choosing the wrong precision (say precision 3, ~45 km cells) makes one cell hold ~80,000 points — the index does nothing.

The three-stage pipeline costs:
1. Cell lookup: O(1) per cell, ~4 cells
2. Candidate materialization: ~1,570 rows
3. Exact filter + sort: O(1,570 log 1,570)
