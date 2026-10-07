# File Hash Finder

## What this project exists to solve
Build a production-aware Go CLI that finds duplicate files by content. The goal is to practice Go's filesystem APIs, concurrency, configuration, and safe destructive-operation design — all without a server.

## Success criteria / completion metrics
- Correctly identifies duplicates in a fixture tree with known contents.
- Handles ignore patterns and minimum-size filters from a config file.
- Parallel worker pool; `-race` passes; benchmark compares serial vs. parallel throughput.
- Dry-run mode is the default; actual deletion requires explicit confirmation and checksum verification.
- A `NOTES.md` reflecting on concurrency choices (bounded worker pool vs. unbounded) and the safe-deletion design.

## Prerequisites and dependencies
- `go-fundamentals` package layout, testing conventions, error wrapping.

## Tools, libraries, and runtime
- Go toolchain.
- Standard library: `crypto/sha256`, `path/filepath`, `context`, `sync`, `flag` (or `cobra`).
- Optional: `viper` for config, `BLAKE3` (if comparing algorithms).
- No external services.

## Learning objectives (skills practiced)
- `fs.WalkDir` for recursive traversal.
- Hashing: streaming reads, partial hash for pre-filter (size + first-N-bytes), full hash for confirmation.
- Worker pool pattern: bounded goroutines, `sync.WaitGroup`, error channel.
- Config parsing: YAML/TOML config for ignore patterns, min-size, hash algorithm.
- `context` cancellation: handle SIGINT gracefully, do not leave dangling goroutines.
- `go test -race` under real concurrency.
- Benchmarks with `testing.B` and `-benchmem`.

## Architecture / design note
```
cmd/finder/
  main.go          # CLI wiring
internal/
  walker.go        # directory traversal, emits FileMeta
  hasher.go        # worker pool, partial + full hash
  matcher.go       # group by hash, report duplicates
  config.go        # viper/flag config loader
  output.go        # human + JSON output
pkg/
  fileset/         # (optional) reusable FileSet type
```

Key design decisions:
- Hash-once strategy: size + first-N-bytes filter before computing SHA-256 to avoid reading every byte of every file.
- Two-pass: cheap filter then expensive confirmation. This is how every real deduplicator works.
- Worker pool with a bounded channel: unbounded goroutines exhaust file descriptors.
- Dry-run by default: deletion is irreversible; never surprise the user.

## Test strategy
- Fixture directory with known duplicate files, unique files, symlinks, and a circular symlink (test behavior explicitly).
- Unit tests for `hasher` with in-memory `io.Reader` sequences (no filesystem required).
- Concurrency tests: `go test -race`, verify no data races under parallel hashing.
- Integration test running the full CLI against a temp dir.

## Documentation checklist
- `README.md` with setup, usage, config format, dry-run behavior, and performance notes.
- `NOTES.md` with concurrency design reflection and why bounded pools matter.

## API contract
No HTTP API. CLI only; support `--json` output for machine-readable results.

## UI / status surfaces
Terminal output. `--json` for piping to other tools.

## Security boundaries to think about
- Symlink traversal: follow symlinks? Document the choice and the risk of loops.
- Path traversal in config-supplied directories: resolve to absolute paths.
- File permissions: hashing a file you can't read is an error, not a crash.
- Deletion is irreversible; dry-run is the contract.

## Profiling plan
- Benchmark parallel throughput vs. serial with `testing.B`.
- Profile memory allocations during hashing; confirm reads are streaming, not buffering entire files.
- Compare SHA-256 vs. BLAKE3 throughput; measure the tradeoff between speed and collision resistance.

## How this project fits into the curriculum
First real Go tool after `go-fundamentals`. Concurrency and `context` patterns recur in `data-compressor` and `raft-adv`. The worker-pool pattern and safe-destructive-operation design are broadly applicable.

## Suggested milestone walkthrough
1. **Serial walk + SHA-256.** Walk a fixture tree; report duplicates by hash. Tests with known fixtures.
2. **Partial hash optimization.** Size + first-N-bytes filter before full SHA-256; confirm identical results.
3. **Parallel worker pool.** Add bounded concurrency; benchmark vs. serial with `-race`.
4. **Config + dry-run deletion.** Add viper config for ignore patterns and min-size. Default to dry-run; deletion requires `--delete` flag and checksum confirmation.

## Reference notes and resources
- Go `filepath.WalkDir` docs.
- `crypto/sha256` and streaming `io.Reader` patterns.
- Partial hash / "hash-on-read" strategies from deduplication literature.
