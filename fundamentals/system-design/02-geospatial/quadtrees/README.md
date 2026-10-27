# Quadtrees

[Back](../../README.md)

## Why

A quadtree adapts spatial resolution to data distribution. Dense regions get more subdivisions; empty regions stay coarse.

## How

Start with a world rectangle. Split a node into four equal quadrants when it exceeds a capacity threshold.

```text
             world
          /    |    \
       NW      NE
       SW      SE
```

A range query descends only into nodes whose rectangles intersect the query region.

## Under the hood

Each node stores a bounding box, child pointers, and either points or references to deeper nodes. In a balanced distribution, lookup approaches `O(log n)` depth. Skewed data can create deep paths; cap depth and handle a full leaf explicitly.

For distributed systems, tree nodes require ownership and split coordination. A hot city can become one hot subtree; split it or shard by another key.

## Production use cases

Dynamic point indexes, collision detection, tile generation, and spatial clustering.

## Trade-offs

| Quadtrees | Alternative grid |
|---|---|
| adapts to density | predictable cell lookup |
| variable depth | easier sharding |
| split/merge complexity | more false positives |

## Lab

Insert uniform points, then a dense cluster. Plot node depth and candidate count. Vary capacity and maximum depth.

## Worked examples

**Situation: 1M points, 8,192/leaf capacity, uniform distribution.**
```text
4^d × 8,192 ≥ 1,000,000
d = log4(122) ≈ 3.5 → 4 levels
max nodes = 4^4 = 256
```
A 10 km range query at world scale touches ~1 node. At city scale (1/100,000 of world area), it touches ~4-8 nodes. The query cost is O(depth × nodes_visited) ≈ O(4 × 8) = O(32) operations.

City vs rural 100:1 skew: the city subtree reaches 8,192/leaf in ~2 levels (16,384 points in the city cell). The rural subtree stays at depth 1 (163 points per rural cell). The hot city subtree is 2× deeper → its range queries are 2× slower.

```text
depth 1: 4 cells × 250,000 points
depth 2: 16 cells × 62,500 points
depth 3: 64 cells × 15,625 points
depth 4: 256 cells × 3,906 points  ← near capacity
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
