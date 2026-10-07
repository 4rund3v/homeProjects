# file-grepper

## What this project exists to solve

String search is one of the most frequently tested algorithm families at L5 interviews because it appears in log analysis, compiler tokenizers, DNA matching, and intrusion detection — domains where naive O(nm) search is observably too slow. This project forces you to implement each algorithm from scratch so you understand not just the correctness but the invariant each one maintains and the failure mode it was designed to fix. Building a real tool (not a LeetCode stub) means every algorithm must handle real file I/O, binary-safe byte handling, and multi-file traversal, making the performance differences tangible rather than theoretical.

## Success criteria / completion metrics

- `file-grepper <pattern> <path>` works recursively; output matches `grep`'s `filename:line:col` format exactly
- All five algorithms (`naive`, `kmp`, `rk`, `bm`, `ac`) produce identical match sets on the same input; a cross-algorithm correctness test asserts this
- `-algo=kmp|bm|rk|ac` switches the search engine at runtime with no other changes needed
- `-patterns-file` activates Aho-Corasick and accepts multiple patterns from a file (one per line)
- `-count` prints only match counts per file (like `grep -c`)
- Benchmark subcommand prints a table: algorithm, corpus size, matches, elapsed time, MB/s
- All algorithms pass a fuzz-style test with random patterns and random file contents (including null bytes and non-UTF-8 sequences)
- Binary files (detected by null byte in the first 8 KB) are skipped with a `[binary file skipped]` notice
- KMP, Rabin-Karp, and Aho-Corasick each have an inline comment block explaining the invariant they maintain and the complexity guarantee

## Prerequisites and dependencies

- Completed `go-fundamentals`: Go modules, slices, maps, interfaces, `os`/`bufio` file I/O, `testing` package
- Completed `file-hash-finder`: recursive `filepath.Walk` pattern; file-open error handling; path traversal guards
- Can articulate O(nm) string search before touching any of the advanced algorithms

## Tools, libraries, and runtime

- Go 1.22+ (standard library only — no third-party search libraries)
- `testing` and `testing.B` for unit tests and benchmarks
- `bufio.Scanner` or `bufio.Reader` for line-buffered file reading
- `flag` package for CLI flags
- A synthetic corpus generator (small Go script in `cmd/gencorpus/`) to produce deterministic test files of exact sizes (10 MB, 50 MB)
- No external dependencies; `go.mod` has no `require` entries beyond the standard library

## Learning objectives (skills practiced)

- Implement the KMP failure function from the recurrence definition, not from a tutorial; explain why it never needs to backtrack in the text
- Implement Rabin-Karp's rolling hash using a polynomial hash with a prime modulus; explain why collision probability is bounded and why verification is O(m) per collision
- Implement Boyer-Moore's bad-character table (O(alphabet + m) preprocessing) and then add the good-suffix rule; articulate why skipping right-to-left makes the algorithm sublinear on typical text
- Implement Aho-Corasick by recognizing it as: trie construction (O(total pattern len)) + BFS to compute failure links (same as KMP failure function on a trie) + output links for overlapping matches; connect this to the BFS/trie patterns already studied
- Know when to reach for each algorithm: Naive (pattern << text, simple code), KMP (worst-case guarantee needed), Rabin-Karp (multi-pattern or rolling-window variant), Boyer-Moore (single pattern, large alphabet, long pattern), Aho-Corasick (many patterns, one pass over text)
- Write `testing.B` benchmarks that report MB/s using `b.SetBytes()`; interpret allocations per operation
- Detect and skip binary files safely without panicking on null bytes or non-UTF-8 input

## Architecture / design note

```
file-grepper/
├── cmd/
│   └── file-grepper/
│       └── main.go          # flag parsing, subcommand dispatch
├── internal/
│   ├── search/
│   │   ├── naive.go         # Naive O(nm)
│   │   ├── kmp.go           # KMP + failure function
│   │   ├── rabinkarp.go     # Rabin-Karp + rolling hash
│   │   ├── boyermoore.go    # BM bad-char + good-suffix
│   │   ├── ahocorasick.go   # Trie + BFS failure links
│   │   └── searcher.go      # Searcher interface + factory func
│   └── walker/
│       ├── walker.go        # Recursive file walker with path guard
│       └── binary.go        # Binary file detection
├── cmd/gencorpus/
│   └── main.go              # Corpus generator for benchmarks
├── testdata/                # Small deterministic files for unit tests
├── go.mod
└── README.md
```

**Key design decisions to make explicitly:**
- `Searcher` interface: `Search(text []byte, pattern string) []Match` where `Match` holds `{Line, Col int}`; all algorithms satisfy the same interface so the benchmark and cross-algo test are trivial to write
- Preprocessing (KMP failure table, BM tables, AC trie) happens once per pattern/pattern-set, not per file; the walker passes the pre-built searcher into each file scan
- Line number tracking is done by the walker/scanner layer, not by each algorithm; algorithms return byte offsets, the walker converts to line:col

## Test strategy

- **Unit tests per algorithm**: known patterns with exact expected `{line, col}` outputs; edge cases: empty pattern, pattern equals entire text, overlapping matches (`"aaa"` in `"aaaa"`), pattern not found, single-character pattern, pattern at start/end of line
- **Cross-algorithm correctness test**: for 100 random (pattern, text) pairs, assert all five algorithms return identical match sets
- **Binary file test**: file containing null bytes is skipped; no panic, no spurious matches
- **Benchmark (`go test -bench`)**: `BenchmarkNaive`, `BenchmarkKMP`, `BenchmarkRK`, `BenchmarkBM`, `BenchmarkAC` each call `b.SetBytes()` with the corpus size so `go test` reports MB/s automatically
- **Walker test**: symlinks outside the root are not followed; path traversal via `../` in a patterns file is rejected

## Documentation checklist

- `README.md` — project goal, milestone list, build and run instructions, example output
- Each algorithm file has a top-of-file comment block: invariant, complexity (preprocessing + search), and one sentence on when to prefer this algorithm over the others
- `BENCH.md` — generated by the benchmark subcommand; a markdown table of results from a 50 MB corpus run (committed to the repo after Milestone 5)
- Inline comments at every non-obvious index arithmetic step in KMP failure function and Aho-Corasick BFS

## API contract

CLI only. No HTTP API.

```
file-grepper [flags] <pattern> <path>
file-grepper benchmark <path>          # benchmark subcommand

Flags:
  -algo string        Search algorithm: naive|kmp|rk|bm|ac (default "kmp")
  -patterns-file string  Path to newline-separated patterns file (activates ac)
  -count              Print only match count per file, not match lines
```

Output format (normal mode):
```
<filepath>:<line>:<col>:<matched_line_content>
```

Output format (`-count`):
```
<filepath>:<count>
```

## UI / status surfaces

None. CLI output only. Errors go to stderr; matches go to stdout (allows piping).

## Security boundaries to think about

- **Path traversal**: `filepath.Walk` is rooted at the user-supplied `<path>`; validate that the resolved absolute path of every file is still under the root before opening it; symlinks are not followed
- **Binary files**: detect null bytes in the first 8 KB; skip the file entirely to avoid garbled output and potential panics from invalid UTF-8 in line-splitting logic
- **Large files**: stream files line by line with `bufio.Scanner`; never read an entire file into memory; set `Scanner.Buffer` max size explicitly to avoid silent truncation of long lines
- **Pattern file injection**: when `-patterns-file` is used, strip each line of leading/trailing whitespace and skip blank lines; do not interpret any pattern as a file path or shell expression
- **Resource exhaustion**: reject any single pattern longer than 1 MB (the Aho-Corasick trie would be unreasonably large)

## Profiling plan

After Milestone 5, run `go test -bench=. -cpuprofile=cpu.prof ./internal/search/` on the 50 MB corpus. Use `go tool pprof` to find the hottest function in each algorithm. Expected findings: Naive spends all time in inner comparison loop; Boyer-Moore's good-suffix table lookup should dominate its preprocessing; Aho-Corasick's hot path is the trie node transition. Document findings in `BENCH.md`.

## How this project fits into the curriculum

Depends on `go-fundamentals` (Go syntax, testing, file I/O) and `file-hash-finder` (file walking, path safety). Unlocks any future project that requires substring or pattern matching — compiler front-ends, log analyzers, or an inverted-index project. The rolling-hash technique from Rabin-Karp also directly prepares for sliding-window DP problems. The Aho-Corasick trie + BFS connection reinforces trie and BFS patterns studied elsewhere in the curriculum.

## Suggested milestone walkthrough

1. Implement `walker.go` with recursive file walk, binary detection, and path traversal guard; write `walker_test.go` with a small temp-dir fixture; confirm `[binary file skipped]` output
2. Implement `naive.go` with `Searcher` interface returning byte-offset matches; add line:col conversion in the walker; write unit tests with known expected outputs; wire `main.go` with `-algo=naive`
3. Implement `kmp.go`: write the failure function first with its own unit test (`failureTable("ababc") == [0,0,1,2,0]`), then the search loop; run cross-algo test against Naive; add `BenchmarkKMP` and `BenchmarkNaive` with a 10 MB corpus; note the speedup
4. Implement `rabinkarp.go`: choose polynomial base and prime modulus; add collision verification loop; add `BenchmarkRK`; in a comment explain why multiple patterns can share one hash pass
5. Implement `boyermoore.go`: bad-character table only first, run tests, then add good-suffix table; confirm sublinear skip count on a corpus of repeated `"a"`s with pattern `"b"` at end
6. Implement `ahocorasick.go`: trie insertion → BFS for failure links → output-link propagation → search loop; wire `-patterns-file` flag; run cross-algo correctness test for multi-pattern case; generate 50 MB corpus with `gencorpus`; run benchmark subcommand and write `BENCH.md`

## Reference notes and resources

- Knuth, Morris, Pratt (1977) — "Fast Pattern Matching in Strings" (the original paper is readable)
- [KMP visualizer](https://people.cs.pitt.edu/~kirk/cs1501/animations/String.html) — trace the failure function step by step
- Aho, Corasick (1975) — "Efficient String Matching: An Aid to Bibliographic Search"
- Go `strings` package source (`strings/search.go`) — Go's stdlib uses a variant of Boyer-Moore-Horspool; read it after implementing your own
- [CP-Algorithms: KMP](https://cp-algorithms.com/string/kmp.html) and [Aho-Corasick](https://cp-algorithms.com/string/aho_corasick.html) — rigorous pseudocode with complexity proofs
- `go test -bench` documentation: `testing.B.SetBytes`, `b.ReportAllocs()`
