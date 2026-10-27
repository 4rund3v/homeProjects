# H3 hexagonal hierarchical spatial index

[Back](../../README.md)

## Why

Hexagons give each interior cell six equidistant neighbors and avoid the diagonal-neighbor bias of square grids. H3 provides a hierarchy, so systems can aggregate at multiple resolutions.

## How

```text
lat/lon → H3 cell at resolution r → neighboring k-ring → exact geometry filter
```

A cell can be expanded to children for detail or compacted to a parent when all children are present. The same identifier supports bucketing, joins, and rollups.

## Under the hood

H3 projects the sphere onto an icosahedron and indexes hierarchical hexagonal cells, with special handling for pentagons and face boundaries. A cell ID encodes resolution, base cell, and digits for child choices.

The hierarchy makes a useful write/read pattern: store events by cell and resolution, then aggregate nearby cells. Pentagon distortion and boundary behavior must be tested, not assumed away.

## Production use cases

Heat maps, delivery-zone aggregation, privacy-preserving location bucketing, and multi-resolution analytics.

## Trade-offs

Hex cells simplify neighborhood traversal but are not exact circles. Choose resolution based on physical cell size, privacy requirements, and candidate count.

## Lab

Bucket points at three resolutions. Compare storage size, cell counts, neighbor traversal, and exact-distance false positives.

## Worked examples

**Situation: delivery zone, 1 km radius, H3 resolution 7.**
```text
res 7 cell area ≈ 0.37 km²
circle area      = π × 1² ≈ 3.14 km²
cells in circle  = 3.14 / 0.37 ≈ 8.5 → ~10 cells
k-ring 1         = 10 + 6 = 16 candidate cells
```
At 1,000 points/km²: 16 cells × 0.37 km² × 1,000 = ~5,920 candidates. Exact filter keeps ~3,140. At resolution 9 (0.03 km²), the same circle covers ~105 cells; candidates = 105 × 0.03 × 1,000 = 3,150 — similar count, but 105 lookups instead of 16.

Pentagon distortion: within ~500 km of a pentagon center, cells are irregular. A k-ring of 1 around a pentagon cell has 5 neighbors, not 6. The query must test the actual cell geometry, not the ideal hex count.

```text
res 7: 16 lookups, 5,920 candidates, 53% FP
res 9: 105 lookups, 3,150 candidates, 3% FP
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
