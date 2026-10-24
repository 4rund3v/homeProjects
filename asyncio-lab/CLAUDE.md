# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **learning-first** asyncio project. The *deliverable* is understanding, not a polished tool. The concrete exercise: **find duplicate files in a directory by hash, group them, list full paths.** The *reason* that exercise is chosen is the *question it forces you to answer*:

> Hashing is **CPU-bound**; reading files is **I/O-bound**. Which parts does `asyncio` actually help, and which parts need **processes**?

Everything in this repo exists to make that question *felt*, not just stated.

## The one rule that decides "is this a good asyncio use case?"

- **I/O-bound** (waiting on disk / network / a syscall) → `asyncio` helps. The event loop *yields* while waiting; other coroutines run.
- **CPU-bound** (a `hashlib` loop, a parse, a math kernel) → `asyncio` does **not** help. It runs on **one thread**; CPU work *blocks* the loop. You need **processes** (`ProcessPoolExecutor`) or you *accept* that the CPU work is serial.

Your hash tool is **both**. The design (and the whole exercise) is: `asyncio` orchestrates the **I/O** (reading files, concurrent open/read), and a **process pool** does the **CPU** (the hash). If you "fix" it by making the hash `await`-able, that is the *exact* mistake the docs are warning about.

## Layout

- `docs/` — read in order. `00` is the conceptual core (the loop, coroutines, `async/await`, tasks). `01` is the I/O-vs-CPU decision. `02` is `asyncio.gather` / task groups / backpressure. `03` is the process-pool bridge. `04` is the *design* of the dup-find tool. `05` is uv + Docker + a k8s Service, i.e. the *delivery* layer.
- `app/dupfind/` — the CLI entrypoint (`main.py`). (Named `app/`, not `cmd/`, because a top-level `cmd` package *shadows the stdlib `cmd` module* — a real packaging footgun this repo deliberately avoids.)
- `internal/io/` — the async *reading* layer (the I/O-bound half).
- `internal/hasher/` — the *hashing* layer (the CPU-bound half; runs in a process pool).
- `internal/orchestrator/` — glues io + hasher with `gather` + the pool; the *design* is the point.
- `internal/report/` — grouping + printing full paths.
- `examples/` — runnable micro-exercises that build the concepts *before* the tool (a slow `sleep` fan-out, a CPU spin, the A/B of "async hash" vs "pool hash").
- `pyproject.toml` — `uv`-managed. `Dockerfile` + `k8s.yaml` — the container + Service scope.

## The exercise, in order (do not skip)

1. `docs/00` → run `examples/ex0-loop-and-sleep.py`. *Feel* the loop.
2. `docs/01` → run `examples/ex1-io-vs-cpu.py`. *Measure* why the CPU spin blocks the loop.
3. `docs/02` → run `examples/ex2-gather-vs-wait.py`. `gather` vs `TaskGroup` vs manual `wait` — the *differences* are the point.
4. `docs/03` → run `examples/ex3-pool-hash.py`. The A/B: `asyncio`-only hash vs `ProcessPoolExecutor` hash, *timed*.
5. `docs/04` → build `cmd/dupfind/` + the four `internal/` modules.
6. `docs/05` → `uv` lock, `Dockerfile`, `k8s.yaml` (a Service exposing a health/dup endpoint), run on a cluster.

## Working style (in this repo)

- Prefer **concrete timings and code** over prose. Every "asyncio helps here" claim should have a *measured* number next to it.
- Do **not** make the hash `await`-able. If a change tempts you to, stop and re-read `docs/01`.
- `asyncio` code: use **`asyncio.TaskGroup`** (3.11+) over bare `gather` where cancellation matters; use **`asyncio.to_thread`** for *cheap* CPU blips, **`ProcessPoolExecutor`** for *sustained* CPU.
- Keep the *dup-find* tool's correctness *independent* of concurrency: the *result* (the duplicate groups) must be *identical* whether you run with 1 worker or 64. Concurrency changes *speed*, never *output*.

## Anti-goals

- No "make it faster by 3×" — the goal is *correct* concurrency with *measured* understanding of *where* it helps.
- No blocking the event loop "just for the hash" — that is the *exact* anti-pattern; use the pool.
- No global mutable state in the async path; pass results via `Task` return values / `Queue`.
- The k8s Service is for *delivery + a live probe*, not for "we need k8s." Keep the container self-contained; the Service just exposes it.

## uv note

This project is `uv`-managed (see the workspace-root `uv-setup.md`). Commands: `uv run ...` (never bare `python`), `uv lock`, `uv sync`. The `pyproject.toml` pins Python `>=3.11` because `TaskGroup` and `asyncio.to_thread` ergonomics are 3.11+.
