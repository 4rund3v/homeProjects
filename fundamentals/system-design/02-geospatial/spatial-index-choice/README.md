# Choosing a spatial index

[Back](../../README.md)

## Why

The "best" spatial index depends on query shape, data distribution, update rate, hardware, and storage. A global fleet tracker and a city-scale delivery system need different choices.

## How

Match the index to the dominant query:

```text
query type → cell/cell-cover semantics → cost → alternative
```

For each candidate, measure candidate count, exact-filter work, index size, write cost, sharding behavior, and failure isolation.

## Under the hood

| Index | Strength | Weakness |
|---|---|---|
| Geohash | simple, string-key compatible | rectangle cells, boundary effects |
| Quadtree | density-adaptive | distributed split coordination |
| H3 | hex neighborhoods, hierarchy | pentagon/boundary complexity |
| S2 | global coverage, stable cells | implementation complexity |
| Hilbert key | 1D KV locality | range fragmentation across recursion |
| R-tree/STRtree | exact geometry and complex shapes | less distributed-friendly |

For a distributed store, the partition key matters more than the fancy data structure. A hot city can become one hot shard no matter what in-cell index is used.

## Production decision process

1. Define radius, polygons, update cadence, cardinality, and SLOs.
2. Pick a resolution level for the dominant query.
3. Prototype with 1% sampled data and 100% query mix.
4. Measure candidate set and exact-filter work.
5. Stress hot regions and boundary cases.
6. Add a reconciliation path.

## Lab

Run the same query mix against geohash, H3, and S2. Report candidate count, p95 latency, index size, and failure blast radius.

## Worked examples

**Situation: 1M points, 3 km radius query, 100 points/km².**
```text
circle area = π × 3² ≈ 28.3 km²
expected hits = 28.3 × 100 = 2,830

geohash p6 (1.2×0.6 km):  ~5-7 cells, ~20% overhead
H3 res 8 (0.37 km²):      ~10 cells, ~50% overhead
S2 level 15 (~4.8 km):    ~3-4 cells, ~10% overhead
```
At 5,000 queries/second:
- geohash p6: 2,830 × 1.2 = 3,396 candidates × 10 ns = 34 µs → 170 ms/s CPU
- H3 res 8: 2,830 × 1.5 = 4,245 × 10 ns = 42 µs → 210 ms/s CPU
- S2 level 15: 2,830 × 1.1 = 3,113 × 10 ns = 31 µs → 155 ms/s CPU

S2 is the best per-query CPU. But S2 index size is ~40% larger than geohash p6 for the same 1M points. The decision is index storage vs per-query CPU. At 5,000 qps, the CPU savings (155 vs 170 ms/s) save 15 ms/s of CPU — the storage cost likely dominates.

```text
geohash:  170 ms/s CPU, smallest index
S2:       155 ms/s CPU, +40% index size
H3:       210 ms/s CPU, medium index
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
