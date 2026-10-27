# Basics: quadtrees

[Back](README.md)

## Why

Learn quadtrees by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: 1 million points, 10,000 depth capacity

```text
world → split on 8,192-point threshold
depth 1: 4 nodes
depth 2: 16 nodes
...
depth d: up to 4^d nodes
```

If points are uniform across the whole world, depth needed to hit 8,192 points per leaf is:

```text
4^d × 8,192 ≥ 1,000,000
d ≈ log4(122) ≈ 3.5 → 4 levels
```

A 100:1 city vs rural skew means the city reaches 8,192 in ~2 levels while rural stays at depth 1. A dense hot spot (say 500,000 points in one area) forces that subtree to ~5 levels; a hot spot at one leaf becomes a distributed partition key.

Range query visits: a 10 km query at city scale touches ~4–8 nodes; at world scale, 1 node.
