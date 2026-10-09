# Go Fundamentals

**Goal:** Build fluency in idiomatic Go and master foundational algorithmic data structures and concurrency patterns from scratch before tackling networked services and distributed systems.

**Scope:** 
- Generic data structures from scratch: Binary Min/Max Heap (`pkg/ds/heap`), Circular Ring Buffer (`pkg/ds/ringbuffer`), and Generic Stack with Monotonic Stack helpers (`pkg/ds/stack`).
- Search algorithms: Binary search primitives (`pkg/algo/search`) including exact match, `LowerBound`, `UpperBound`, and predicate-based search.
- Concurrency & synchronization: Thread-safe counters (`pkg/counter`) comparing `sync.Mutex`, `sync.RWMutex`, and `sync/atomic`; generic concurrent worker pipeline (`pkg/pipeline`) with fan-out, fan-in, and `context.Context` cancellation.
- Tooling & testing: Table-driven tests, subtests, race detector (`go test -race`), memory allocation benchmarks (`b.ReportAllocs()`), and package boundary design.

**Out of scope:** External HTTP frameworks, database drivers, third-party libraries (standard library only).

**Learning focus:** Go 1.22+ generics (`any`, `cmp.Ordered`), memory model under `-race`, pointer vs. value receiver semantics, sift-up/down heap mechanics, monotonic stack invariants, circular buffer wrap-around math, binary search boundary conditions, channel ownership, and context propagation.

**Depends on:** None.

## Milestones
- [ ] Milestone 1 — Module Setup & Thread-Safe Primitives: Initialize `go.mod`. Implement `pkg/counter` with Mutex, RWMutex, and Atomic implementations. Table-driven tests, race detection (`go test -race`), and benchmark comparisons under high contention.
- [ ] Milestone 2 — Foundational Data Structures (Heap & Stack): Implement generic binary min/max heap (`pkg/ds/heap`) from scratch with sift-up/down ($O(\log N)$) and linear-time heapify ($O(N)$). Implement generic stack (`pkg/ds/stack`) with monotonic stack tracking. Comprehensive unit and property tests.
- [ ] Milestone 3 — Ring Buffer & Binary Search Algorithms: Implement generic circular ring buffer (`pkg/ds/ringbuffer`) with $O(1)$ head/tail operations. Implement binary search primitives (`pkg/algo/search`) including `LowerBound`, `UpperBound`, and monotonic predicate binary search. Table-driven edge case tests.
- [ ] Milestone 4 — Concurrent Worker Pipeline with Context Cancellation: Implement generic concurrent pipeline (`pkg/pipeline`) with generator, bounded worker pool (fan-out/fan-in), and graceful cancellation using `context.WithCancel` and `context.WithTimeout`. Stress-tested under `-race` with zero leaks.
- [ ] Milestone 5 — Reflection & Invariant Documentation: Author `NOTES.md` documenting the Go memory model, interface design ("accept interfaces, return structs"), channel vs. mutex tradeoffs, and Big-O complexity tables for all implemented data structures.
