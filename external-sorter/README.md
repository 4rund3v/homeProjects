# external-sorter

**Goal:** Build a production-grade external sorting and K-way merge engine CLI in Go that sorts massive disk-bound files under strict memory limits using divide-and-conquer and min-heap algorithms.

**Scope:** Memory-bounded record chunking, in-memory run sorting, sorted run spill to temporary disk files, min-heap priority queue K-way merger, hierarchical multi-pass merge tree for open file descriptor limits, divide-and-conquer inversion counter for disorder scoring, disk-based sparse index builder with binary search range scans, deterministic synthetic log generator, CLI subcommands (`sort`, `merge`, `disorder-score`, `query`).

**Out of scope:** Distributed/multi-node cluster sorting (e.g., full MapReduce shuffle phase), custom binary serialization protocols (operates on standard delimiter-separated records/lines), GUI or web interfaces, disk compression for intermediate temporary runs.

**Learning focus:** Divide-and-conquer problem decomposition for data exceeding physical RAM; min-heap priority queue mechanics (`container/heap.Interface`) for streaming K-way merges; external sorting architecture and multi-pass fan-in limits; inversion counting via modified merge sort; disk-based binary search using sparse offset indexing; strict memory bounding and GC overhead accounting in Go; articulating FAANG L5 algorithmic scalability tradeoffs.

**Depends on:** [`go-fundamentals`](../go-fundamentals/README.md)

## Milestones
- [ ] Milestone 1 — In-memory chunk sorter & run generator: strictly bounded buffer, in-memory chunk sorting, and spill of sorted temporary runs to disk.
- [ ] Milestone 2 — Min-heap K-way merger: priority queue over K open run files with streaming output and constant memory overhead.
- [ ] Milestone 3 — End-to-end external sort: hierarchical multi-pass merge tree when run count exceeds file descriptor limits, signal handling, and clean scratch disk lifecycle.
- [ ] Milestone 4 — Divide-and-conquer inversion counter & binary search indexing: measure presortedness via inversion counting and implement sparse index binary search range queries.
