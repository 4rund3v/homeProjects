# Learn 01: map rendering mechanism

[Back](../README.md)

## Why

The first lesson for map rendering is mechanism, not vocabulary. A named pattern is useful only after its failure mode is visible.

## How

Draw the smallest system that exhibits the problem. Run one control case, then vary one input: concurrency, data size, failure rate, or freshness requirement.

## Under the hood

Trace one operation through memory, network, storage, and recovery. Write down every durable boundary and every point where a duplicate or stale result can appear.

## Exercise

Implement or simulate the smallest example from the topic README. Record workload, expected invariant, observed result, and the change that makes the invariant hold.

## Senior checkpoint

- Which assumption is load-bearing?
- What is the saturation knee?
- What is the safe recovery action?

## Worked numbers

**Exercise: tile build + serve.**
- Zoom 8, vector tiles, 1080p viewport
- Measure: tile count, payload size, CDN hit ratio, build time
- Expected: 48 tiles, 576 KB, 90% CDN hit, 6.5 h build (8 workers)

```text
vector:  576 KB
raster:  9.6 MB
build:   6.5 h
```
