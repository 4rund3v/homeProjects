# bitmap-indexer

## What this project exists to solve
Bit manipulation and probabilistic filters are among the most heavily tested algorithmic domains in Google L5 interviews, yet candidates often study them through contrived LeetCode puzzles rather than mechanical sympathy. Real-world storage and search engines—such as Elasticsearch, ClickHouse, and Redis—rely on 64-bit word-level bitsets and Bloom filters to filter millions of records per millisecond without scanning full rows. This project builds a standalone attribute indexing and set-filtering engine from scratch in Go, demonstrating how low-level bit operations (popcount, lowest-bit isolation, word-level bitwise parallelism) and probabilistic data structures solve real-world retrieval challenges at scale.

## Success criteria / completion metrics
- `bitmap-indexer index` ingests 1M records with categorical attributes from CSV and builds columnar bitsets in under 2 seconds.
- `bitmap-indexer query` evaluates multi-attribute boolean queries (AND, OR, XOR, NOT) using 64-bit word-level operations, returning matching document IDs and counts in sub-millisecond latency.
- Bitset iterator extracts matched document IDs using `x & -x` and `bits.TrailingZeros64` without scanning zero bits.
- `bitmap-indexer bloom-create` allocates optimal bit array size $M$ and hash count $K$ for capacity $N$ and target false-positive rate $P$.
- `bitmap-indexer bloom-check` guarantees zero false negatives and measures an empirical false-positive rate within 10% of theoretical target $P$.
- `bitmap-indexer bench` outputs a benchmark table comparing bitset queries against naive slice iterations and hash map lookups, proving a 20x–100x speedup.
- `docs/bitmap-tradeoffs.md` documents L5 tradeoffs between dense bitsets, inverted posting lists, and Roaring Bitmaps.

## Prerequisites and dependencies
- Completed [`go-fundamentals`](../go-fundamentals/README.md): Go syntax, bitwise operators (`&`, `|`, `^`, `&^`), slices, binary I/O with `encoding/binary`, and `testing.B`.
- Familiarity with basic probability and logarithms for Bloom filter sizing formulas ($M = -\frac{N \ln P}{(\ln 2)^2}$, $K = \frac{M}{N} \ln 2$).
- Understanding of CPU word width (64-bit registers), CPU cache locality, and algorithmic time/space complexity.

## Tools, libraries, and runtime
- Go 1.22+ (standard library only; no external indexing or Bloom filter libraries).
- Standard library packages: `math/bits` (hardware popcount / trailing zeros), `hash/fnv`, `encoding/binary`, `bufio`, `os`, `flag`, `testing`.
- `benchstat` (from `golang.org/x/perf`) for statistical comparison of benchmark iterations.

## Learning objectives (skills practiced)
- Implement dense bit vectors packed in `[]uint64` slices with word-aligned bit masking, offset arithmetic, and boundary safety.
- Harness word-level parallelism: evaluate bitwise AND (`&`), OR (`|`), XOR (`^`), and NOT (`&^`) across 64 records per single CPU instruction.
- Apply bit manipulation idioms in production code: `x & -x` (isolate lowest set bit), `x & (x - 1)` (clear lowest set bit), and `bits.TrailingZeros64` for zero-overhead ID extraction.
- Implement instant cardinality estimation (`COUNT(*)`) via hardware instructions (`bits.OnesCount64`).
- Build a lexer and recursive-descent AST evaluator to compile boolean expressions (`(A | B) & C & !D`) into an optimal bitwise execution tree.
- Implement Kirsch-Mitzenmacher optimization: generate $K$ independent hash values using two base hash functions: $g_i(x) = h_1(x) + i \cdot h_2(x) \pmod M$.
- Calculate optimal Bloom filter parameters ($M$, $K$) given capacity $N$ and false-positive probability $P$.
- Analyze tradeoffs between dense bitsets, inverted posting lists, and Roaring Bitmaps for sparse attribute spaces in L5 system design rounds.

## Architecture / design note
```
bitmap-indexer/
├── cmd/bitmap-indexer/
│   └── main.go              # CLI entry point, flag parsing, command dispatch
├── pkg/bitset/
│   ├── bitset.go            # Word-level []uint64 bitset (Set, Clear, Test, Popcount, Ops)
│   ├── iterator.go          # Fast bit iterator using x & -x and TrailingZeros64
│   └── bitset_test.go       # Comprehensive bitset unit tests and property tests
├── pkg/query/
│   ├── ast.go               # Query AST nodes (And, Or, Xor, Not, Term)
│   ├── parser.go            # Recursive-descent parser for boolean query expressions
│   └── evaluator.go         # Evaluates AST across attribute bitsets
├── pkg/bloom/
│   ├── bloom.go             # Bloom filter with Kirsch-Mitzenmacher double-hashing
│   ├── math.go              # Optimal M and K parameter calculations
│   └── bloom_test.go        # False-positive validation and capacity tests
├── pkg/index/
│   ├── columnar.go          # Attribute dictionary mapping attribute:value -> Bitset
│   └── storage.go           # Binary serialization/deserialization of index files
├── bench/
│   └── bench_test.go        # Bitwise query vs naive iteration & map lookup benchmarks
├── docs/
│   └── bitmap-tradeoffs.md  # Dense vs Sparse vs Roaring Bitmaps & L5 design notes
├── go.mod
└── README.md
```
Key design decisions to make explicitly:
- Attribute index stores a distinct `*Bitset` for each `attribute:value` pair (e.g. `role:admin`), where bit index represents doc ID.
- NOT operations (`!expr`) must be masked with a universal active-document mask to prevent matching non-existent IDs beyond the indexed range.
- Iteration over matched IDs skips empty `uint64` words entirely (`word == 0`), extracting set bits in $O(\text{set bits})$ rather than $O(\text{total bits})$ using `x & -x`.

## Test strategy
- **Unit tests (`pkg/bitset`)**: Table-driven tests verifying `Set`, `Clear`, `Test`, `Popcount`, word-level operations across word boundaries (bit 63 vs 64), and edge cases (empty bitset, all ones, all zeros).
- **Parser tests (`pkg/query`)**: Test precedence rules (`&` binds tighter than `|`), nested parentheses, malformed syntax rejection, and correct AST evaluation matching known truth tables.
- **Probabilistic validation (`pkg/bloom`)**: Insert 100,000 keys; verify 0% false negative rate; query 100,000 non-inserted keys and verify empirical false-positive rate falls within expected bounds of target $P$.
- **Benchmarks (`bench/bench_test.go`)**: Benchmark multi-clause query throughput comparing bitwise operations, naive `[]Record` linear scans, and `map[string]bool` lookups with memory allocation reporting (`-benchmem`).

## Documentation checklist
- `README.md` with CLI usage instructions, flag definitions, and milestone checklist.
- `docs/bitmap-tradeoffs.md`: Analysis of memory consumption, CPU cache locality, and dense bitmap vs. Roaring Bitmap vs. inverted lists.
- Inline godoc documentation on all exported types, bit manipulation helper routines, and Bloom filter formulas.
- Benchmark summary recorded in `docs/bitmap-tradeoffs.md` detailing speedup factors and memory overhead.

## API contract
CLI only — no HTTP API.
```
bitmap-indexer index --data=<path.csv> --output=<index.db>
bitmap-indexer query --index=<index.db> --expr="<boolean-expr>" [--limit=N]
bitmap-indexer bloom-create --capacity=<N> --fp-rate=<float> --output=<path.bloom>
bitmap-indexer bloom-check --filter=<path.bloom> --key=<string>
bitmap-indexer bench [--records=1000000]
```
Exit codes: `0` on success, `1` on invalid arguments or syntax error, `2` on I/O error. Query outputs line-delimited matched IDs and summary counts to stdout.

## UI / status surfaces
None. CLI output only. Progress indicators on long-running indexing tasks sent to stderr; machine-readable query output on stdout.

## Security boundaries to think about
- **Resource exhaustion via malformed queries**: Deeply nested parentheses in `--expr` could trigger stack overflow; enforce a maximum recursion depth (e.g., 32 levels) in the parser.
- **Index file bounds validation**: Validate file headers, word counts, and payload bounds during deserialization to prevent out-of-memory allocations on corrupted `.db` files.
- **Hash collision resistance**: Bloom filters for security-sensitive checks must avoid predictable hash seeding if untrusted keys are indexed (mitigate HashDoS).

## Profiling plan
- Run `go test -bench=BenchmarkQueryExecution -cpuprofile=cpu.prof ./bench/` on 1,000,000 records; verify CPU popcount instruction generation (`POPCNT` on x86-64) via `go tool objdump`.
- Run memory profiling (`-memprofile=mem.prof`) during `index` to ensure bitset packing generates zero heap allocations per query evaluation.
- Profile Bloom filter hashing hot path to verify Kirsch-Mitzenmacher minimizes hash function overhead.

## How this project fits into the curriculum
Depends on [`go-fundamentals`](../go-fundamentals/README.md) (Go idioms, memory layout, binary I/O). Unlocks advanced database internals, search engines, and cache systems (e.g. `redis-cache`, LSM tree pre-filtering). Directly prepares for Google L5 rounds on bitwise tricks, hardware parallelism, and probabilistic data structure design commonly required in large-scale distributed systems interviews.

## Suggested milestone walkthrough
1. Implement `pkg/bitset/` with `[]uint64` backing slice, bit indexing arithmetic, word-level AND/OR/XOR/NOT, `bits.OnesCount64` popcount, and `x & -x` bit iteration; verify with table-driven tests.
2. Build `pkg/query/` lexer and recursive-descent parser for expressions like `(A | B) & C & !D`; implement AST evaluator producing a resulting bitset from attribute bitsets.
3. Implement `pkg/bloom/` using Kirsch-Mitzenmacher double-hashing, math formulas for optimal M and K, and serialization; test false-positive rate against theoretical bounds.
4. Wire CLI subcommands (`index`, `query`, `bloom-create`, `bloom-check`, `bench`) in `cmd/bitmap-indexer/`; run benchmark suite comparing bitmap queries vs naive slice scans; write `docs/bitmap-tradeoffs.md`.

## Reference notes and resources
- Warren, *Hacker's Delight* (2nd ed.) — Chapter 2: Basics (Lowest set bit isolation `x & -x`, clearing `x & (x - 1)`).
- Kirsch & Mitzenmacher (2006) — "Less Hashing, Same Performance: Building a Better Bloom Filter".
- Lemire et al. — "Roaring Bitmaps: Implementation of an Optimized Software Library".
- ClickHouse Architecture — "Using Bitmaps for Multi-Attribute Filtering and Aggregation".
- Go standard library documentation: [`math/bits`](https://pkg.go.dev/math/bits).
