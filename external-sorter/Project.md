# external-sorter

## What this project exists to solve
Massive datasets routinely exceed physical RAM, causing processes to crash from out-of-memory errors if loaded naively. This project bridges algorithmic theory and production systems engineering by building an external sorting and K-way merge CLI (`external-sorter`) modeled after GNU `sort -S`, SQLite's internal VDBE sorter, and the MapReduce shuffle phase. Designed specifically for Google L5 interview readiness without using artificial puzzle sheets, it grounds core algorithmic patterns — Divide and Conquer, Priority Queues / Min-Heaps, Inversion Counting, and Disk-Based Binary Search — in a real systems tool that genuinely demands them.

## Success criteria / completion metrics
- `external-sorter sort --mem-limit=64MB --key=timestamp --input=large.log --output=sorted.log` sorts a 10 GB+ file without exceeding the configured 64 MB resident memory budget, verified via Go runtime memory statistics.
- `external-sorter merge --inputs=run1.log,run2.log,run3.log --output=merged.log` opens K sorted runs, maintains a min-heap of size K, and streams records to output in O(N log K) time with O(K · record_size) memory.
- Hierarchical multi-pass merge cascade automatically activates whenever the run count exceeds the maximum allowed open file descriptor limit (fan-in capacity), producing a correctly sorted final file.
- `external-sorter disorder-score --sample-size=100000 input.log` computes exact inversion count and normalized disorder score on sampled records in O(N log N) time using a divide-and-conquer modified merge sort.
- `external-sorter query --sorted-file=sorted.log --from="2026-10-01" --to="2026-10-02"` generates or leverages a sparse disk offset index to perform binary search range scans in logarithmic disk seek time.
- Deterministic cleanup guarantees zero orphaned temporary run files in scratch storage on normal completion, unexpected errors, or termination signals (`SIGINT`, `SIGTERM`).
- All packages achieve high test coverage, pass `go test -race ./...` with zero data races, and validate output sortedness against POSIX `sort -C`.

## Prerequisites and dependencies
- Completed `go-fundamentals`: Go interfaces, `io.Reader` and `io.Writer` pipelines, `bufio.Scanner`, `container/heap`, file descriptor I/O, table-driven testing, and benchmarks.
- Solid theoretical understanding of Divide and Conquer, Merge Sort, QuickSort, and Min-Heap priority queues.
- Familiarity with operating system process limits (`ulimit -n`), disk page caching, and buffered I/O semantics.

## Tools, libraries, and runtime
- Go 1.22+ standard library (`bufio`, `container/heap`, `io`, `os`, `os/signal`, `slices`, `sort`, `flag`, `testing`). No third-party dependencies.
- Go profiling tools: `testing.B` for benchmarks, `runtime/pprof` and `runtime.MemStats` for memory and CPU profiling.
- Synthetic log generator CLI tool (`cmd/genlogs/`) to produce deterministic structured test datasets of arbitrary size (10 MB to 10 GB+).
- POSIX `sort -C` system utility as an external correctness oracle for sorting verification.

## Learning objectives (skills practiced)
- Decomposing out-of-core problems exceeding single-machine RAM using the Divide and Conquer paradigm (chunking, run generation, multi-pass merging).
- Implementing Go's `container/heap.Interface` to maintain a min-heap priority queue over K concurrent file streams with O(log K) amortized insertion/extraction.
- Engineering external sorting mechanics: memory budgeting, buffer estimation, disk spill management, and hierarchical merge trees with fan-in limits.
- Augmenting Merge Sort to count inversions in O(N log N) time, calculating presortedness metrics without quadratic comparison overhead.
- Designing disk-based binary search: constructing sparse primary-key index offsets and using `os.File.Seek` for sub-millisecond range queries on sorted disk files.
- Enforcing strict memory bounds by accounting for Go runtime memory overhead (pointer indirection, slice capacity, garbage collection overhead).
- Implementing robust resource lifecycle management: atomic temp file creation, cleanup traps on process signals (`SIGINT`, `SIGTERM`), and graceful error recovery.
- Articulating Google L5 interview trade-offs: K-way merge time/space complexity, fan-in file descriptor limits vs. pass count, and mapping heap merging to FAANG interview problems (e.g. Merge K Sorted Lists, Merge Intervals).

## Architecture / design note
```
external-sorter/
├── cmd/
│   ├── external-sorter/
│   │   └── main.go          # CLI entry point, flag parsing, and subcommand dispatch
│   └── genlogs/
│       └── main.go          # Deterministic synthetic log generator (configurable size/format)
├── internal/
│   ├── chunker/
│   │   ├── chunker.go       # Memory-bounded buffer, in-memory sort, and temp run spilling
│   │   └── chunker_test.go
│   ├── merger/
│   │   ├── heap.go          # Min-heap priority queue over K stream heads
│   │   ├── merger.go        # Streaming K-way merger and multi-pass merge tree
│   │   └── merger_test.go
│   ├── analyzer/
│   │   ├── inversion.go     # Divide-and-conquer inversion counter
│   │   └── inversion_test.go
│   ├── index/
│   │   ├── sparse.go        # Sparse index builder and binary search range scanner
│   │   └── sparse_test.go
│   └── record/
│       ├── record.go        # Record parsing, field key extraction, and comparator
│       └── record_test.go
├── testdata/                # Deterministic test fixtures for unit and integration tests
├── docs/
│   └── l5-tradeoffs.md      # L5 algorithm analysis: D&C, K-way merge, heap mechanics, FAANG mappings
├── go.mod
└── README.md
```
Key design decisions to make explicitly:
- Memory budgeting must track both raw record bytes and Go runtime allocation overhead (slice headers, pointer indirection, GC headroom) before triggering run flushes.
- Min-heap elements encapsulate both current record and stream reader ID, allowing immediate replenishment from the exact exhausted run file upon pop.
- Intermediate merge passes must delete consumed temporary runs as soon as their streams are exhausted, bounding disk overhead to 2× input size.
- Sparse index records key-to-offset pairs at sampled block intervals (e.g., every 64 KB or 1,000 records) to keep index RAM minimal while enabling O(log N) disk seeks.

## Test strategy
- **Unit tests:** test record parsing and key comparison; verify min-heap invariants during arbitrary push/pop sequences; verify inversion counter against known permutations (sorted, reverse, random).
- **Streaming merger tests:** merge K pre-sorted runs and verify strict global ordering and constant heap memory consumption.
- **End-to-end sorting tests:** sort inputs with memory limits set artificially small (e.g., 1 MB limit on 10 MB input) to force multiple runs and hierarchical merge passes; verify sortedness with POSIX `sort -C`.
- **Bounded memory property tests:** monitor peak heap allocations via `runtime.ReadMemStats` during sorting runs; assert allocated memory never exceeds the specified limit plus a 10% safety margin.
- **Lifecycle & fault-tolerance tests:** simulate unexpected process termination or inject I/O errors during run generation and merge passes; assert zero leaked temporary files remain in scratch storage.
- **Benchmarks:** `BenchmarkKWayMerge` across varying fan-in values (K = 4, 16, 64, 256); `BenchmarkInversionCounter` measuring O(N log N) scaling against an O(N²) naive baseline.

## Documentation checklist
- `README.md`: project goal, scope, dependencies, milestone checklist, and quickstart commands.
- `docs/l5-tradeoffs.md`: external sort mechanics, K-way merge heap complexity, fan-in vs. I/O pass analysis, inversion counting D&C recurrence, and FAANG interview problem mapping.
- Comprehensive Go docstrings on all exported packages and methods documenting algorithmic invariants, time complexity, and memory requirements.

## API contract
CLI only — no HTTP API.
```
external-sorter sort --mem-limit=<limit> --key=<field> --input=<path> --output=<path> [--max-fan-in=<K>]
external-sorter merge --inputs=<path1,path2,...> --output=<path> [--key=<field>]
external-sorter disorder-score --sample-size=<N> [--key=<field>] <input>
external-sorter query --sorted-file=<path> --from=<start> --to=<end> [--key=<field>] [--index=<path>]
```
- Exit codes: 0 on success, 1 on invalid arguments or parsing errors, 2 on I/O or runtime failures.
- Output streams: processed records and query matches stream to stdout (or designated `--output` file); operational progress, run stats, and diagnostic metrics stream to stderr.

## UI / status surfaces
None. CLI output only. Real-time progress indicators (chunk generation count, active merge pass, records processed) stream to stderr.

## Security boundaries to think about
- **Temporary file isolation:** scratch run files must be created in a designated scratch directory with restricted permissions (`0700` directory, `0600` files) and `os.O_EXCL` flags to prevent symlink attacks and race conditions.
- **Path traversal prevention:** sanitize all user-supplied paths (`--input`, `--output`, `--index`) and restrict temporary run paths strictly within the isolated scratch directory.
- **Resource exhaustion limits:** validate available disk space prior to execution; enforce maximum allowable input sizes and cap total run generation to prevent disk exhaustion denial of service.
- **Unbounded line protection:** guard `bufio.Scanner` against excessively long record lines with explicit buffer limits; return a descriptive error instead of silently truncating or causing panic on buffer exhaustion.

## Profiling plan
- Profile memory allocations and GC pause frequency during run generation using `go test -bench=. -memprofile=mem.prof ./internal/chunker/` to verify minimal GC overhead.
- CPU profile during the K-way merge phase (`-cpuprofile=cpu.prof`) to confirm min-heap extraction and buffered I/O dominate wall time rather than string conversions or reflection.
- Benchmark run reader buffer sizes (16 KB, 64 KB, 256 KB) with `benchstat` to determine the throughput sweet spot balancing disk latency and RAM allocation per open run.

## How this project fits into the curriculum
Sits in Phase 1 (Algorithms) following `go-fundamentals` and alongside `file-grepper`. It transitions algorithmic study from pure in-memory data structures to out-of-core systems engineering, teaching how to handle datasets that exceed physical hardware constraints. The min-heap K-way merge directly reinforces heap concepts from `autocomplete-engine` while unlocking advanced systems projects like `kafka-basics` (log-structured disk segments and index search) and `profiling-lab` (memory profiling and allocation tuning).

## Suggested milestone walkthrough
1. **Record parser and synthetic generator:** implement structured record parsing, key extraction, and comparator in `internal/record/`; create `cmd/genlogs/` to generate deterministic test logs.
2. **Chunker and run generator:** build memory-bounded streaming reader in `internal/chunker/`; buffer records up to memory limit, sort with `slices.SortFunc`, and spill sorted temporary runs to disk.
3. **Min-heap and streaming K-way merger:** implement `container/heap.Interface` over open run file streams in `internal/merger/`; stream merged records to output with constant O(K · record_size) memory; wire `merge` CLI command.
4. **Hierarchical multi-pass merge tree:** implement multi-pass cascade for run counts exceeding max open files; add signal traps for deterministic scratch cleanup; wire end-to-end `sort` CLI command.
5. **Divide-and-conquer inversion counter:** implement modified merge sort in `internal/analyzer/` to count inversions and calculate normalized disorder score in O(N log N) time; wire `disorder-score` CLI command.
6. **Sparse disk index and binary search:** implement block-sampled sparse index builder and binary search range scanner in `internal/index/`; wire `query` CLI command; test with seek benchmarks.
7. **L5 tradeoff documentation and profiling:** author `docs/l5-tradeoffs.md` detailing algorithmic complexities, fan-in mathematics, and FAANG interview mappings; capture and commit memory/CPU benchmark profiles.

## Reference notes and resources
- Donald Knuth, *The Art of Computer Programming, Vol. 3: Sorting and Searching*, Section 5.4 ("External Sorting") — foundational reference for multi-way merging and run generation.
- Cormen, Leiserson, Rivest, Stein (CLRS), *Introduction to Algorithms*, Chapter 4 (Divide-and-Conquer & Inversion Counting) and Chapter 6 (Heaps / Priority Queues).
- GNU Coreutils `sort.c` source code — reference implementation for buffer budgeting, temp spill, and merge phase.
- SQLite Source Code (`vdbesort.c`) — multi-threaded external sorter architecture for relational queries.
- Go standard library documentation: [`container/heap`](https://pkg.go.dev/container/heap) and [`slices`](https://pkg.go.dev/slices).
