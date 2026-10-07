# Go Fundamentals

## What this project exists to solve
Build fluency in idiomatic Go before networked services or concurrency puzzles. The goal is not "write something that compiles" — it is to internalize Go's design philosophy so later projects read naturally.

## Success criteria / completion metrics
- A working Go module with at least three small, tested packages.
- A concurrent pipeline exercise that can be explained, tested under `-race`, and benchmarked.
- A reflective write-up (in this file or a short `NOTES.md`) explaining each Go design decision made: why interfaces, why errors-as-values, why `context`, why channels vs. mutexes.
- No external HTTP server or database — this is purely language and stdlib.

## Prerequisites and dependencies
- Go toolchain installed.
- No prior project needed.

## Tools, libraries, and runtime
- Go (latest stable).
- Standard library only (`encoding`, `sync`, `context`, `testing`, `crypto`, etc.).
- No third-party dependencies for this project — choosing dependencies is itself a later skill.

## Learning objectives (skills practiced)
- Go module system (`go.mod`, package boundaries, semantic import versioning).
- Composition over inheritance: embedding, interfaces, `accept interfaces, return structs`.
- Error handling: wrapped errors, sentinel errors vs. typed errors, `errors.Is`/`errors.As`.
- `context.Context` for cancellation and deadlines.
- Concurrency: goroutines, channels, `sync.WaitGroup`, `sync.Once`, `sync.Mutex`, worker pools.
- Testing: table-driven tests, subtests, race detector (`-race`), benchmarks with `testing.B`.
- Profiling baseline: recognize what `go test -bench=. -benchmem` reports.

## Architecture / design note
Organize work as small, independent packages rather than a single `main.go`:

Suggested packages:
- `pkg/counter` — a thread-safe counter. Demonstrates `sync.Mutex` vs. `atomic`, interface design.
- `pkg/pipeline` — a generic-style (Go 1.18+) concurrent pipeline. Demonstrates channels, fan-out/fan-in, cancellation via `context`.
- `pkg/config` — a typed YAML/JSON loader with validation. Demonstrates struct tags, `encoding`, and error wrapping.

`cmd/` holds thin `main.go` binaries that wire packages together. This `cmd/pkg` split is the convention used by most production Go projects and will recur everywhere.

## Test strategy
- Unit tests in `*_test.go` files adjacent to the package they test.
- Table-driven tests with named cases covering happy path, error path, and boundary.
- `go test -race ./...` as the standard invocation.
- Benchmarks using `testing.B` with `b.ReportAllocs()` and `b.ResetTimer()`.

## Documentation checklist
- `README.md` in each package briefly describing responsibility, exported types, and usage.
- `go doc` output should be readable.
- A top-level `NOTES.md` with design reflections on interface design, error wrapping, and concurrency choices.

## API contract
No HTTP API. Binary `cmd/` entries provide CLI surfaces for manual testing.

## UI / status surfaces
None. CLI output only.

## Security boundaries to think about
- Input validation at package boundaries (what does `config` accept?).
- Error wrapping should not leak secrets in error messages returned to callers.
- `atomic` vs. `sync.Mutex` tradeoffs matter for correctness; pick deliberately.

## Profiling plan
- Benchmark `pkg/counter` under contention; compare `atomic` vs. `sync.Mutex` throughput.
- Benchmark `pkg/pipeline` with varying worker counts; observe diminishing returns.
- Run `go test -bench=. -benchmem -count=5` and save results for comparison with `benchstat` later in `profiling-lab`.

## How this project fits into the curriculum
This is the foundation for every Go project afterward. Patterns established here (package layout, error handling, testing conventions) will appear in `file-hash-finder`, `go-http-server`, `raft-adv`, and others. Investing time here reduces confusion later.

## Suggested milestone walkthrough
1. **Module + counter.** Initialize `go.mod`, build `pkg/counter`, write table-driven tests and a benchmark. Run `-race`. Explain why `atomic` is safe here.
2. **Concurrent pipeline.** Build `pkg/pipeline` with a `context`-aware generator, N workers, and an aggregator. Test cancellation mid-pipeline.
3. **Typed config loader.** Build `pkg/config` that reads YAML/JSON and validates required fields. Demonstrate wrapped errors on validation failure.
4. **Reflection.** Write `NOTES.md` with 3–5 design decisions and the reasoning behind each.

## Reference notes and resources
- Go blog: "Error handling and Go" (official blog).
- `go doc` for every stdlib package used.
- `benchstat` (install later in `profiling-lab`) for comparing benchmark results.
