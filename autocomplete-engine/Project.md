# autocomplete-engine

## What this project exists to solve
Tries appear in at least 20% of L5 string/search interviews, yet most engineers only know them as a textbook structure. This project makes the trie concrete by attaching it to a real tool — an autocomplete engine that could front a search box. Building the full stack (insert → ranked completions → wildcards → compression) forces the learner to understand both when a trie wins over a hash map and how the same trie node becomes the foundation of Aho-Corasick. The explicit benchmarks and comparison note make the tradeoffs interview-ready, not just toy-exercise-ready.

## Success criteria / completion metrics
- `search <prefix>` returns the correct top-5 completions, in score order, on a 100K-word trie
- `add <word> <score>` inserts or updates a word and immediately affects subsequent `search` results
- `delete <word>` removes a word and prunes dead branches; prefix queries no longer return it
- `wildcard <pattern>` correctly matches `?` (exactly one char) and `*` (zero or more chars) against all trie words
- `stats` prints node count, trie depth, and estimated memory vs. a `map[string]int` baseline
- Benchmark shows top-K completion time on a 100K-word trie; compressed trie node count reduction is measured and documented
- A written note (`notes/trie-vs-radix-vs-map.md`) explains which structure wins in which scenario, including system-design relevance
- A written note (`notes/wildcard-dfs-vs-dp.md`) explains why the trie DFS and DP approaches to wildcard matching are related
- All core operations have table-driven tests covering edge cases (empty trie, single-char words, full deletions leaving empty root, overlapping prefixes)

## Prerequisites and dependencies
- Completed `go-fundamentals`: Go module setup, structs, interfaces, maps, slices, goroutines, benchmarks with `testing.B`
- Completed `file-grepper`: familiarity with Aho-Corasick failure links — this project draws the explicit connection back to that work
- Understand heap operations (min-heap, max-heap) at the level of Go's `container/heap` interface
- Know basic complexity analysis: O(L) trie operations where L is word length; contrast O(1) average hash map lookup

## Tools, libraries, and runtime
- Go 1.22+ (module path: `autocomplete`)
- Standard library only: `container/heap`, `unicode/utf8`, `testing`, `flag`, `fmt`, `os`
- No third-party trie or NLP libraries — all data structures hand-rolled
- `go test -bench=. -benchmem` for profiling
- Word corpus: `/usr/share/dict/words` (Linux) or a downloaded English word-frequency list (e.g., `wordfreq` dataset, top 100K words with scores)

## Learning objectives (skills practiced)
- Implement a trie with a `map[rune]* Node` children map; understand why an array (`[26]*Node`) is faster but wastes memory for Unicode or sparse alphabets
- Write `Insert`, `Search`, `StartsWith`, `Delete` with correct branch-pruning on delete
- Store a frequency/score at terminal nodes; propagate a `maxScore` up each node to enable pruning during top-K search
- Implement top-K completions using `container/heap` (min-heap of size K) during a trie DFS; understand why keeping a bounded heap beats collecting all completions then sorting
- Implement wildcard DFS: at `?` advance one level to every child; at `*` branch into zero-advance (stay at same trie level) and one-advance (consume one char); recognise this as the same state space as the DP table
- Implement radix-tree compression: merge chains of single-child, non-terminal nodes into edge labels; measure node count before and after on the same corpus
- Articulate (in writing) why trie beats hash map for prefix queries, why radix tree beats naive trie for memory on sparse datasets, and when a hash map is still the right answer
- Trace Aho-Corasick failure links as a second use of the same trie node structure (referencing `file-grepper`), demonstrating cross-project synthesis

## Architecture / design note
```
autocomplete-engine/
├── trie/
│   ├── node.go          # TrieNode struct (children map, isEnd, score, maxScore)
│   ├── trie.go          # Insert, Search, StartsWith, Delete, PrefixMatch
│   ├── topk.go          # top-K DFS + min-heap wrapper
│   ├── wildcard.go      # wildcard DFS for ? and *
│   └── trie_test.go     # table-driven tests for all operations
├── radix/
│   ├── node.go          # RadixNode (edge label string, children map, isEnd, score)
│   ├── radix.go         # Insert, Search, Delete, PrefixMatch
│   └── radix_test.go
├── bench/
│   └── bench_test.go    # benchmarks: trie vs. radix vs. map; top-K on 100K corpus
├── notes/
│   ├── trie-vs-radix-vs-map.md
│   └── wildcard-dfs-vs-dp.md
├── main.go              # CLI: search, add, delete, wildcard, stats sub-commands
├── corpus.go            # load word list from file; assign scores (line number = score)
└── go.mod
```
Key design decisions to make explicitly:
- `maxScore` cached at every node means top-K can prune subtrees whose best possible score is below the current heap minimum — decide whether to implement this optimisation or note it as an extension.
- `Delete` must prune upward: a node is removable only if it is non-terminal and has no children.
- Radix tree `Insert` must handle four cases: exact match, shared prefix (split node), full edge consumed (descend), no shared prefix (new child).
- Wildcard `*` handling must avoid infinite loops: branching "consume zero chars" must not revisit the same `(node, patternIndex)` pair.

## Test strategy
- **Unit tests** (`trie/trie_test.go`): table-driven; cover empty trie, single-char words, inserting duplicate with updated score, deleting a word that is a prefix of another, deleting a word that shares a prefix with another, `StartsWith` on an empty prefix, Unicode words
- **Unit tests** (`trie/topk.go` path): verify top-K returns exactly K results when ≥K exist, fewer when <K exist, correct order with ties broken consistently
- **Unit tests** (`trie/wildcard.go`): `?` matches exactly one char; `*` matches zero, one, many chars; leading and trailing `*`; pattern longer than any word; pattern with consecutive `*`
- **Unit tests** (`radix/radix_test.go`): same functional contract as trie tests — insert/search/delete/prefix — to prove behavioural equivalence
- **Benchmarks** (`bench/bench_test.go`): `BenchmarkTrieInsert100K`, `BenchmarkMapInsert100K`, `BenchmarkTrieTopK`, `BenchmarkRadixTopK`, all with `-benchmem` to capture allocations

## Documentation checklist
- `README.md` with usage examples for all five CLI sub-commands
- `notes/trie-vs-radix-vs-map.md`: complexity table, memory comparison from benchmark output, scenario guide (when each wins)
- `notes/wildcard-dfs-vs-dp.md`: side-by-side pseudocode of DFS and DP, explanation of equivalence, note on LeetCode 44 (Wildcard Matching) and 212 (Word Search II)
- Inline comments on every non-obvious trie operation (especially `Delete` pruning and wildcard `*` branching)
- `bench/bench_test.go` output committed as a Markdown table in `notes/trie-vs-radix-vs-map.md`

## API contract
CLI only — no HTTP API.

```
autocomplete search <prefix> [--top N]    # default N=5
autocomplete add <word> <score>
autocomplete delete <word>
autocomplete wildcard <pattern>
autocomplete stats
```

Exit code 0 on success, 1 on error. Output is line-delimited plain text (word<TAB>score per result line).

## UI / status surfaces
None. CLI output only. `stats` prints a formatted table to stdout.

## Security boundaries to think about
- **Unbounded trie growth**: a caller sending millions of unique strings exhausts memory; document the risk and add an optional `--max-nodes` flag that rejects inserts once the node count limit is reached.
- **Unbounded wildcard fan-out**: a pattern like `*a*b*c*` on a large trie may visit exponentially many nodes; document worst-case and consider a visited-state cache (memoisation) or a depth/node-visit budget.
- **Input sanitisation**: reject words containing null bytes or control characters at the CLI boundary; define maximum word length (e.g., 256 chars) and enforce it.

## Profiling plan
- Run `go test -bench=BenchmarkTrieTopK -benchmem -count=5 ./bench/` on a 100K-word trie loaded from corpus; record ns/op and B/op.
- Run `BenchmarkRadixTopK` with the same corpus; record node count reduction logged by `stats`.
- Commit results as a table in `notes/trie-vs-radix-vs-map.md`.
- Profile further only if top-K on 100K words exceeds 10ms; if so, use `go tool pprof` to identify hot paths.

## How this project fits into the curriculum
`autocomplete-engine` sits after `go-fundamentals` (language) and `file-grepper` (Aho-Corasick / trie first contact). It deepens the trie from "pattern matching structure" to "ranked retrieval structure" and introduces heap-based top-K — a pattern that recurs in `k-nearest-neighbours`, `log-aggregator`, and any system-design project involving ranked results. The compressed trie (radix tree) is the bridge to system-design interviews ("how would you implement autocomplete at scale?"). Completing this project unlocks any project that requires prefix indexing, ranked retrieval, or multi-pattern matching.

## Suggested milestone walkthrough
1. Create the Go module; write `TrieNode` and the four core operations (`Insert`, `Search`, `StartsWith`, `Delete`) with branch-pruning; load `/usr/share/dict/words`; write table-driven tests and confirm all pass.
2. Add a `score int` field to terminal nodes and a `maxScore int` field to every node; implement `Insert` with score; write `TopK(prefix string, k int) []Result` using a DFS + `container/heap` min-heap; test score updates and ordering.
3. Wire up the CLI (`main.go`) for `search`, `add`, `delete`, `stats`; confirm end-to-end: load corpus, search a prefix, add a new word, delete a word, print stats.
4. Implement `Wildcard(pattern string) []string` using DFS with `?` (advance one child level, all children) and `*` (branch: consume zero or one char); add tests for edge patterns; write `notes/wildcard-dfs-vs-dp.md`.
5. Implement `radix/` package with radix tree insert (four split cases), search, delete, and prefix-match; verify behavioural equivalence against trie tests; run `bench/bench_test.go` and record results.
6. Write `notes/trie-vs-radix-vs-map.md` with benchmark table, complexity analysis, scenario guide; add `--max-nodes` guard to CLI; final review of all docs and inline comments.

## Reference notes and resources
- Sedgewick & Wayne, *Algorithms* (4th ed.) — Chapter 5.2: Tries; Chapter 5.3: Substring Search (Aho-Corasick context)
- Go standard library: [`container/heap`](https://pkg.go.dev/container/heap) — read the interface definition and example carefully
- LeetCode 208 (Implement Trie), 212 (Word Search II), 44 (Wildcard Matching), 745 (Prefix and Suffix Search) — use as test-case inspiration, not as the goal
- Wikipedia: [PATRICIA trie](https://en.wikipedia.org/wiki/Radix_tree) — read the "Compressed tries" section
- Aho & Corasick (1975), "Efficient String Matching" — skim Section 2 to see the trie as the foundation; connect to `file-grepper` notes
- Go blog: ["Profiling Go Programs"](https://go.dev/blog/pprof) — reference for the profiling plan
