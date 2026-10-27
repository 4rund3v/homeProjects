# Elasticsearch architecture essentials

[Back](../../README.md)

## Why

A production search cluster must scale to large corpora, stay available under shard loss, and absorb write bursts. Elasticsearch's architecture is built around sharding and a near-real-time indexing path.

## How

```text
request → coordinating node
  → routes to primary shard
  → primary acknowledges after commit
  → async replica sync
read → replica for load spreading
```

Each index is split into **shards**, each with one primary and one or more replicas.

## Under the hood

The indexing path is asynchronous:

1. A document arrives at the coordinating node.
2. The routing key selects the primary shard.
3. The primary writes to a **translog** (durable log) and to an in-memory **buffer**.
4. When the buffer flushes, it becomes a new **segment** on disk and is searchable.
5. Until refresh (or the flush that triggers it), the document is not visible — hence "near real-time."
6. Replicas receive the write and apply it.

The **refresh interval** is the knob that trades write cost against read freshness. The default is around 1 second.

## Production use cases

Log search, product search, document search, and faceted navigation.

## Trade-offs and tuning

| Knob | Effect |
|---|---|
| Refresh interval | small = fresher reads, more segments, more load |
| Shards per node | many small shards = high memory and IO |
| Replicas | availability and read scale, at storage cost |
| Mappings | dynamic mapping can balloon; pin fields |
| Bulk size | too small = overhead; too large = timeout and big transactions |

A shard is too large when it cannot fit in a node's memory for fast operations. Aim for a shard size that leaves headroom.

## Observability

Cluster health, shard allocation, JVM heap usage, segment counts, refresh latency, and index vs search node load.

## Lab

Index a large corpus with a fast refresh interval and a slow one. Measure indexing throughput and read freshness under each.

## Worked examples

**Situation: 100 GB index, 5 shards, 3 search nodes, 30 GB heap/node.**
```text
per-shard = 100/5 = 20 GB
hot working set = 60 GB per node (3 shards × 20 GB)
page cache = 64 GB RAM → 4 GB cold
```
A cold-segment page miss: p99 jumps from 50 ms to 500 ms. The 4 GB cold fraction is 4/60 = 6.7% of the working set. 6.7% of queries hit disk → p99 ≈ 500 ms. To keep p99 < 50 ms, all 60 GB must be hot → 64 GB RAM is just barely enough.

Refresh interval: 1 s → 86,400 segments/day → merge CPU ≈ 15% of a core. 30 s → 2,880 segments/day → merge CPU ≈ 0.5% of a core. Set refresh to match freshness SLO.

Bulk size: 5,000 docs × 30 KB = 150 MB/bulk. 100 bulks/second = 15 GB/second of indexing. A 4-core node sustains ~3 GB/second of disk writes. 100 rps × 150 MB = 15 GB/s → 5× over. Reduce to 50 rps → 7.5 GB/s, still 2.5× over. 30 rps → 4.5 GB/s, inside the 3 GB/s ceiling with 1.5× headroom.

```text
cold: 6.7% of queries → p99 = 500 ms
refresh 1s: merge = 15% core
bulk 5000 × 150 MB @ 100 rps = 15 GB/s → 5× over
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
