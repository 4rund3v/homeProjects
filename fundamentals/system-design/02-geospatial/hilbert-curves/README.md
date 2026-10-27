# Space-filling curves and Hilbert curves

[Back](../../README.md)

## Why

A key-value store has one-dimensional ordering. A space-filling curve maps two-dimensional coordinates to one dimension while trying to keep nearby points near each other in key order.

## How

A Hilbert curve recursively visits every quadrant, rotating and reflecting the traversal so adjacent curve positions tend to share spatial locality.

```text
2D cells ──Hilbert order──> 1D key ranges
```

A range query becomes several 1D intervals. Read those intervals, then exact-filter results.

## Under the hood

Hilbert locality is better than simple row-major order for many workloads because it minimizes long jumps between adjacent cells. It does not preserve every neighborhood: nearby points can still map far apart, especially across recursion boundaries.

A practical index stores `(hilbert_key, entity_id)`. Query planning chooses a curve resolution and decomposes the geometry into ranges. More resolution improves precision but creates more ranges.

## Production use cases

LSM/B-tree spatial indexes, distributed partition keys, range scans, and cache locality.

## Lab

Map a grid with row-major, Morton/Z-order, and Hilbert keys. For random circular queries, measure the number and total length of 1D ranges required.

## Worked examples

**Situation: 1024×1024 grid, 10×10 window query, 1M points.**
```text
row-major: 10 separate row segments × 1024 cells wide = 10,240 cells scanned
           useful cells = 100 → 99% waste
Hilbert:   ~2 contiguous ranges × 200 cells = 400 cells scanned
           useful cells = 100 → 75% waste
```
At 16 bytes per point: row-major reads 160 KB, Hilbert reads 6.4 KB. I/O is the bottleneck. The 25× reduction in I/O is the whole reason the curve is used.

Scaled: 4096×4096 grid (16M points). A 10×10 window in row-major scans 10 × 4096 = 40,960 cells. Hilbert scans ~400. I/O reduction scales with grid width, not point count.

```text
row-major: 10 ranges × 1024 = 10,240 cells → 160 KB I/O
Hilbert:   2 ranges × 200   = 400 cells   → 6.4 KB I/O
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
