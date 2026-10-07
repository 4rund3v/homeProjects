# file-grepper

**Goal:** Build a grep-like file search CLI in Go that implements five string search algorithms — Naive, KMP, Rabin-Karp, Boyer-Moore, and Aho-Corasick — each powering a real flag-selectable code path.

**Scope:** Naive search baseline, KMP failure function, Rabin-Karp rolling hash with collision detection, Boyer-Moore bad-character and good-suffix heuristics, Aho-Corasick trie with failure and output links, recursive file walker, `filename:line:col` output, `-algo` flag, `-patterns-file` flag, `-count` flag, benchmark subcommand comparing all algorithms on the same corpus.

**Out of scope:** Regex support, colored output, binary file search (binary files are detected and skipped), case-folding beyond ASCII, parallel file scanning.

**Learning focus:** Why each algorithm exists and what failure mode it fixes; O(n+m) vs O(nm) worst-case analysis; rolling-hash as the foundation for sliding-window DP problems; Aho-Corasick as trie + BFS on failure links; precise tradeoff articulation between algorithms; Go benchmark tooling (`testing.B`); throughput measurement in MB/s.

**Depends on:** [`go-fundamentals`](../go-fundamentals/README.md), [`file-hash-finder`](../file-hash-finder/README.md)

## Milestones

- [ ] Milestone 1 — Naive search + recursive file walker + test harness; print `filename:line:col` matches; establish O(nm) correctness baseline
- [ ] Milestone 2 — KMP: implement the failure function (partial-match table); single-pattern O(n+m) search; compare wall time and character comparisons against Naive on a 10 MB corpus
- [ ] Milestone 3 — Rabin-Karp: rolling hash with explicit collision verification; add `-algo=rk` flag; explain in a code comment why it is preferred over KMP for multi-pattern search
- [ ] Milestone 4 — Boyer-Moore: bad-character rule first, then good-suffix; `-algo=bm` flag; document in a comment why the algorithm is often sublinear in practice and where it degrades
- [ ] Milestone 5 — Aho-Corasick: trie construction, BFS failure links, output links, `-patterns-file` flag; benchmark subcommand prints a comparison table (MB/s) for all algorithms on a 50 MB corpus
