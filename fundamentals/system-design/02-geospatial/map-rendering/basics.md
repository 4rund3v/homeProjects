# Basics: map rendering

[Back](README.md)

## Why

Learn map rendering by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: tile count and payload

Web-mercator zoom 8 covers a 256 × 256 tile world: `256 × 256 = 65,536` tiles. A user's visible viewport at 1080p shows roughly a `6 × 4 = 24`-tile region, plus 1 ring of neighbors = `8 × 6 = 48` tiles.

```text
vector tile, ~10 KB each, 90% CDN hit
p50 bytes = 48 × 10 KB × 0.9 + 48 × 10 KB × 0.1 × 3 (origin)
           = 432 KB + 144 KB = 576 KB per viewport
```

If you pre-render raster at 512 × 512 px, each tile is ~200 KB; one viewport is `48 × 200 KB = 9.6 MB`. Vector wins on bandwidth by ~17×. The cost shifts to the client's decode step and to the renderer's geometry-simplification step at build time.

Zoom 12 covers a 1024 × 1024 tile world: `1,048,576` tiles. A 6 × 4 viewport is still 24 tiles, but the source dataset grows. If one source build produces 1 million tiles at 50 ms each, build time is `1,000,000 × 0.05 s / workers` — 13.9 hours single-threaded, ~1.7 hours with 8 workers.
