# Geohash

[Back](../../README.md)

## Why

Geohash turns a point into a string whose prefix represents a rectangular region. Prefixes make ordinary key-value or B-tree indexes useful for coarse spatial lookup.

## How

Repeatedly bisect longitude and latitude intervals. Each bit selects a lower or upper half. Interleave the longitude and latitude bits, then encode groups of bits as characters.

```text
world → hemisphere → quadrant → smaller rectangle
```

A nearby query chooses a precision and searches the cell plus neighboring cells, because two close points can fall on opposite sides of a cell boundary.

## Under the hood

A geohash is not a distance metric. A prefix is a rectangle, and rectangle width depends on latitude and precision. At the equator, a fixed number of longitude bits covers a wider physical distance than at high latitude.

A common index is `(geohash_prefix, entity_id)`. Query: compute the covering prefixes, issue one lookup per prefix, then exact-filter by distance. Too-short prefixes create many candidates; too-long prefixes create too many neighbor lookups.

## Production use cases

Simple nearby search, sharded location keys, cache keys for map data, and coarse geofencing.

## Failure modes

- Checking only one prefix misses boundary results.
- Treating string order as physical distance produces false assumptions.
- Using one precision globally creates poor performance across scales.

## Lab

Index 1 million synthetic points by 5-, 6-, and 7-character geohash. Compare candidate count and neighbor-query count for a 1 km radius at several latitudes.

## Worked examples

**Situation: 1 km radius, geohash precision 6.**
```text
precision 6 cell = 1.2 km × 0.6 km
circle area       = π × 1² ≈ 3.14 km²
cells covered     = 3.14 / 0.72 ≈ 4.4 → 5 cell lookups
```
At 100 points/km²: 5 cells × 72 points/cell = 360 candidates. Exact filter keeps ~314. False-positive overhead = (360-314)/314 = 15%.

At 10,000 points/km²: candidates = 5 × 7,200 = 36,000. Exact filter keeps ~31,400. The index is now useless — the cell is too coarse. Drop to precision 7 (0.3 × 0.15 km): 9 cells × 4.5 points = 40 candidates. False-positive rate drops to ~10%.

```text
precision 6: 5 lookups, 360 candidates, 15% FP
precision 7: 9 lookups, 40 candidates, 10% FP
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
