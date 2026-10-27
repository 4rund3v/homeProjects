# Basics: elasticsearch

[Back](README.md)

## Why

Learn elasticsearch by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: shard size math

```text
index size = 100 GB
shards     = 5 primary + 5 replicas
per-shard  = 100 GB / 5 = 20 GB
heap       = 30 GB per node, 3 search nodes
```

A search node holds at most `20 GB × 5 = 100 GB` of index data. Lucene's Lucene-on-heap segment metadata is a fraction of that, but the hot segment files must fit in OS page cache or searches go to disk. At 100 GB index, a node with 64 GB RAM and a 20 GB shard set can keep ~60 GB of the working set in page cache. Queries that touch a cold segment page miss to disk: p99 jumps from ~50 ms to ~500 ms.

Refresh interval trade-off:
```text
refresh = 1 s  → index is searchable in ~1 s
           → ~1 segment/sec/shard, ~86,400 segments/day → merge pressure
refresh = 30 s → 288 segments/day, far less merge CPU
           → read freshness SLO = 30 s
```
Set `refresh_interval` to match your freshness SLO; don't run 1 s on a low-update index.

Bulk size: 5,000 docs/bulk with 30 KB avg doc → 150 MB/bulk. A 150 MB bulk on a 3-node cluster with 100 ms RTT to the primary is 150 ms per round trip. 100 bulks/second to one node = 10,000 MB/s of indexing; the node's disk write headroom must exceed that.
