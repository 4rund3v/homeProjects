# Basics: h3

[Back](README.md)

## Why

Learn h3 by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: H3 resolution → cell size

H3 resolution 7 ≈ 0.37 km² cells; resolution 9 ≈ 0.03 km².

```text
delivery zone = 1 km radius circle, area ≈ 3.14 km²
```

At resolution 7, a 1 km circle covers roughly `3.14 / 0.37 ≈ 8.5` hex cells. At resolution 9, it covers `3.14 / 0.03 ≈ 105` cells. A k-ring of 1 around the center cell at resolution 7 adds ~6 more cells, giving ~14 candidate cells; at resolution 9, ~300 candidates.

Pentagon distortion: near the 12 H3 pentagon centers (roughly one per continent), cells deviate from regular hexagons. A query that assumes "6 equidistant neighbors" must test the actual covering, not the ideal k-ring, within ~500 km of a pentagon.

Storage: for 10 million delivery points, resolution 7 uses ~1.25× the distinct cell count of resolution 8 (cells cover more area), so the index is smaller but candidates per query are 4–16× more.
