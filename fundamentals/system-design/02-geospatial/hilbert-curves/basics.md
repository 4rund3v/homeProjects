# Basics: hilbert curves

[Back](README.md)

## Why

Learn hilbert curves by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: row-major vs Hilbert key ranges

A 1024 × 1024 grid has 1,048,576 cells. A 10 × 10 query window is 100 cells.

```text
row-major: the 10 columns of the window wrap across 10 separate row segments
           → ~10 one-dimensional ranges, each ~1024 cells wide
Hilbert:   most 10 × 10 windows are ~1–3 contiguous ranges
```

In row-major, total cells scanned ≈ 10 × 1024 = 10,240; useful cells are 100 → 99% waste.
In Hilbert, cells scanned ≈ 100–400 → 75–99% hit rate.

At 1 million points, a point-lookup query using the Hilbert key reads 100–400 × 16 bytes ≈ 1.6–6.4 KB; row-major reads 160 KB. I/O is the bottleneck; that gap is the whole reason the curve is used.
