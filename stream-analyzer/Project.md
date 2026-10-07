# Stream Analyzer

## What this project exists to solve
Sliding windows, monotonic stacks/queues, two pointers, two heaps, and range query trees are among the most heavily tested algorithmic patterns in Google L5 interviews. Studying them as LeetCode array puzzles obscures why they exist and leads to poor retention. This project embeds them in a production-grade telemetry and log analysis CLI (`stream-analyzer`). Production monitoring systems cannot buffer millions of events in memory or re-sort histories on every tick — they must process continuous streams using $O(1)$ window transitions, monotonic deque peak tracking, $O(1)$ stack-based spike discovery, two-pointer linear sweeps, $O(\log N)$ heap updates, and Fenwick tree range aggregations.

## Success criteria / completion metrics
- Working CLI tool (`stream-analyzer`) with `ingest`, `min-error-window`, `latency-stats`, `match-pairs`, and `range-query` subcommands.
- Fixed sliding window maintains event counts and error rates with strictly $O(1)$ time per event added/evicted.
- Monotonic deque maintains the exact maximum latency across a sliding window of size $W$ in $O(1)$ amortized time per event.
- Monotonic stack identifies the next greater latency spike and calculates spike duration for all events in $O(N)$ total time ($O(1)$ amortized per event).
- Variable sliding window correctly identifies the shortest window of logs containing all requested error signatures (e.g. `500`, `502`, `504`) in $O(N)$ time and $O(K)$ space.
- Two-pointer log reconciler pairs request and response logs with $O(N + M)$ time and $O(1)$ extra space beyond input buffering.
- Streaming two-heap structure calculates exact median latency with $O(\log N)$ insert and $O(1)$ median lookup; verified against `sort.Slice` ground truth.
- Fenwick tree (Binary Indexed Tree) evaluates dynamic prefix sums and arbitrary time-interval metric aggregations with $O(\log N)$ updates and queries.
- Benchmarks comparing two-heap streaming median vs batch sorting on 100,000 log events documented in `docs/benchmarks.md`.

## Prerequisites and dependencies
- `go-fundamentals` completed: Go structs, interfaces, slices, `container/heap`, and `testing.B` benchmarks.

## Tools, libraries, and runtime
- Go 1.22+ (standard library only).
- `bufio` for line-by-line log streaming without buffering whole files into RAM.
- `container/heap` for min-heap and max-heap implementations.
- Synthetic log generator script in `cmd/genlogs/` for reproducible testing.

## Learning objectives (skills practiced)
- **Fixed sliding window:** maintaining rolling time windows with circular ring buffers or timestamped queues; instant window slides.
- **Monotonic deque (Sliding Window Maximum):** maintaining elements in monotonically decreasing order to query the window peak in $O(1)$ time — canonical Google L5 interview pattern.
- **Monotonic stack (Next Greater Element):** maintaining an increasing/decreasing stack to detect latency spikes, calculate histogram bounds, and measure time-to-recovery in $O(1)$ amortized time.
- **Variable sliding window:** expanding right boundary to satisfy matching condition, contracting left boundary to minimize window size; invariant verification.
- **Two pointers:** monotonic convergence argument on sorted timestamp streams; pairing asynchronous logs with maximum time skew tolerance.
- **Two-heap pattern:** balancing a max-heap (lower 50% values) and min-heap (upper 50% values) to calculate running median in $O(\log N)$ time — canonical L5 data structure design pattern.
- **Top-K streaming heap:** maintaining a bounded min-heap of size $K$ to track the slowest endpoints without retaining full event history.
- **Fenwick Tree (Binary Indexed Tree):** point updates and range query evaluations using low-bit arithmetic (`i & (-i)`) in $O(\log N)$ time for streaming time-series intervals.

## Architecture / design note
```
stream-analyzer/
├── cmd/
│   ├── stream-analyzer/
│   │   └── main.go          # CLI entrypoint and subcommand dispatch
│   └── genlogs/
│       └── main.go          # Synthetic access log generator
├── internal/
│   ├── parser/
│   │   └── logentry.go      # Log record schema (JSON / Common Log Format)
│   ├── window/
│   │   ├── fixed.go         # Fixed W-second sliding window ring buffer
│   │   ├── deque.go         # Monotonic deque for sliding window maximum
│   │   ├── variable.go      # Minimum window error signature matcher
│   │   └── window_test.go
│   ├── correlate/
│   │   ├── twopointer.go    # Two-pointer request/response correlator
│   │   └── correlate_test.go
│   └── stats/
│       ├── stack.go         # Monotonic stack for next greater spike detection
│       ├── twoheap.go       # Running median via min-heap + max-heap
│       ├── topk.go          # Bounded min-heap for Top-K slowest paths
│       ├── fenwick.go       # Binary Indexed Tree for dynamic range queries
│       └── stats_test.go
├── docs/
│   ├── algorithmic-invariants.md
│   └── benchmarks.md
├── go.mod
└── README.md
```

## Test strategy
- **Unit tests:**
  - Fixed window: edge cases when window is empty, filled, wrap-around, and sudden idle gaps.
  - Monotonic deque: strictly increasing latencies, strictly decreasing, alternating peaks, window slide boundary evictions.
  - Monotonic stack: flat stream, strictly increasing spikes, strictly decreasing, duplicate peak latencies.
  - Variable window: test with non-existent signature, single-event match, overlapping occurrences, and duplicate signatures.
  - Two pointers: request without response, response without request, clock drift within max-skew, out-of-order within skew.
  - Two heaps: odd vs even number of elements, identical latencies, strictly increasing sequence, strictly decreasing sequence.
  - Fenwick tree: point updates, prefix sums, arbitrary range sums $[L, R]$, comparison with brute-force slice loop.
- **Cross-check tests:** Run two-heap median against `sort.Slice` over 10,000 random latencies; assert exact equivalence at every step.
- **Benchmarks:** Ingestion throughput (events/sec) and allocations per event for each algorithm.

## Documentation checklist
- `README.md`: Quickstart, command examples, and milestone tracking.
- `docs/algorithmic-invariants.md`: Formal explanations of sliding window left/right pointer invariants, monotonic queue/stack push/pop mechanics, two-pointer termination conditions, heap balance properties, and Fenwick low-bit isolation (`i & -i`).
- `docs/benchmarks.md`: Benchmark numbers comparing streaming two-heap vs batch sort, and Fenwick tree vs naive range scan.

## API contract
CLI commands:
```bash
stream-analyzer ingest --window=30s access.log
stream-analyzer min-error-window --signatures="500,502,504" access.log
stream-analyzer latency-stats --stream access.log
stream-analyzer match-pairs --requests req.log --responses res.log --max-skew=2s
stream-analyzer range-query --data metrics.log --start 100 --end 500
```

## UI / status surfaces
Terminal stdout for processed results and alerts; stderr for progress and parse errors.

## Security boundaries to think about
- **Memory exhaustion:** Stream files line by line; never load whole files into memory (`bufio.Scanner` with capped buffer).
- **Unbounded sliding windows:** If timestamps jump forward by hours, evict stale entries in $O(1)$ by resetting bucket counters rather than looping over millions of dead seconds.
- **Path traversal:** Validate input log file paths before opening.

## Profiling plan
Run `go test -bench=. -cpuprofile=cpu.prof ./internal/stats` to verify that monotonic stack/queue and heap operations do not allocate on the heap (`0 allocs/op`).

## How this project fits into the curriculum
Replaces abstract algorithm exercises with a production-minded stream processor. Patterns learned here directly empower `telemetry-hub` and `rate-limiter` in later phases while training high-frequency Google L5 interview patterns (monotonic deque, monotonic stack, two-heap median, Fenwick tree).

## Suggested milestone walkthrough
1. Implement `logentry.go`, `fixed.go`, and `deque.go`: build ring-buffer sliding window with monotonic deque for peak tracking; test under time jumps.
2. Implement `variable.go` and `stack.go`: implement minimum window error signature search, and monotonic stack for spike detection; write unit tests.
3. Implement `twopointer.go`: stream two sorted log files; advance left/right pointers to pair events within skew threshold.
4. Implement `twoheap.go`, `topk.go`, and `fenwick.go`: build min-heap and max-heap balancing logic, and Binary Indexed Tree range index; run cross-check tests; write `docs/benchmarks.md`.

## Reference notes and resources
- LeetCode 239 (Sliding Window Maximum - Monotonic Deque), LeetCode 739 (Daily Temperatures - Monotonic Stack), LeetCode 84 (Largest Rectangle in Histogram), LeetCode 76 (Minimum Window Substring), LeetCode 295 (Find Median from Data Stream), LeetCode 307 (Range Sum Query Mutable - Fenwick/BIT).
- Go standard library documentation: `container/heap`.
