# diff-tool
**Goal:** Build a working `diff` utility in Python (with a Go hot-path port) whose core algorithms are the canonical DP problems that appear in L5 interviews.

**Scope:** Edit distance (Levenshtein) with memoization, tabulation, and O(n) space optimization; LCS with full sequence reconstruction; Myers diff algorithm; unified diff output format; Python CLI; Go port of the edit-distance hot path; `NOTES.md` cataloguing the 8 DP patterns.

**Out of scope:** Three-way merge, binary file diffing, colorized terminal output, patch application (`patch`), VCS integration.

**Learning focus:** Recognizing and implementing the core DP patterns — linear DP, 2D DP, space optimization (rolling array), sequence reconstruction via DP-table backtracking, and divide-and-conquer DP (Myers); reading and generating unified diff hunks; Python-to-Go performance comparison.

**Depends on:** [`python-refresh`](../python-refresh/), [`go-fundamentals`](../go-fundamentals/) *(Go port only)*

## Milestones
- [ ] Milestone 1 — Edit distance: memoized recursion → tabulation → O(n) rolling-array; tested on known word pairs
- [ ] Milestone 2 — LCS: tabulation + backtracking to reconstruct the actual sequence; connection to edit distance documented
- [ ] Milestone 3 — Myers algorithm: edit graph, D-path search, snake concept; correct diff hunks on small examples
- [ ] Milestone 4 — Unified diff output: `@@ -l,s +l,s @@` headers, context lines, validated against POSIX `diff`
- [ ] Milestone 5 — `NOTES.md`: 8 DP patterns catalogue, one interview problem mapped to each; space-optimization recipe; reconstruction recipe

**Environment (Python):** See [`uv-setup.md`](../uv-setup.md).
