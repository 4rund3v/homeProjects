# Basics: s2

[Back](README.md)

## Why

Learn s2 by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: S2 cell level → physical size

S2 level 16 ≈ 1 km × 1 km; level 18 ≈ 250 m × 250 m.

```text
geofence = a polygon covering a 5 × 5 km district
```

At level 16 the district needs ~25 cells. At level 18, ~400 cells. A `getCovering(polygon, level)` call returns a bounded set of cells; you then read every point tagged with those cells and check point-in-polygon exactly.

Global scale: a fleet of 1 million vehicles, one point per vehicle, level 16. The index has at most 1 million distinct cell keys. A "vehicles in district" query touches ~25 keys → ~25,000 candidates → exact filter. That is 40× fewer candidates than a full-table scan.

The antimeridian case: a 1,000 km × 1,000 km square centered on longitude 180° splits into two rectangles in planar storage. In S2 it is one covering; you cannot reproduce that locality with a 1D planar key.
