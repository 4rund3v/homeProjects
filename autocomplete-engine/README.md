# autocomplete-engine
**Goal:** Build a real autocomplete engine in Go that teaches trie design, prefix search, ranked top-K completion, wildcard matching, and compressed tries — then connects to Aho-Corasick for multi-pattern search.

**Scope:** Trie (insert, search, delete, prefix-match), ranked top-K completions with a min-heap, wildcard matching (`?` and `*`), compressed trie (radix tree), memory/speed benchmarks vs. hash map, CLI interface.

**Out of scope:** Persistent storage, HTTP API, fuzzy (edit-distance) matching, distributed autocomplete, UI frontend.

**Learning focus:** Trie as a data structure and algorithm; children-map vs. array tradeoff; top-K with a heap; wildcard DFS vs. DP intuition; radix tree compression; when a trie beats a hash map; synthesis with Aho-Corasick failure links.

**Depends on:** [`go-fundamentals`](../go-fundamentals/README.md), [`file-grepper`](../file-grepper/README.md)

## Milestones
- [ ] Milestone 1 — Trie core: insert, search, startsWith, delete; edge-case tests; memory/speed comparison to `map[string]struct{}` baseline
- [ ] Milestone 2 — Ranked top-K: store scores at terminal nodes; return top-K completions using a min-heap; test score updates and re-ranking
- [ ] Milestone 3 — Wildcard matching: support `?` (single char) and `*` (zero or more); DFS-on-trie approach; contrast with DP approach in a written note
- [ ] Milestone 4 — Compressed trie (radix tree): implement compression; benchmark node count reduction; write a comparison note: plain trie vs. radix tree vs. hash map — when each wins
