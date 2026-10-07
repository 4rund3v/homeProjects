# Data Compressor

**Goal:** Compare compression formats using reproducible measurements.

**Scope:** gzip plus selected formats such as Zstandard and Snappy; Parquet as a columnar storage format, not a drop-in compression codec; round-trip checks, benchmarks, profiling.

**Out of scope:** Distributed compression and cloud storage.

**Learning focus:** Format tradeoffs, streaming IO, memory use, benchmark design, profiling.

**Depends on:** `go-fundamentals`.

## Milestones
- [ ] Define representative datasets and correctness checks.
- [ ] Implement streaming round trips for gzip and one additional codec.
- [ ] Benchmark throughput, output size, and allocations on the same inputs.
- [ ] Separately explore Parquet encoding/compression and record when it fits.
