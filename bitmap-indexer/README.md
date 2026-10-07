# bitmap-indexer

**Goal:** Build a high-performance attribute search and fast set-filtering engine CLI in Go that indexes millions of records using 64-bit word-level bitmaps and Kirsch-Mitzenmacher Bloom filters.

**Scope:** Compact `[]uint64` bitset with word-level bitwise operations (AND, OR, XOR, NOT), popcount cardinality estimation, bit isolation (`x & -x`) iterator, boolean query parser and AST evaluator, double-hashed Bloom filter with optimal M/K sizing, binary index persistence, CLI subcommands (`index`, `query`, `bloom-create`, `bloom-check`, `bench`), benchmarks vs. naive record scanning.

**Out of scope:** Compressed roaring bitmaps (covered conceptually in notes), distributed indexing, real-time mutable streaming ingestion, SQL query dialect, HTTP server API.

**Learning focus:** Bit manipulation primitives and word-level parallelism (64 elements per CPU cycle); popcount hardware instructions; low-bit isolation (`x & -x`) and bit clearing (`x & (x - 1)`); Kirsch-Mitzenmacher double hashing; probabilistic data structure sizing and empirical false-positive analysis; dense bitmap vs. sparse posting list tradeoffs for L5 system design.

**Depends on:** [`go-fundamentals`](../go-fundamentals/README.md)

## Milestones
- [ ] Milestone 1 — Bitset core & bitwise primitives: `[]uint64` bitset with Set, Clear, Test, Popcount, word-level AND/OR/XOR/NOT, and lowest-bit iterator (`x & -x`).
- [ ] Milestone 2 — Boolean query evaluation engine: Lexer, recursive-descent parser, and AST evaluator compiling boolean expressions into bitwise operations across attribute bitsets.
- [ ] Milestone 3 — Bloom filter from scratch: Kirsch-Mitzenmacher double-hashing (generating K hashes from Murmur3/FNV-1a), optimal bit-array sizing (M, K), and membership checking.
- [ ] Milestone 4 — Benchmark suite & analysis: Compare bitmap query throughput against naive slice and map scans; empirically measure Bloom filter false-positive rate vs. theoretical formula; document Roaring Bitmap tradeoffs.
