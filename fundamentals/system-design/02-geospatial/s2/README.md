# Google S2 library concepts

[Back](../../README.md)

## Why

Global geospatial systems need cells that cover a sphere, support hierarchy, and provide stable locality across the whole Earth. S2 uses a projection of the sphere onto cube faces and indexes cells hierarchically.

## How

```text
latitude/longitude → cube face → Hilbert position → S2 cell ID
```

A cell ID identifies a face, position along a Hilbert curve, and level. Parent and child cells are derivable from the ID. Region coverings approximate arbitrary polygons with a bounded set of cells.

## Under the hood

S2's hierarchy gives a total order for storage and a compact representation for coverings. A region query asks for a covering at a level range, then checks candidate geometry exactly. Face boundaries and spherical geometry are first-class; planar assumptions are unsafe for global data.

## Production use cases

Global proximity, geofences crossing the antimeridian, map tiling, and distributed spatial partitioning.

## Trade-offs

S2 is powerful for spherical coverage and hierarchy. It has more conceptual and implementation complexity than a simple geohash. Choose it when global geometry and stable coverings matter.

## Lab

Cover a polygon that crosses the antimeridian. Compare a planar bounding box with an S2 covering, then exact-filter candidates.

## Worked examples

**Situation: 1M vehicles, S2 level 16, geofence query.**
```text
S2 level 16 cell ≈ 1 km × 1 km
geofence = 5 × 5 km district → ~25 cells
candidates = 25 cells × ~40 vehicles/cell = 1,000
exact filter = point-in-polygon on 1,000
```
Full-table scan = 1M × 10 ns = 10 ms. S2 covering = 25 lookups × 10 ns + 1,000 × 100 ns point-in-polygon = ~100 µs. 100× faster.

Antimeridian: a 1000 km × 1000 km square centered on longitude 180° splits into two rectangles in planar storage. In S2 it is one covering of ~4,000 level-16 cells. The covering API returns a single set of cell IDs — no special-casing needed.

```text
S2 level 16: 25 lookups + 1,000 exact checks ≈ 100 µs
full scan:   1M checks ≈ 10 ms
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
