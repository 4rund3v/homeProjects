# Job Scheduler

## What this project exists to solve
Google L5 interview candidates frequently stumble when classic algorithmic patterns must be synthesized within realistic system constraints, or when asked to formally prove greedy choices under questioning. This project grounds four critical L5 algorithm families — interval sweep-line, binary search on answer spaces, greedy heuristics with formal proofs, and Dynamic Programming (Weighted Interval Scheduling and 0/1 Knapsack) — in a production-grade cluster task placement and SLA capacity planner CLI (`job-scheduler`). Simulating batch workload scheduling across compute nodes (akin to Borg or Kubernetes task allocation) demonstrates why these algorithms are required in real infrastructure while mastering monotonic feasibility predicates, exchange argument proofs, and DP transition formulations.

## Success criteria / completion metrics
- `job-scheduler peak-nodes --jobs=workload.json` calculates minimum parallel nodes using both sort-and-min-heap and two-pointer sweep-line algorithms with identical results.
- `job-scheduler free-slots --schedule=calendar.json --duration=2h --range="08:00-18:00"` coalesces overlapping busy intervals and extracts available maintenance windows.
- `job-scheduler size-capacity --jobs=batch.json --deadline=4h` binary searches the monotonic answer space to find minimum worker capacity satisfying workload SLAs.
- `job-scheduler plan --policy=edf|sjf --jobs=workload.json --nodes=4` generates execution timelines and reports total makespan and maximum lateness.
- `job-scheduler optimal-weighted --jobs=weighted_batch.json` uses Dynamic Programming + binary search (`sort.Search`) to find the optimal subset of non-overlapping jobs maximizing total weight/value in $O(N \log N)$ time.
- `job-scheduler pack-node --tasks=tasks.json --max-memory=64GB` uses 0/1 Knapsack Dynamic Programming to maximize task throughput within fixed node memory limits.
- All algorithms pass table-driven tests covering edge cases: identical timestamps, zero-length jobs, fully disjoint tasks, nested intervals, and tight SLAs.
- Zero external runtime dependencies beyond Go standard library; benchmarks confirm $O(N \log N)$ scaling across 100,000 synthetic tasks.
- `docs/greedy-proofs.md` contains formal exchange arguments proving EDF minimizes maximum lateness and details counterexamples where greedy heuristics fail and DP is mandatory.

## Prerequisites and dependencies
- Completed [`go-fundamentals`](../go-fundamentals/README.md): slices, structs, custom sorting (`sort.Slice`), binary search (`sort.Search`), `container/heap` interface, table-driven tests, and benchmarks.
- Algorithmic maturity: asymptotic time/space complexity analysis, priority queue invariants, proof by induction / exchange argument fundamentals, and Dynamic Programming state transitions.

## Tools, libraries, and runtime
- Go 1.22+ runtime using standard library packages only (`container/heap`, `sort`, `time`, `encoding/json`, `flag`, `testing`).
- Standard Go toolchain commands for validation: `go test -v ./...`, `go test -race ./...`, and `go test -bench=. -benchmem`.

## Learning objectives (skills practiced)
- Implementing interval sweep-line and min-heap tracking (Meeting Rooms II) to compute peak concurrency without quadratic comparisons.
- Coalescing overlapping time intervals (Merge Intervals) and inverting busy schedules to discover free maintenance windows within query boundaries.
- Formulating monotonic feasibility predicates `canCompleteUnderSLA(capacity, deadline)` to execute binary search on answer spaces — the single most frequently failed pattern by senior candidates.
- Implementing Earliest Deadline First (EDF) and Shortest Job First (SJF) dispatchers across multi-node worker pools.
- Constructing formal greedy exchange arguments and articulating precise boundaries where greedy decisions fail, requiring dynamic programming.
- **Weighted Interval Scheduling (DP + Binary Search):** solving the non-overlapping maximum-profit scheduling problem in $O(N \log N)$ using memoized/tabulated DP and `sort.Search` for predecessor lookups — canonical Google L5 interview question.
- **0/1 Knapsack (DP):** resource budget allocation with state compression, determining optimal task assignment under capacity limits.

## Architecture / design note
```
job-scheduler/
├── cmd/job-scheduler/
│   └── main.go                 # CLI dispatch, flag parsing, JSON stdout formatting
├── pkg/intervals/
│   ├── interval.go             # Interval and Job structs, timestamp normalizer
│   ├── peak.go                 # Min-heap and sweep-line peak concurrency engines
│   ├── merge.go                # Interval coalescing and free window inversion
│   └── intervals_test.go       # Table-driven unit and property tests
├── pkg/capacity/
│   ├── predicate.go            # canCompleteUnderSLA feasibility evaluation
│   ├── search.go               # Binary search on capacity answer space
│   └── search_test.go          # Boundary tests, unachievable deadlines, single-job limits
├── pkg/planner/
│   ├── scheduler.go            # Multi-node worker pool simulator
│   ├── edf.go                  # Earliest Deadline First policy
│   ├── sjf.go                  # Shortest Job First policy
│   ├── dp_weighted.go          # Weighted Interval Scheduling (DP + Binary Search)
│   ├── knapsack.go             # 0/1 Knapsack node memory task packing
│   └── planner_test.go         # Lateness metrics and schedule verification
├── docs/
│   └── greedy-proofs.md        # Exchange arguments and greedy vs. DP failure analysis
└── testdata/                   # Workload, calendar, and batch sample JSON fixtures
```
Key design decisions:
- Domain types normalize ISO-8601 timestamps and relative durations into integer ticks (seconds) for deterministic comparisons.
- Sweep-line algorithm splits intervals into start (+1) and end (-1) events, sorting end events before start events on identical timestamps.
- Binary search establishes lower bound as `max(job_duration)` and upper bound as `sum(job_duration)` to guarantee logarithmic convergence.
- Weighted Interval Scheduling sorts tasks by finish time; for each task $i$, binary search (`sort.Search`) finds the latest non-conflicting predecessor $p(i)$ in $O(\log N)$, yielding recurrence: $DP[i] = \max(DP[i-1], \text{weight}_i + DP[p(i)])$.

## Test strategy
- **Unit tests:** table-driven tests verifying edge cases (empty workloads, simultaneous endpoints, nested sub-intervals, single huge jobs).
- **Equivalence tests:** assert that min-heap and sweep-line peak concurrency implementations yield identical results across random workloads.
- **Monotonicity invariant tests:** assert that for any capacity `C`, if `canCompleteUnderSLA(C) == true`, then `canCompleteUnderSLA(C + 1) == true`.
- **DP optimality verification:** test Weighted Interval Scheduling against an exponential brute-force recursive search on $N=20$ random tasks; assert exact equality of max weight.
- **Benchmarks:** `BenchmarkPeakNodesHeap`, `BenchmarkPeakNodesSweep`, `BenchmarkBinarySearchCapacity`, and `BenchmarkDPWeightedScheduling` on 10,000 and 100,000 synthetic jobs.

## Documentation checklist
- `README.md`: goal, scope, CLI subcommands with sample input/output, and milestone checklist.
- `docs/greedy-proofs.md`: rigorous exchange argument proof for EDF lateness minimization, counterexamples showing greedy failure on weighted intervals, and the DP recurrence derivation.
- In-code documentation: doc comments on all exported structs/interfaces, including algorithmic time and space complexity notes.

## API contract
CLI interface (No HTTP API):
```
job-scheduler peak-nodes --jobs=workload.json
job-scheduler free-slots --schedule=calendar.json --duration=2h --range="08:00-18:00"
job-scheduler size-capacity --jobs=batch.json --deadline=4h
job-scheduler plan --policy=edf|sjf --jobs=workload.json --nodes=4
job-scheduler optimal-weighted --jobs=weighted_batch.json
job-scheduler pack-node --tasks=tasks.json --max-memory=64GB
```
All commands write formatted JSON results to stdout on success (exit code 0) and structured error messages to stderr on failure (exit code 1).

## UI / status surfaces
None. CLI output only. Subcommands emit structured JSON payloads detailing computed metrics, timelines, and allocation summaries.

## Security boundaries to think about
- **Resource exhaustion / DoS:** enforce maximum job count (e.g., 500,000 tasks) during JSON unmarshaling to prevent unbounded memory allocation.
- **Integer overflow & boundary safety:** binary search midpoints calculated using `low + (high - low) / 2`; cumulative durations checked for overflow.
- **Input validation:** reject jobs with inverted intervals (`end < start`), negative durations, negative resource weights, or invalid date-time formatting.

## Profiling plan
- Benchmark sweep-line versus min-heap approaches using `go test -bench=. -benchmem` across 10K, 50K, and 100K job slices to compare allocation profiles.
- Profile memory allocations in DP table allocation; verify state space compression ($O(N)$ space for 1D DP, rolling row for Knapsack).

## How this project fits into the curriculum
Directly follows [`go-fundamentals`](../go-fundamentals/README.md), putting core Go data structures (`container/heap`, slices, custom sort) into service solving complex scheduling challenges. It establishes pattern recognition for Google L5 interview loops (intervals, answer-space binary search, greedy proofs, Dynamic Programming) before distributed systems topics like `raft-adv` and `telemetry-hub`.

## Suggested milestone walkthrough
1. **Interval overlap & peak capacity engine:** implement `Job` model and JSON parser; build sort + min-heap and sweep-line peak concurrency engines; expose `peak-nodes` CLI subcommand.
2. **Interval merging & free window discovery:** implement sort-by-start merging algorithm to coalesce overlapping intervals; implement range complement inversion; expose `free-slots` CLI command.
3. **Capacity sizing via binary search on answer space:** define `canCompleteUnderSLA` predicate; establish tight search bounds; implement binary search loop and expose `size-capacity` CLI command.
4. **Greedy dispatchers (EDF/SJF) & formal proof notes:** build multi-node simulation harness; implement EDF and SJF scheduling; output timelines and lateness metrics via `plan`; author formal proof sketches in `docs/greedy-proofs.md`.
5. **Weighted Interval Scheduling & Knapsack (DP):** implement $O(N \log N)$ DP with binary search for weighted interval scheduling, and 0/1 Knapsack task packing; wire `optimal-weighted` and `pack-node` commands.

## Reference notes and resources
- Cormen, Leiserson, Rivest, Stein (CLRS) — *Introduction to Algorithms*, Chapter 16: Greedy Algorithms (Activity Selection & Exchange Arguments), Chapter 15: Dynamic Programming.
- Kleinberg & Tardos — *Algorithm Design*, Chapter 4: Greedy Algorithms (Scheduling to Minimize Lateness & Earliest Deadline First), Chapter 6: Dynamic Programming (Weighted Interval Scheduling).
- Kubernetes Scheduler design documentation: Pod priority and queue sorting mechanisms.
- Go stdlib documentation: [`container/heap`](https://pkg.go.dev/container/heap) and [`sort`](https://pkg.go.dev/sort).
- LeetCode reference patterns: 253 (Meeting Rooms II), 56 (Merge Intervals), 435 (Non-overlapping Intervals), 1011 (Capacity To Ship Packages Within D Days), 1235 (Maximum Profit in Job Scheduling - DP + Binary Search), 416 (Partition Equal Subset Sum - 0/1 Knapsack).
