# Profiling Lab

## What this project exists to solve
Learn performance profiling as an engineering discipline, not a reflex. This lab teaches how to form a hypothesis, define a representative workload, capture evidence, and decide whether a change matters.

## Success criteria / completion metrics
- A repeatable benchmark workload for both Python and Go, with input shape and machine/runtime details documented.
- At least one CPU profile and one memory/heap profile captured for each language.
- A before/after comparison for one deliberate optimization with no correctness regression.
- A `NOTES.md` interpretation that states what each profile does and does not demonstrate.

## Prerequisites and dependencies
- `go-fundamentals`, `python-refresh`.
- Run after the language projects; revisit it whenever a later project needs measurement.

## Tools, libraries, and runtime
- Go: `testing.B`, `go test -bench`, `pprof`, `benchstat`.
- Python: `cProfile`, `pyinstrument`, `tracemalloc`, optional `memory_profiler`.
- Optional: `perf` when host permissions and OS support permit it.
- All Python tooling managed via `uv` (see `../uv-setup.md`).

## Learning objectives (skills practiced)
- Workload definition, warm-up, repeated trials, variance and outlier awareness.
- CPU profile vs. heap profile vs. allocation profile vs. traces.
- Reading flame graphs and identifying inclusive vs. exclusive time.
- Distinguishing measurement noise from meaningful improvement.
- Avoiding premature optimization and preserving correctness.

## Architecture / design note
This is a lab repository, not a service. Organize each experiment as a small package/script with a stable input fixture and one command to reproduce the measurement. Keep profile artifacts out of version control unless a small image or summary is intentionally documented.

## Test strategy
- Correctness tests run before and after optimization.
- Benchmark command records the workload, environment, seed, and command line.
- Python and Go results are not compared as raw language rankings; compare changes within the same implementation/workload.

## Documentation checklist
- `README.md` with reproducible setup and benchmark commands.
- `NOTES.md` with hypothesis, baseline, change, result, variance, profile interpretation, and decision.

## API contract
None. The APIs are experiment functions and command-line runners.

## UI / status surfaces
None. Use text tables and optional flamegraph images in the notes.

## Security boundaries to think about
- Treat input datasets and profile outputs as potentially sensitive; use synthetic data by default.
- Profilers can expose function names, paths, and data values depending on instrumentation; do not publish profiles from real secrets/data.

## Profiling plan
This is the profiling curriculum itself. Each experiment should follow: define workload → collect baseline (≥5 runs when practical) → inspect profile → change one variable → rerun → summarize uncertainty. Use `benchstat` for Go benchmark comparisons; use repeated Python runs and report distributions where practical.

## How this project fits into the curriculum
It follows the fundamentals and precedes the projects with explicit performance claims, especially `data-compressor`; then it is reused by file hashing, services, telemetry, and Raft.

## Suggested milestone walkthrough
1. **Measurement basics.** Benchmark a pure CPU function in both languages. Observe variability; avoid asserting exact timing in tests.
2. **CPU vs. memory.** Use one allocation-heavy workload and one CPU-heavy workload. Capture the right profile type and explain why.
3. **Optimization experiment.** Form a hypothesis, make a single change, rerun at least five times, compare, and reject changes that do not show reliable gains.
4. **Service profiling (later).** Profile a defined request workload in `go-http-server` or `telemetry-hub`; protect profile endpoints and avoid production exposure.

## Reference notes and resources
- Go `pprof` guide: https://go.dev/blog/pprof.
- Go diagnostics documentation: https://go.dev/doc/diagnostics.
- Python `profile`, `cProfile`, and `tracemalloc` docs.
- `benchstat` documentation and examples.
