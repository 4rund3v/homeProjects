# Geospatial search introduction

[Back](../../README.md)

## Why

A B-tree over latitude alone cannot efficiently answer "nearest restaurants within 2 km". Longitude and latitude interact, and the Earth is curved. A spatial index reduces a two-dimensional region to a small set of candidate cells.

## How

```text
point → cell covering → candidate records → exact distance/geometry filter → ranked results
```

Never trust cell membership alone for correctness. A cell covering is a coarse filter; exact haversine or geodesic distance decides whether a result is inside the requested radius.

## Under the hood

The design has three stages:

1. **Encode** coordinates into a hierarchical cell ID.
2. **Query neighboring cells** that overlap the search region.
3. **Refine candidates** by exact geometry and sort by distance or business rank.

Index precision controls the candidate set. Finer cells reduce false positives but require more cells at large radii and increase index/storage overhead.

## Production use cases

Nearby search, geofencing, delivery zones, ride matching, map tiles, and location analytics.

## Lab

Generate clustered and uniform points. Query increasing radii. Measure cells visited, candidate count, exact-distance checks, p95 latency, and false-positive ratio.

## Worked examples

**Situation: 2,000 restaurants/100 km², 5 km query radius.**
```text
query area    = π × 5² ≈ 78.5 km²
expected hits = 78.5 × 20 = 1,570
naive scan    = 200,000 restaurants (whole city)
geohash p5    = ~4 cells × 200 points = 800 candidates
```
The index returns 800 candidates; the exact haversine filter keeps ~1,570 (the circle overlaps cell boundaries, so some candidates are outside the radius). CPU: 1,570 × 10 ns haversine = 15.7 µs. Naive scan: 200,000 × 10 ns = 2 ms — 130× slower.

```mermaid
flowchart LR
  Q[query: lat,lon,r=5km] --> Cells[4 geohash cells]
  Cells --> Cand[800 candidates]
  Cand --> Dist[haversine filter]
  Dist --> Result[1,570 in-radius]
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
