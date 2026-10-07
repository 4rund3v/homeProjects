# Profiling Lab

**Goal:** Build reproducible performance measurement habits for Python and Go services and CLI tools.

**Scope:** CPU, heap/allocations, goroutines/locks, latency/throughput, deterministic load generation, forming a hypothesis before profiling, and reading flame graphs and allocation profiles.

**Out of scope:** Production APM dashboards, alerting, and tracing infrastructure — those belong in `telemetry-hub` and follow-on deployment work.

**Learning focus:** Performance measurement as a scientific loop: model the workload, capture a baseline, isolate one change, compare. Profiles are evidence, not proof.

**Depends on:** `go-fundamentals`, `python-refresh`.

## Milestones
- [ ] Define a small workload with known input shape and resource footprint.
- [ ] Profile a Python exercise (CPU and heap) and a Go benchmark; document what each profile shows and does not show.
- [ ] Introduce one change per experiment, rerun, and compare with `benchstat` or an equivalent.
- [ ] Save profile artifacts and write a compact interpretation; treat each profile as evidence, not as a verdict.

## Tools
- Go `testing`, `pprof`, `benchstat`.
- Python `cProfile`, `pyinstrument`, `tracemalloc`, `memory_profiler`.
- Optional OS-level `perf` where available.

**Environment (Python):** See [`uv-setup.md`](../uv-setup.md).
