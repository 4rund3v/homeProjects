# Basics: geohash

[Back](README.md)

## Why

Learn geohash by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: geohash cell size vs query radius

Geohash character 5 covers ~4.9 km × 4.9 km at the equator; character 6 ≈ 1.2 km × 0.6 km.

```text
query: 1 km radius
precision = 6 chars
cell      = 1.2 × 0.6 km
```

A 1 km circle at the cell boundary can intersect up to 4 cells (the center cell + 3 neighbors in a worst-case alignment, typically 4–5 lookups). Each lookup returns every point in that cell; the exact-distance filter trims the candidates outside 1 km.

Math: if a 1 km circle has area π km² ≈ 3.14 km² and each 1.2 × 0.6 cell holds ~0.72 km², the circle spans ~4.4 cells. At 100 points per km², a cell has ~72 points; 5 cells × 72 = 360 candidates; the exact filter keeps ≈ 314 (circle area × density).

Scaled: at 10,000 points/km², candidates jump to ~3,600; dropping to precision 7 (cell ~0.3 × 0.15 km) reduces each cell to ~4.5 points, 9 cells × 4.5 = 40 candidates. The query trades storage for precision.
