# Engineering Learning Curriculum

A step-by-step, hands-on curriculum for strengthening Python, becoming proficient in Go, mastering core algorithms through real software tools, and understanding backend, distributed-systems, security, data, and platform engineering.

This is a learning workspace: every milestone is designed and implemented as a real, usable software project. We avoid artificial LeetCode-style puzzle stubs. The goal is to build deep mechanical intuition and tradeoff articulation for Google L5-level engineering by implementing the algorithms inside the tools that genuinely demand them.

## Learning goals and constraints

- **Python:** Refresh modern language features, OOP/design patterns, decorators, typing, testing, Django, and Django REST Framework.
- **Go:** Build from fundamentals to idiomatic services, concurrency, configuration, profiling, and systems tooling.
- **Algorithms (Google L5 Readiness):** Master algorithmic patterns, asymptotic complexity, and tradeoff reasoning by building concrete tools (a grep engine, dependency resolver, diff tool, search autocomplete, streaming log window analyzer, out-of-core external sorter, cluster job scheduler, and bitmap indexer).
- **Systems & Platform:** PostgreSQL, Redis cache and Streams, Kafka, observability, Raft consensus, TLS/mTLS, applied cryptography, network diagnostics, gRPC, Kubernetes, Helm, Terraform, local CI/CD, and Keycloak (required).
- **Local Environment:** Use Docker/local environments wherever practical; avoid requiring cloud accounts or paid services.
- **Production Mindset:** Treat each project as production-minded engineering practice, not a claim that a small local learning app is production-ready.

---

## Google L5 Algorithm Readiness: Real Projects vs. LeetCode

Google L5 interview rounds evaluate senior problem-solving:
1. **Pattern Recognition:** Can you identify within 2-3 minutes whether a problem requires a sliding window, a topological sort, dynamic programming with space optimization, a two-heap median, or a binary search over an answer space?
2. **Deep Tradeoff Articulation:** Can you compare algorithm alternatives honestly (e.g. KMP vs Boyer-Moore vs Rabin-Karp; dense bitsets vs posting lists vs Roaring Bitmaps; Kahn's algorithm vs DFS cycle detection; in-memory sort vs external K-way merge)?
3. **Formal Verification:** Can you prove why a greedy heuristic is optimal (using exchange arguments) or prove that an answer space is monotonic before applying binary search?
4. **Mechanical Sympathy:** Do you understand cache locality, hardware POPCNT, CPU word-level parallelism, memory allocation overhead, and disk seek latency?

To develop lasting retention and genuine intuition, **every algorithm pattern is implemented inside a functional CLI tool or library**:

| Algorithmic Pattern | Real Tool / Project | Concrete Problem Solved |
|---|---|---|
| **Backtracking & Constraint Propagation** | [`sudoku-solver`](sudoku-solver/) | Exact cover solver with MRV heuristic & forward checking |
| **Tree Traversal & Hashing** | [`file-hash-finder`](file-hash-finder/) | File tree duplicate detector with bounded concurrency & safe dry-run |
| **String Search (KMP, BM, Rabin-Karp, Aho-Corasick)** | [`file-grepper`](file-grepper/) | Recursive grep CLI with `-algo` switch & multi-pattern Aho-Corasick trie |
| **Graphs (BFS, DFS, Topo Sort, LCA, Union-Find, MST, Dijkstra, SCC)** | [`graph-lab`](graph-lab/) | Package dependency resolver: Kahn's topo sort, DAG Lowest Common Ancestor (merge-base), Kruskal MST, Dijkstra, and Tarjan SCC |
| **Dynamic Programming (Edit Distance, LCS, Myers Diff)** | [`diff-tool`](diff-tool/) | Unified diff utility (`diff -u`) with space-optimized DP & sequence reconstruction |
| **Tries, Heaps (Top-K), Wildcards, Radix Trees** | [`autocomplete-engine`](autocomplete-engine/) | Search prefix autocomplete engine with ranked min-heap & compressed radix tree |
| **Sliding Window, Monotonic Queue/Stack, Two Heaps, Fenwick Tree** | [`stream-analyzer`](stream-analyzer/) | Real-time telemetry analyzer: monotonic deque window maximums, monotonic stack spikes, two-heap median, and Fenwick tree range index |
| **Divide & Conquer, External Sorting, K-Way Merge** | [`external-sorter`](external-sorter/) | 10 GB+ disk-backed file sorter running under 64 MB RAM limit using min-heap & inversion counting |
| **Intervals, Binary Search on Answer Space, Greedy, DP** | [`job-scheduler`](job-scheduler/) | Cluster task planner: interval sweep-line, monotonic feasibility binary search, greedy EDF with proofs, Weighted Interval DP & Knapsack |
| **Bit Manipulation, Word-Level Parallelism, Bloom Filter** | [`bitmap-indexer`](bitmap-indexer/) | Columnar attribute search & fast set filter engine with Kirsch-Mitzenmacher hashing & bit isolation (`x & -x`) |
| **Compression & Columnar Storage** | [`data-compressor`](data-compressor/) | Codec evaluation (gzip/zstd) & Parquet columnar storage format comparison |
| **Empirical Profiling & Benchmarking** | [`profiling-lab`](profiling-lab/) | CPU/heap profiling (`pprof`), flame graphs, memory allocations (`benchstat`) |
| **Concurrency Patterns & Rate Limiting** | [`rate-limiter`](rate-limiter/) | Token bucket & sliding window concurrent library with HTTP middleware |

---

## Definition of done for each project

Each project README tracks its scope and milestones:
- A concise architecture/design note, setup/run instructions, configuration reference, and lessons/tradeoffs.
- Tests at appropriate unit, integration, and property boundaries; reproducible commands and representative fixtures.
- API contract documentation (CLI syntax or OpenAPI/Swagger for HTTP APIs).
- Usable UI or terminal surface for inspecting behavior.
- Security review of input boundaries, memory limits, secrets, and failure modes.
- Empirical profiling/benchmarks where relevant (workload baseline, latency/allocations reported via `benchstat` or `pprof`).
- Clean linting, typing, formatting, and CI integration.

---

## Homer project dashboard

The workspace uses **Homer** as a simple local landing page ([`homer-dashboard`](homer-dashboard/)). It is a navigation layer listing every project, linking to its documentation, and providing a live URL/health link when services run.

---

## Recommended Order

Order reflects prerequisites, conceptual progression, and algorithmic depth:

### Phase 0 — Build language fluency
1. **`go-fundamentals`** — Types, generics, generic binary heap, monotonic stack, circular ring buffer, binary search primitives, thread-safe synchronization (`atomic` vs `mutex`), concurrent worker pipeline with `context`, and benchmarks.
2. **`python-refresh`** — Decorators, context managers, dataclasses, Protocols vs ABCs, generators, typing (`mypy --strict`), `pytest`, and `Hypothesis`.

### Phase 1 — Algorithms in Real Tools (L5 Foundations)
3. **`sudoku-solver`** — Backtracking, constraint propagation, minimum remaining values (MRV) heuristic, property-based invariant testing. *(Python)*
4. **`file-hash-finder`** — Recursive file walking, SHA-256 content hashing, bounded worker pool concurrency, dry-run cleanup. *(Go)*
5. **`file-grepper`** — Grep CLI implementing Naive, KMP failure table, Rabin-Karp rolling polynomial hash, Boyer-Moore skip heuristics, and Aho-Corasick multi-pattern trie. *(Go)*
6. **`graph-lab`** — Package dependency resolver: BFS/DFS (iterative stack), Kahn's topological sort, Lowest Common Ancestor (LCA / merge-base in DAGs), Union-Find/DSU with path compression, Kruskal's MST, Dijkstra with min-heap, and Tarjan/Kosaraju SCC. *(Go)*
7. **`diff-tool`** — File diffing tool implementing LeetCode/L5 dynamic programming: Levenshtein edit distance, LCS sequence reconstruction, Myers divide-and-conquer diff algorithm, and unified diff hunks. *(Python & Go)*
8. **`autocomplete-engine`** — Search autocomplete engine with prefix trie, ranked top-K completions with min-heap, wildcard DFS matching (`?`, `*`), and compressed radix tree. *(Go)*
9. **`stream-analyzer`** — Telemetry stream analyzer: fixed sliding window, monotonic deque for $O(1)$ window peaks, monotonic stack for spike alerts, variable-window error signatures, two-pointer correlation, two-heap running median, and Fenwick tree range index. *(Go)*
10. **`external-sorter`** — Out-of-core big data sorter running under 64 MB RAM: divide-and-conquer run chunking, K-way streaming merge via min-heap, inversion counting, and binary search sparse indexing. *(Go)*
11. **`job-scheduler`** — Cluster task planner: interval sweep-line peak concurrency (Meeting Rooms II), interval merging, binary search on capacity answer space, greedy EDF/SJF with exchange argument proofs, and Weighted Interval DP ($O(N \log N)$) & Knapsack packing. *(Go)*
12. **`bitmap-indexer`** — Columnar attribute search engine implementing 64-bit word-level bitsets, bit isolation (`x & -x`), popcount cardinality, boolean AST query compiler, and double-hashed Bloom filter. *(Go)*
13. **`data-compressor`** — Streaming compression codecs (gzip/zstd), compression ratios, throughput, memory allocation profiling, and Parquet columnar storage. *(Go)*
14. **`profiling-lab`** — Empirical measurement discipline: Go `pprof`, `benchstat`, Python `cProfile`/`tracemalloc`, identifying CPU and heap bottlenecks. *(Go & Python)*
15. **`rate-limiter`** — Concurrency & algorithms bridge: token bucket and sliding window counter library, `sync.Map` per-key tracking, zero data races under `-race`, and HTTP middleware. *(Go)*

### Phase 2 — Web services and persistence
16. **`go-http-server`** — Idiomatic HTTP service, middleware chains, structured logging (`slog`), graceful SIGTERM shutdown, health endpoints, OpenAPI spec. *(Go)*
17. **`postgres-lab`** — PostgreSQL schema design, indexes, isolation levels, transactions, connection pooling, migrations, `EXPLAIN (ANALYZE, BUFFERS)`. *(PostgreSQL & Go/Python)*
18. **`drf-basics`** — Django REST Framework API, serializers, viewsets, authentication, PostgreSQL migrations, OpenAPI schema. *(Python)*
19. **`grpc-service`** — High-performance RPC: Protocol Buffers, unary & server-streaming RPCs, auth & logging interceptors, health probe protocol, REST vs gRPC comparison. *(Go & Python)*

### Phase 3 — Security, identity, network foundations
20. **`crypto-utils`** — Applied cryptography: hashing, HMAC, symmetric encryption (AES-GCM), digital signatures, password hashing (Argon2/bcrypt), threat models. *(Go & Python)*
21. **`tls-setup`** — Local Certificate Authority, X.509 certs, SANs, trust chains, HTTPS, and mutual TLS (mTLS) with handshake inspection. *(Go & OpenSSL)*
22. **`network-tracer`** — Safe local network diagnostics: interfaces, ARP tables, routing, active sockets, and traceroute reachability. *(Go)*

### Phase 4 — Distributed systems and telemetry
23. **`raft-adv`** — Distributed consensus from scratch: leader election, log replication, safety invariants, randomized election timeouts, quorum, Docker network partition and heal tests. *(Go & Python)*
24. **`telemetry-hub`** — Distributed observability: OpenTelemetry SDK, context propagation, tracing across Python API, Go collector, and PostgreSQL. *(Go, Python, OTel)*

### Phase 5 — Caching and event streaming
25. **`redis-cache`** — Cache-aside patterns, TTL/invalidation, Pub/Sub, and Redis Streams consumer groups with acknowledgments. *(Redis, Go, Python)*
26. **`kafka-basics`** — Event streaming with local KRaft: topics, partitions, consumer groups, offsets, idempotency, consumer lag monitoring. *(Kafka, Go, Python)*

### Phase 6 — Identity and platform engineering
27. **`keycloak-setup`** — Enterprise identity: Keycloak container, OIDC/OAuth2 flows, PKCE, JWT token validation, role-based access control. *(Keycloak & Go/DRF)*
28. **`k3s-helm`** — Container orchestration: local k3s cluster, Kubernetes manifests, Helm packaging, liveness/readiness probes, zero-downtime rollouts. *(Kubernetes, Helm)*
29. **`terraform-k3s`** — Infrastructure as Code: Terraform local provisioning, state management, provider configuration, secret handling. *(Terraform)*
30. **`cicd-local`** — Local CI/CD automation: Jenkins/Gitea pipeline-as-code, local container registry, lint/test/build/deploy loop to k3s. *(Docker, Jenkins)*
31. **`homer-dashboard`** — Workspace landing dashboard: central navigation linking documentation, live endpoints, and health status pings. *(Docker, Homer)*

### Optional extension
32. **`packet-tracer`** — Packet capture & dissection on isolated lab network: PCAP analysis, raw sockets (`CAP_NET_RAW`), protocol framing. *(Go & Wireshark)*

---

## Estimated Timeline (at 3–4 hours/day)

| Phase | Projects | Est. Hours (Low) | Est. Hours (High) | Est. Days (3 hrs/day) | Est. Days (4 hrs/day) |
|---|---|---|---|---|---|
| **Phase 0: Language Fluency** | 2 projects (`go-fundamentals`, `python-refresh`) | 16 | 28 | 5–9 days | 4–7 days |
| **Phase 1: Algorithms in Real Tools** | 13 projects (`sudoku-solver` to `rate-limiter`) | 85 | 150 | 28–50 days | 21–38 days |
| **Phase 2: Web & Persistence** | 4 projects (`go-http-server` to `grpc-service`) | 25 | 42 | 8–14 days | 6–11 days |
| **Phase 3: Security & Network** | 3 projects (`crypto-utils` to `network-tracer`) | 14 | 23 | 5–8 days | 4–6 days |
| **Phase 4: Distributed Systems** | 2 projects (`raft-adv`, `telemetry-hub`) | 28 | 49 | 9–16 days | 7–12 days |
| **Phase 5: Caching & Streaming** | 2 projects (`redis-cache`, `kafka-basics`) | 11 | 18 | 4–6 days | 3–5 days |
| **Phase 6: Platform & Identity** | 5 projects (`keycloak-setup` to `homer-dashboard`) | 26 | 44 | 9–15 days | 7–11 days |
| **Total Core Curriculum** | **31 projects** | **205 hrs** | **354 hrs** | **~68–118 days** | **~51–88 days** |

> **Timeline Summary:** At **3–4 hours/day**, the complete curriculum takes approximately **2.5 to 4 months**. Phase 1 (algorithms in real tools) is the core investment (~4–6 weeks), directly preparing you for Google L5 coding rounds with genuine system-level depth.

---

## Working Agreement

At the start of each project milestone:
1. Discuss the algorithmic invariants, edge cases, and design tradeoffs.
2. Formulate test cases and benchmarks before implementation.
3. The learner writes the implementation; guidance acts as a senior peer reviewer asking probing questions about failure modes, complexity bounds, and system behavior.
4. Verify invariants using `-race`, benchmarks, or property tests before moving forward.
