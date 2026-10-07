# Graph Lab

## What this project exists to solve
L5 graph interview questions are almost never "implement Dijkstra from memory" — they are "recognize that this problem is a shortest-path, topological order, dynamic connectivity, or common ancestor problem and apply the right algorithm correctly in 25 minutes." This project builds that recognition reflex by anchoring every algorithm to a single realistic tool: a package dependency resolver and build graph analyzer. BFS/DFS become reachability checks, topological sort becomes install-order computation, Lowest Common Ancestor (LCA) becomes dependency base resolution (like git merge-base), Union-Find and Kruskal become component membership and minimal build network creation, Dijkstra becomes install-cost minimization, and SCC becomes circular-dependency cluster detection. Every algorithm has a concrete reason to exist.

## Success criteria / completion metrics
- A working CLI binary (`dep`) with `resolve`, `cycles`, `shortest-path`, `components`, `lca`, `mst`, and `viz` subcommands, all driven by a parsed manifest file.
- Iterative DFS implemented explicitly (no recursion); cycle detection must not overflow on a 10,000-node linear chain.
- Kahn's algorithm reports the exact cycle path (not just "cycle exists") when topological sort fails.
- `dep lca <pkgA> <pkgB>` correctly identifies the Lowest Common Ancestor / dependency merge-base in a DAG using binary lifting or ancestor depth BFS/DFS.
- Union-Find implementation uses both union by rank and path compression; an in-code comment explains the α(n) amortized cost argument.
- `dep mst` computes the Minimum Spanning Tree of the cluster network using Kruskal's algorithm with the Union-Find engine.
- Dijkstra built on `container/heap`; a `NOTES.md` entry explains why it silently gives wrong answers on negative-weight edges.
- At least one SCC identified in a synthetic circular-dependency manifest; `viz` emits valid Graphviz DOT.
- Benchmarks comparing BFS, iterative DFS, and Kahn's on a 10,000-node synthetic graph; results saved to `bench/results.txt`.
- `NOTES.md` containing a table comparing all graph algorithm families: use case, time complexity, space complexity, and "when NOT to use."

## Prerequisites and dependencies
- `go-fundamentals` completed: package layout (`cmd/`+`pkg/`), table-driven tests, benchmarks, `go test -race`.
- Comfortable with Go interfaces and `container/heap` (or willing to read the stdlib source).
- No prior graph course required — the project teaches by doing, not by prerequisite.

## Tools, libraries, and runtime
- Go (latest stable); no third-party graph libraries — all algorithms implemented from scratch.
- Standard library only: `encoding/json`, `container/heap`, `flag`/`os.Args`, `fmt`, `testing`.
- Graphviz (`dot`) installed locally only for manual verification of `viz` output; not a build dependency.
- `benchstat` (from `golang.org/x/perf`) for comparing benchmark runs in Milestone 5.

## Learning objectives (skills practiced)
- Choosing between adjacency list (sparse, typical) and adjacency matrix (dense, O(1) edge lookup) based on graph density.
- Writing iterative DFS with an explicit stack — recognizing when recursion is unsafe on deep/large inputs.
- BFS level-order traversal for shortest-hop path in an unweighted graph.
- Kahn's algorithm: the in-degree queue loop and what it means when the queue empties before processing all nodes.
- DFS-based topological sort with coloring (white/gray/black) and back-edge cycle detection.
- **Lowest Common Ancestor (LCA) in DAGs:** finding common ancestors, topological depth calculation, and binary lifting / ancestor sets (canonical tree & DAG interview pattern, identical to git merge-base).
- Union-Find: union by rank to bound tree height; path compression to flatten lookup chains; when DSU beats DFS.
- **Kruskal's Minimum Spanning Tree (MST):** greedy edge sorting + Union-Find cycle prevention to connect all nodes with minimal cost.
- Dijkstra: min-heap `container/heap` implementation; the "relaxation" step; why negative weights break the greedy invariant.
- Bellman-Ford awareness: when to reach for it instead of Dijkstra (negative edges, negative cycle detection).
- Kosaraju or Tarjan SCC: two-pass DFS; strongly connected components as circular dependency groups.
- Benchmarking with `testing.B`, `b.ResetTimer()`, `b.ReportAllocs()`; synthetic graph generation for reproducible benchmarks.

## Architecture / design note
```
graph-lab/
├── cmd/dep/main.go          # CLI entry point; subcommand dispatch
├── pkg/graph/
│   ├── graph.go             # Graph type; adjacency list; AddEdge, AddWeightedEdge
│   ├── bfs.go               # BFS traversal; level-order; reachability
│   ├── dfs.go               # Iterative DFS; cycle detection; coloring
│   ├── toposort.go          # Kahn's + DFS-based topo sort; cycle path extraction
│   ├── lca.go               # Lowest Common Ancestor (LCA) in DAG
│   ├── unionfind.go         # DSU with union by rank + path compression
│   ├── mst.go               # Kruskal's Minimum Spanning Tree using DSU
│   ├── dijkstra.go          # Min-heap Dijkstra; returns dist map + prev map
│   ├── scc.go               # Kosaraju or Tarjan SCC
│   └── dot.go               # Graphviz DOT serializer
├── pkg/manifest/
│   ├── manifest.go          # Parse JSON/text dep manifest → Graph
│   └── manifest_test.go
├── bench/
│   ├── bench_test.go        # BFS vs. DFS vs. Kahn's on synthetic 10k-node graph
│   └── results.txt          # Saved benchmark output
├── testdata/
│   ├── simple.json          # Small acyclic manifest
│   ├── cycle.json           # Manifest with a known cycle
│   └── lca_test.json        # Branching dependency manifest for LCA
├── docs/
│   └── NOTES.md             # Algorithm comparison table, complexity, and tradeoffs
├── go.mod
└── README.md
```

## Test strategy
- Unit tests for each algorithm package against deterministic test graphs.
- Iterative DFS tested against a 10,000-node linear chain graph to guarantee no stack overflow.
- Kahn's algorithm tested on cyclic graph: assert that it returns an error AND the extracted cycle matches the actual cycle in the manifest.
- LCA test: assert correct ancestor on multi-branch DAGs and trees, including direct ancestor-descendant pairs.
- Kruskal's MST test: verify edge weight sum matches known MST on reference graphs, and cycle avoidance works.
- Dijkstra tested on graph with a known shortest path; negative edge test documenting why relaxation fails.
- Union-Find tested with a wrapper counting operations to verify that path compression actually flattens the tree.
- Benchmarks comparing BFS, DFS, and Kahn's on identical 10,000-node synthetic graphs.

## Documentation checklist
- `README.md`: usage, build commands, subcommand reference.
- `docs/NOTES.md`: table of all algorithm families (BFS, DFS, Topo Sort, LCA, Union-Find, MST, Dijkstra, SCC) comparing:
  - Typical interview problem disguise
  - Time complexity (best, worst, average)
  - Space complexity
  - Key invariant or state maintained
  - When NOT to use / common failure modes

## API contract
CLI only — no HTTP API.
```bash
dep resolve <manifest.json>           # prints install order
dep cycles <manifest.json>            # prints all detected cycles with paths
dep shortest-path <from> <to> <manifest.json> # Dijkstra shortest path
dep components <manifest.json>        # prints connected components via Union-Find
dep lca <pkgA> <pkgB> <manifest.json> # Lowest Common Ancestor in DAG
dep mst <manifest.json>               # Minimum Spanning Tree via Kruskal
dep viz <manifest.json>               # emits Graphviz DOT to stdout
```

## UI / status surfaces
None. CLI stdout for results; stderr for error and diagnostic messages.

## Security boundaries to think about
- **Unbounded recursion:** Iterative DFS guarantees process will not crash on deeply nested graphs.
- **Malformed manifests:** JSON parser must reject dangling edges (references to packages not in manifest) before building the graph.
- **Arbitrary command execution:** The `viz` command emits DOT format to stdout; it does not invoke `dot` or execute shell commands.

## Profiling plan
- Benchmark on a 10,000-node synthetic graph using `go test -bench=. -benchmem`.
- Verify adjacency list edge additions avoid quadratic slice re-allocations by pre-allocating known capacities where possible.

## How this project fits into the curriculum
Directly follows `go-fundamentals` and `file-grepper`. Prepares for distributed consensus reasoning in `raft-adv` (where network partitions, quorums, and leader reachability are graph concepts) and network topology analysis in `network-tracer`.

## Suggested milestone walkthrough
1. Implement adjacency list in `pkg/graph/graph.go`; implement iterative BFS and DFS; test reachability and cycle detection on linear chains.
2. Implement Kahn's topological sort in `pkg/graph/toposort.go` with cycle path extraction; implement LCA in `pkg/graph/lca.go`; wire CLI commands `resolve`, `cycles`, and `lca`.
3. Implement Union-Find in `pkg/graph/unionfind.go` with union by rank and path compression; implement Kruskal's MST in `pkg/graph/mst.go`; wire `components` and `mst` commands.
4. Implement Dijkstra in `pkg/graph/dijkstra.go` with min-heap on `container/heap`; wire `shortest-path` command; test negative-weight failure case.
5. Implement Tarjan or Kosaraju SCC in `pkg/graph/scc.go`; implement DOT serializer; run benchmark suite; write `docs/NOTES.md`.

## Reference notes and resources
- Cormen, Leiserson, Rivest, Stein (CLRS) — *Introduction to Algorithms*, Chapters 22 (Elementary Graph Algorithms), 23 (Minimum Spanning Trees), 24 (Single-Source Shortest Paths).
- Tarjan (1972) — "Depth-First Search and Linear Graph Algorithms" (SCC and topological sort).
- LeetCode reference patterns: 207 (Course Schedule), 210 (Course Schedule II), 236 (Lowest Common Ancestor), 684 (Redundant Connection - Union-Find), 743 (Network Delay Time - Dijkstra), 1584 (Min Cost to Connect All Points - Kruskal MST).
