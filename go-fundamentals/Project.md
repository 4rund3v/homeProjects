# Go Fundamentals & Algorithmic Foundations

## What this project exists to solve
To master Go for Google L5-level engineering, you cannot just learn syntax through trivial hello-world exercises. You must internalize Go's memory model, concurrency primitives, and idiomatic type design while implementing foundational algorithmic data structures from scratch using Go 1.22+ generics. Building custom heaps, monotonic stacks, ring buffers, binary search primitives, and concurrent worker pipelines establishes the exact algorithmic reflexes needed for all downstream systems and algorithm projects.

## Success criteria / completion metrics
- A modular Go module (`go-fundamentals`) with all packages passing `go test -v -race ./...` with zero data races.
- Generic Binary Min/Max Heap (`pkg/ds/heap`) built from scratch with $O(\log N)$ push/pop and $O(N)$ heapify, verified against `container/heap`.
- Generic Circular Ring Buffer (`pkg/ds/ringbuffer`) supporting $O(1)$ push/pop and overwrite semantics with boundary wrap-around tests.
- Generic Stack & Monotonic Stack (`pkg/ds/stack`) calculating nearest greater elements in $O(1)$ amortized time.
- Generic Binary Search package (`pkg/algo/search`) implementing exact search, `LowerBound`, `UpperBound`, and custom monotonic predicate binary search.
- Thread-safe Counter package (`pkg/counter`) comparing `sync.Mutex`, `sync.RWMutex`, and `sync/atomic` with benchmark reports.
- Generic Concurrent Pipeline (`pkg/pipeline`) implementing fan-out/fan-in worker pool with `context.Context` cancellation and no goroutine leaks.
- `NOTES.md` documenting Go design decisions: interfaces, pointer receivers, generics, channel vs. mutex tradeoffs, and Big-O invariants.

## Prerequisites and dependencies
- Go 1.22+ toolchain installed.
- No prior projects required — this is Project 1.

## Tools, libraries, and runtime
- Go standard library only (`sync`, `sync/atomic`, `context`, `cmp`, `container/heap`, `testing`). No third-party dependencies.
- Standard Go toolchain: `go test -race`, `go test -bench=. -benchmem`, `go vet`.

## Learning objectives (skills practiced)
- **Generics in Go 1.22+:** Designing generic constraints (`cmp.Ordered`, `any`), type parameters, and generic interfaces.
- **Binary Heap from scratch:** Array-based heap representation (parent `(i-1)/2`, children `2i+1`, `2i+2`), sift-up, sift-down, and Floyd's $O(N)$ linear-time heapify algorithm.
- **Monotonic Stack:** Maintaining strictly increasing/decreasing invariant to solve Nearest Greater Element problems in linear time.
- **Ring Buffer arithmetic:** Modular arithmetic `(head + 1) % capacity`, handling full/empty states without element reallocation.
- **Binary Search mechanics:** Strict midpoint calculation `low + (high - low) / 2` avoiding integer overflow; off-by-one boundary correctness in `LowerBound` and `UpperBound`.
- **Go Concurrency & Memory Model:** `sync.Mutex` vs. `sync.RWMutex` vs. `sync/atomic`, memory visibility, data race detection under `-race`.
- **Channel Patterns & Context:** Worker pools, fan-out/fan-in, closing channel ownership rules, and cancellation propagation with `context.WithCancel` and `context.WithTimeout`.

## Architecture / design note
```
go-fundamentals/
├── cmd/
│   └── runner/
│       └── main.go               # CLI harness exercising packages
├── pkg/
│   ├── counter/
│   │   ├── counter.go            # Counter interface
│   │   ├── mutex.go              # sync.Mutex implementation
│   │   ├── rwmutex.go            # sync.RWMutex implementation
│   │   ├── atomic.go             # sync/atomic implementation
│   │   └── counter_test.go       # Benchmarks & race detection tests
│   ├── ds/
│   │   ├── heap/
│   │   │   ├── heap.go           # Generic Binary Heap (Min & Max)
│   │   │   └── heap_test.go      # Invariant tests & heapify benchmarks
│   │   ├── ringbuffer/
│   │   │   ├── ringbuffer.go     # Generic Circular Ring Buffer
│   │   │   └── ringbuffer_test.go
│   │   └── stack/
│   │       ├── stack.go          # Generic Stack
│   │       ├── monotonic.go      # Monotonic Stack (Next Greater Element)
│   │       └── stack_test.go
│   ├── algo/
│   │   └── search/
│   │       ├── binarysearch.go   # Exact, LowerBound, UpperBound, Predicate
│   │       └── search_test.go    # Boundary condition tests
│   └── pipeline/
│       ├── pipeline.go           # Generic Generator, WorkerPool, Aggregator
│       └── pipeline_test.go      # Cancellation & goroutine leak tests
├── docs/
│   └── NOTES.md                  # Design reflections, invariants, and benchmark analysis
├── go.mod
└── README.md
```

## Test strategy
- **Unit tests:** Table-driven tests covering empty states, single elements, duplicates, capacity wrap-arounds, and boundary transitions.
- **Property & Invariant tests:**
  - Heap: Assert parent $\le$ children invariant after every push and pop across 10,000 random operations.
  - Ring Buffer: Assert FIFO order and correct overwrite semantics when pushed beyond capacity.
  - Binary Search: Verify `LowerBound` and `UpperBound` against `slices.BinarySearch` on random slices with duplicates.
  - Monotonic Stack: Verify output matches brute-force $O(N^2)$ scan on random arrays.
- **Concurrency tests:** 100 concurrent goroutines executing millions of operations on `pkg/counter` and `pkg/pipeline` under `go test -race`.
- **Benchmarks:** `BenchmarkCounterMutex` vs. `BenchmarkCounterRWMutex` vs. `BenchmarkCounterAtomic` with `-benchmem`.

## Documentation checklist
- `README.md` with package summaries, milestone checklist, and run instructions.
- `docs/NOTES.md` documenting:
  - Atomic vs. Mutex benchmark comparisons and why atomic wins under read-mostly vs. write-heavy workloads.
  - Generic heap sift-up/down derivations and why Floyd's bottom-up heapify runs in $O(N)$ rather than $O(N \log N)$.
  - Monotonic stack invariant proof.
  - Channel closure and cancellation ownership guidelines.

## API contract
CLI harness in `cmd/runner/main.go` runs demonstrations of all data structures and concurrency pipelines.
No HTTP API.

## UI / status surfaces
None. CLI and `go test` output only.

## Security boundaries to think about
- **Goroutine leaks:** Worker pipelines must always listen on `ctx.Done()` to ensure workers terminate when context cancels.
- **Integer overflow:** Midpoint arithmetic in binary search must use `low + (high - low) / 2`.
- **Data races:** Zero unsynchronized shared memory writes; all code verified with `go test -race ./...`.

## Profiling plan
- Run `go test -bench=. -benchmem -count=5 ./pkg/...` to record allocation and CPU profiles.
- Confirm that `heap`, `ringbuffer`, and `search` inner loops perform zero heap allocations (`0 B/op, 0 allocs/op`).

## How this project fits into the curriculum
This is Project 1. The data structures and algorithms built here are directly reused in:
- `stream-analyzer` (uses `ringbuffer` for sliding windows, `heap` for running median, `stack` for spikes).
- `external-sorter` (uses `heap` for K-way merge).
- `graph-lab` (uses `stack` for iterative DFS).
- `job-scheduler` (uses `search` for binary search on answer space).

## Suggested milestone walkthrough
1. **Module & Thread-Safe Counters:** Init `go.mod`. Implement `pkg/counter` (Mutex, RWMutex, Atomic). Run `go test -race` and benchmark.
2. **Generic Heap & Stack:** Implement `pkg/ds/heap` (sift-up/down, heapify) and `pkg/ds/stack` (with monotonic helper). Test invariants.
3. **Ring Buffer & Binary Search:** Implement `pkg/ds/ringbuffer` and `pkg/algo/search` (`LowerBound`, `UpperBound`, predicate). Test edge cases.
4. **Concurrent Worker Pipeline:** Implement `pkg/pipeline` (fan-out/fan-in) with `context` cancellation. Verify zero leaks under `-race`.
5. **Documentation & Benchmark Analysis:** Document benchmark results and invariants in `docs/NOTES.md`.

## Reference notes and resources
- Go standard library documentation: `sync`, `sync/atomic`, `context`, `cmp`.
- Cormen, Leiserson, Rivest, Stein (CLRS) — *Introduction to Algorithms*, Chapter 6 (Heaps) and Chapter 10 (Elementary Data Structures).
- Go memory model: https://go.dev/ref/mem
- Go Blog: "Go Concurrency Patterns: Pipelines and cancellation"
