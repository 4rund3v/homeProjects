# Data Compressor

## What this project exists to solve
Understand compression format tradeoffs through reproducible measurements. The goal is not to write the fastest compressor — it is to build a disciplined measurement practice: define a workload, capture a baseline, change one variable, compare honestly.

## Success criteria / completion metrics
- Streaming round-trip correctness for at least two codecs (gzip + one of Zstandard or Snappy); byte-identical after decompression asserted in tests.
- A benchmark suite over representative datasets; results saved to a file and rendered as a readable table.
- A profiling run (`pprof`) identifying whether compression is CPU-bound or IO-bound on the chosen dataset.
- A recommendation in `NOTES.md` answering: "for my workload, which codec wins and why?"

## Prerequisites and dependencies
- `go-fundamentals` for package layout, testing, benchmarks, profiling.

## Tools, libraries, and runtime
- Go toolchain.
- Standard library: `compress/gzip`, `compress/zlib`.
- Optional: `github.com/klauspost/compress` (Zstandard, Snappy), `github.com/parquet-go/parquet` (for Parquet as a separate format exploration).
- Benchmarking: `testing.B`, `benchstat` (install in `profiling-lab`).
- Profiling: `net/http/pprof` or `go tool pprof`.

## Learning objectives (skills practiced)
- Streaming compression: `io.Pipe`, `bufio.Reader`/`Writer`, chunked processing.
- Benchmark design: representative datasets, `b.ReportAllocs()`, `b.ResetTimer()`, stable measurement.
- Profiling: CPU and memory profiles, flame graphs, allocation tracing.
- Tradeoff framing: throughput vs. ratio vs. memory; when "good enough" is correct.
- Parquet as a columnar storage format with embedded compression — separate from "compress this stream."

## Architecture / design note
```
cmd/compress/
  main.go          # CLI: compress/decompress/benchmark
internal/
  codec.go         # codec interface (Compress/Decompress)
  gzip.go          # gzip implementation
  zstd.go          # zstd implementation (optional)
  parquet.go       # Parquet encoder/decoder (separate concern)
bench/
  bench.go         # benchmark suite
```

Key design decisions:
- Define a `codec.Codec` interface (compress, decompress, name, contentType) so new codecs are one file.
- Separate "compression" from "Parquet encoding" in the mental model. Parquet is a file format that happens to compress; it is not a drop-in codec. If both are included, document the boundary clearly.
- Benchmark the same file at multiple sizes (1 KB, 1 MB, 100 MB) to expose size-dependent behavior.

## Test strategy
- Round-trip tests: compress → decompress → assert `bytes.Equal` original.
- Boundary: empty input, single-byte input, highly compressible input, incompressible input (already compressed / random).
- Benchmark tests with `-benchmem` and `-count=5` for stable numbers.
- Integration: CLI `compress` and `decompress` subcommands on fixture files.

## Documentation checklist
- `README.md` with setup, codec comparison table, how to reproduce benchmarks.
- `NOTES.md` with profiling artifacts, flame graph screenshots/links, and the recommendation table.
- Codec interface documented with `godoc` comments.

## API contract
No HTTP API. CLI with subcommands: `compress`, `decompress`, `benchmark`, `profile`.

## UI / status surfaces
Terminal output; benchmark results rendered as a markdown table.

## Security boundaries to think about
- Decompression bombs: a tiny compressed input expanding to gigabytes. Set a decompression size limit or document the risk.
- Path traversal: output filenames should not escape the target directory.

## Profiling plan
- CPU profile during compression of a 10 MB file; identify hot paths.
- Memory profile (`allocs` space) to confirm streaming (no full-file buffering).
- Compare gzip (single-threaded) vs. zstd (potentially multi-threaded) on the same input; profile shows where time is spent.

## How this project fits into the curriculum
Follows `go-fundamentals` and deepens Go tooling: benchmarks, profiling, package design. The `benchstat` comparison discipline feeds directly into `profiling-lab`. The codec interface pattern reappears in `telemetry-hub` and other integration points.

## Suggested milestone walkthrough
1. **gzip round-trip.** Implement compress/decompress using stdlib gzip; test byte-for-byte identity on fixtures of varying size and entropy.
2. **Second codec + interface.** Add Zstandard (or Snappy) behind the same `Codec` interface. Confirm both codecs pass the same round-trip tests.
3. **Benchmark suite.** Write benchmarks across datasets; capture results, render a markdown table in `NOTES.md`. Form a hypothesis about which wins before running.
4. **Parquet exploration (optional).** Treat Parquet separately: encode a small tabular dataset, compare file size and query-read performance. Document that Parquet is a storage format with embedded compression, not a streaming codec.

## Reference notes and resources
- `compress/` package docs.
- `pprof` guide: https://go.dev/blog/pprof.
- `benchstat` tool (install during `profiling-lab`).
- Parquet format spec overview (Apache Parquet docs).
