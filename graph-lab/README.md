# Graph Lab

**Goal:** Build a package dependency resolver CLI in Go that exercises every major graph algorithm under realistic conditions.

**Scope:** Graph representations (adjacency list, matrix), BFS, iterative DFS, cycle detection, connected components, topological sort (Kahn's + DFS-based), Lowest Common Ancestor (LCA in DAGs / dependency merge-base), Union-Find (union by rank + path compression), Kruskal's Minimum Spanning Tree (MST), Dijkstra with a min-heap, Kosaraju/Tarjan SCC; a CLI tool (`resolve`, `cycles`, `shortest-path`, `components`, `lca`, `mst`, `viz`) driven by a JSON/text dependency manifest.

**Out of scope:** Floyd-Warshall, A*, graph databases, any HTTP server or external infrastructure.

**Learning focus:** Recognizing which graph structure and algorithm applies under time pressure; iterative DFS (no stack overflow on deep graphs); Kahn's cycle-reporting; Lowest Common Ancestor (LCA) in dependency DAGs; Union-Find α(n) amortized cost; Kruskal's Minimum Spanning Tree; Dijkstra priority-queue invariant; SCC as circular-dependency detection; benchmarking BFS vs. DFS vs. Kahn's on 10,000-node synthetic graphs.

**Depends on:** [`go-fundamentals`](../go-fundamentals/README.md)

## Milestones
- [ ] Milestone 1 — Graph representation (adjacency list vs. matrix tradeoffs) + iterative BFS/DFS + cycle detection + connected components on a parsed package manifest
- [ ] Milestone 2 — Topological sort via Kahn's algorithm (BFS-based) with cycle path reporting, plus Lowest Common Ancestor (LCA / dependency merge-base in DAGs); `resolve`, `cycles`, and `lca` CLI commands
- [ ] Milestone 3 — Union-Find (union by rank + path compression) & Kruskal's Minimum Spanning Tree (MST); `components` and `mst` CLI commands
- [ ] Milestone 4 — Dijkstra with a min-heap (`container/heap`); weighted dependency graph; `shortest-path <from> <to>` CLI command; explain priority-queue invariant and negative-weight failure
- [ ] Milestone 5 — SCC via Kosaraju or Tarjan; detect mutually-dependent package groups; `viz` DOT output; benchmark BFS/DFS/Kahn's on 10,000-node graph; write algorithm comparison note
