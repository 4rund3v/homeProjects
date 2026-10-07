# diff-tool

## What this project exists to solve
Dynamic programming is the hardest L5 interview category because candidates treat each problem as unique rather than recognizing the ~8 recurring patterns. This project forces pattern recognition by implementing a real, useful tool — a `diff` utility — whose entire core *is* the canonical DP problems. Edit distance, LCS, and Myers diff are not toy exercises; they are the exact algorithms used in production version-control systems, and interviewer variants ("minimum operations to transform X to Y", "return the actual subsequence") map directly to the sub-problems built here.

## Success criteria / completion metrics
- `diff-tool <file1> <file2>` produces output byte-identical to POSIX `diff -u` on at least 20 test pairs
- `--algorithm=edit-distance|lcs|myers` flag switches the core algorithm; all three produce equivalent change sets
- `--stats` flag prints added/removed/changed line counts
- Edit-distance implementation exists in three forms: memoized recursion, tabulation, O(n) rolling array — all return identical answers
- LCS reconstruction returns the actual sequence, not just its length; tested with known ground-truth pairs
- Myers implementation correctly identifies snakes and D-paths on grids up to 200×200 lines
- Go port of edit distance runs on 100 KB text files; wall-clock comparison against Python is documented in `NOTES.md`
- `NOTES.md` contains all 8 DP patterns, each with one mapped interview problem, a space-optimization recipe, and a reconstruction recipe
- Memory usage stays bounded: no algorithm allocates more than O(n·m) space for the full table, or O(n) when the rolling array is used

## Prerequisites and dependencies
- `python-refresh`: f-strings, dataclasses, `argparse`, `pathlib`, generator functions, type hints
- `go-fundamentals`: slices, structs, goroutines not required; just the Go toolchain and basic syntax
- Understanding of recursion and memoization at the level of a simple Fibonacci implementation
- Familiarity with big-O notation sufficient to evaluate O(nm) vs. O(n) tradeoffs

## Tools, libraries, and runtime
- Python 3.12+ via `uv` (see [`../uv-setup.md`](../uv-setup.md)); no third-party libraries for algorithm code
- `pytest` and `pytest-cov` for the test suite
- Go 1.22+ for the hot-path port (`go build ./cmd/editdistance`)
- `hyperfine` for wall-clock benchmarking of Python vs. Go on large inputs
- POSIX `diff` (system install) as the reference oracle for unified diff output validation

## Learning objectives (skills practiced)
- Implement memoized recursion correctly: recognize overlapping subproblems, define the recurrence, add a cache
- Convert memoized recursion to bottom-up tabulation: identify fill order, eliminate recursion overhead
- Apply the rolling-array (two-row) technique to reduce O(nm) space to O(n) — and articulate *why* it works
- Reconstruct the actual LCS by backtracking a filled DP table — a mandatory skill when the interview asks for the sequence, not just its length
- Recognize that edit distance and LCS are two views of the same recurrence (delete/insert vs. match/skip)
- Understand Myers' edit graph: states are (i, j) grid positions; moves are deletions (→), insertions (↓), or free diagonals (snakes); D-paths explore minimum-edit frontiers
- Generate unified diff hunks: parse `@@` markers, compute context lines, handle edge cases (no trailing newline)
- Identify which of the 8 DP patterns a new problem belongs to without being told

## Architecture / design note
```
diff-tool/
├── src/
│   └── difftool/
│       ├── __init__.py
│       ├── cli.py              # argparse entry point
│       ├── edit_distance.py    # memoized, tabulated, rolling-array variants
│       ├── lcs.py              # tabulation + reconstruct()
│       ├── myers.py            # edit graph, D-path search
│       └── unified.py          # hunk generation, @@ formatting
├── go/
│   └── cmd/
│       └── editdistance/
│           └── main.go         # Go port, hot path only
├── tests/
│   ├── test_edit_distance.py
│   ├── test_lcs.py
│   ├── test_myers.py
│   └── test_unified.py         # oracle: compare against `diff -u`
├── fixtures/                   # paired text files for integration tests
├── NOTES.md                    # 8 DP patterns catalogue (milestone 5)
├── pyproject.toml
└── README.md
```
Key design decisions to make explicitly before coding:
- All three Python algorithm modules expose a single stable function signature; `cli.py` dispatches by name with no special-casing
- The rolling-array variant must be a separate function, not a flag inside the tabulation function, so the space savings are visually obvious
- Myers operates on line arrays (not characters) — tokenization is the caller's job
- `unified.py` must not import from `myers.py` directly; it accepts a generic edit-script type so any algorithm can feed it

## Test strategy
- **Unit tests (edit distance):** known word pairs (`""→""`, `"kitten"→"sitting"` = 3, `"abc"→"abc"` = 0); assert all three variants agree on every input
- **Unit tests (LCS):** verify reconstructed sequence is a valid subsequence of both inputs and has the expected length; test empty inputs and identical inputs
- **Unit tests (Myers):** assert D-paths on 3×3 grids match hand-computed edit graphs; assert snake detection is correct
- **Integration tests (unified diff):** for each fixture pair, run `diff -u` and `diff-tool` and assert byte-identical output (handle trailing newline edge case separately)
- **Space test:** run rolling-array edit distance on a 1000×1000 input and assert peak RSS < 20 MB using `tracemalloc`
- **Regression:** any bug fix adds a new fixture pair that previously failed

## Documentation checklist
- `README.md`: goal, scope, milestones, uv setup reference ✓
- `NOTES.md`: 8 DP patterns, interview problem mapping, space-optimization recipe, reconstruction recipe
- Docstring on every public function: what it computes, parameters, return value, time and space complexity
- Inline comments at each DP recurrence explaining *why* the three cases (match / insert / delete) are what they are
- `go/cmd/editdistance/README.md`: how to build, how to benchmark, comparison methodology

## API contract
**CLI:**
```
diff-tool <file1> <file2> [--algorithm=edit-distance|lcs|myers] [--stats]
```
- Default algorithm: `myers`
- `--stats` writes to stderr so stdout remains pipe-safe
- Exit code 0 if files are identical, 1 if they differ, 2 on error (matches POSIX `diff`)

**Internal Python API (no HTTP):**
```python
edit_distance(s: str, t: str) -> int
lcs(a: list[str], b: list[str]) -> list[str]          # reconstruct
myers_diff(a: list[str], b: list[str]) -> EditScript
render_unified(script: EditScript, a, b, context=3) -> str
```

## UI / status surfaces
None. CLI output only. `--stats` writes a 3-line summary to stderr:
```
--- stats ---
+12 -4 ~3
```

## Security boundaries to think about
- **Memory exhaustion:** files larger than a configurable threshold (default 10 MB) must refuse to run the O(nm) full-table algorithms and either switch to the rolling-array variant or exit with a clear error; never silently OOM
- **Malicious filenames:** `argparse` handles this via positional arguments; no shell interpolation
- **Binary files:** detect non-UTF-8 content and exit with an error rather than corrupting output; do not attempt to diff binary files
- **Symlink loops:** resolve paths with `pathlib.Path.resolve()` before opening; document that symlinks are followed once

## Profiling plan
- After milestone 1: run all three edit-distance variants on a 500-line poem vs. a shuffled version; compare wall-clock with `timeit`
- After milestone 5 (Go port): use `hyperfine` to benchmark Python rolling-array vs. Go on 100 KB text files; document the result in `NOTES.md` under a "Performance" section
- Profile only deeper if a specific question arises (e.g., whether `sys.setrecursionlimit` is needed for memoized recursion on large inputs)

## How this project fits into the curriculum
Sits immediately after `python-refresh` (uses Python idioms throughout) and is a soft prerequisite for any project that requires understanding DP pattern recognition. The Go port creates a bridge to `go-fundamentals`. The `NOTES.md` catalogue becomes a reference card for all subsequent DP problems encountered in mock interviews. No later project depends on this one's code, but the pattern vocabulary it builds is assumed everywhere.

## Suggested milestone walkthrough
1. Implement memoized edit distance with `functools.lru_cache`; test on `"kitten"→"sitting"` and `"saturday"→"sunday"`
2. Convert to bottom-up tabulation; add an assertion that both return the same answer on all test inputs
3. Add the rolling-array variant (two rows only); add the `tracemalloc` space test
4. Implement LCS tabulation; add the `reconstruct()` backtracking function; test that the result is a valid common subsequence
5. Write the edit-distance/LCS connection note in `NOTES.md` — show that LCS length = (n + m − edit_distance) / 2
6. Implement Myers: build the edit graph abstraction, implement D-path BFS, identify snakes
7. Wire Myers output into `unified.py`; generate `@@ -l,s +l,s @@` headers with context lines
8. Run integration tests against POSIX `diff -u`; fix any hunk-boundary edge cases
9. Port rolling-array edit distance to Go; benchmark with `hyperfine`
10. Write the complete `NOTES.md` catalogue: 8 patterns, interview problem mapping, recipes

## Reference notes and resources
- Miller, W. & Myers, E.W. (1985) — "A File Comparison Program" (original Myers paper)
- [James Coglan's series on Myers diff](https://blog.jcoglan.com/2017/02/12/the-myers-diff-algorithm-part-1/) — best walkthrough of the edit graph and D-path concept
- GNU diffutils source — reference implementation of unified diff hunk logic
- *Introduction to Algorithms* (CLRS), Chapter 15 — dynamic programming; edit distance is the worked example
- Python `difflib` source — do NOT copy; read after implementing to compare design decisions
- [Levenshtein space optimization explained](https://en.wikipedia.org/wiki/Levenshtein_distance#Iterative_with_two_matrix_rows) — rolling-array diagram
- Go `strings` package docs — relevant for the Go port
