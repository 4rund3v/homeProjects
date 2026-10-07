# Engineering Learning Curriculum

A step-by-step, hands-on curriculum for strengthening Python, becoming proficient in Go, and understanding backend, distributed-systems, security, data, and platform engineering. This is a learning workspace: the learner designs and implements each milestone; assistance should coach through reasoning and tradeoffs, not hand over full answers unless explicitly requested.

## Learning goals and constraints

- Python: refresh modern language features, OOP/design patterns, decorators, typing, testing, Django and Django REST Framework.
- Go: build from fundamentals to idiomatic services, concurrency, configuration, profiling, and systems tooling.
- Systems: PostgreSQL, Redis cache and Streams, Kafka, observability, Raft consensus, TLS/mTLS, applied cryptography, network diagnostics, Kubernetes, Helm, Terraform, and Keycloak (required).
- Use Docker/local environments wherever practical; avoid requiring cloud accounts or paid services.
- Treat each project as production-minded engineering practice, not a claim that a small local learning app is production-ready.

## Definition of done for each project

Each project README should track its scope and milestones. For each milestone, aim to include, as relevant:

- A concise architecture/design note, setup/run instructions, configuration reference, operational notes, and lessons/tradeoffs.
- Tests at the appropriate unit, integration, and end-to-end boundaries; reproducible commands and representative fixtures.
- API contract documentation (OpenAPI/Swagger for HTTP APIs), examples, and versioning/error semantics where relevant.
- A usable homepage or status UI for projects with a human-facing surface; no frontend is required for CLI-only projects.
- Security review of input boundaries, secrets, permissions, and failure behavior.
- Profiling/measurement where relevant: define a workload first, capture a baseline, report resource/latency/throughput measures, and explain what the profile does and does not prove. Do not add profiling overhead to every tiny milestone just to check a box.
- Formatting, linting, static analysis, dependency review, and CI only after the underlying behavior is understood.
- Containerization and local CI/CD where relevant: if a project is deployable, it should eventually build as a container, run tests in a pipeline, and be deployable to the local k3s cluster. Jenkins is the recommended hands-on local CI tool because it runs locally, is free, and is widely used in enterprises. GitHub Actions or GitLab CI are acceptable alternatives. The goal is to see a local push → build → test → deploy loop; no cloud account is required.

“Enterprise-level” here means high-quality design, testing, documentation, security awareness, operational thinking, and reproducible delivery at a manageable local scale. It does not mean every project needs a distributed production deployment, microservices, or a large framework.

## Homer project dashboard

The workspace will use **Homer** as a simple local landing page. It is a navigation layer, not an application framework: it lists every project, links to that project's documentation, and gains a live URL/status link when the project exposes one.

- Documentation link: always present, points to the project's `README.md` or `Project.md`.
- Application link: added only when the project actually runs an HTTP/UI surface.
- Status link: added when the project exposes a health/status endpoint.
- CLI/infrastructure-only projects: documentation link remains the primary entry; do not invent a web UI just to populate Homer.
- Homer configuration belongs in a future `homer-dashboard/` directory and should be updated as projects become runnable.

## Recommended order

Order reflects prerequisites and reuse. Work one milestone at a time; revisit earlier projects when later work reveals a gap.

### Phase 0 — Build language fluency

**1. `go-fundamentals`** — Go types, structs, methods, interfaces, errors, packages/modules, `context`, goroutines/channels, synchronization, standard library, table-driven tests, race detector, and benchmarks. Deliver a few small tested packages and a concurrent pipeline. Tools: Go toolchain, `go test`, `go vet`, `gofmt`.

**2. `python-refresh`** — Decorators, context managers, dataclasses, ABCs vs. protocols, generators, typing, pytest, Hypothesis. Build small reusable exercises and compare design alternatives. Tools: Python, pytest, mypy, ruff, Hypothesis.

### Phase 1 — Algorithms and focused tools

**3. `sudoku-solver`** — Backtracking, constraint propagation, graph-coloring perspective, invariants and property-based testing. CLI first; profile only after a correct baseline. Tools: Python, pytest, Hypothesis, `cProfile`/`pyinstrument`.

**4. `file-hash-finder`** — Go directory traversal, file metadata, hashing, configuration, bounded concurrency, safe dry-run cleanup. Tools: Go stdlib filesystem and crypto APIs, tests, race detector, benchmarks.

**5. `data-compressor`** — Compare gzip and selected codecs; study Parquet separately as a columnar file format. Measure correctness, ratio, throughput, allocations, and memory. Tools: Go, benchmark suite, `pprof`, codec/Parquet libraries selected during design.

**6. `profiling-lab`** — Focused, reusable practice in profiling Python and Go CPU, heap/allocations, goroutines, and latency. Establish workload and baseline; form a hypothesis; profile; make one change; compare. Tools: Go `pprof`, `benchstat`, Python `cProfile`/`pyinstrument`/`tracemalloc`, optional `perf` where available.

### Phase 2 — Web services and persistence

**7. `go-http-server`** — Go HTTP service with middleware, structured logs, validated config, graceful shutdown, health/readiness checks, and documented API. Include a small status homepage. Tools: `net/http`, optionally `chi`, `slog`, OpenAPI tooling if the API grows, `go test`, `pprof` when a measurable workload exists.

**8. `postgres-lab`** — PostgreSQL from schema design through indexes, transactions, isolation, migrations, query plans, connection pooling, backup/restore basics. Build a small documented service/API only as needed to exercise database behavior. Tools: PostgreSQL in Docker, `psql`, migrations, `EXPLAIN (ANALYZE, BUFFERS)`, Go `database/sql` and Python driver/ORM comparisons.

**9. `drf-basics`** — Django/DRF API with serializers, viewsets, authentication, PostgreSQL, migrations, tests, and OpenAPI/Swagger documentation. Include browsable API; focus on API contract and ORM behavior rather than a large frontend. Tools: Django, DRF, pytest, PostgreSQL, drf-spectacular, mypy/ruff where suitable.

### Phase 3 — Security, identity, network foundations

**10. `crypto-utils`** — Understand hash/MAC, symmetric and public-key encryption, digital signatures, password hashing, randomness, and safe library use through small experiments. Never invent production cryptography. Tools: Go `crypto` and Python standard/library APIs; test vectors and threat-model notes. JWT/JWS is learned in context, not confused with encryption.

**11. `tls-setup`** — Local CA, X.509 certificates, SANs, trust chains, HTTPS and mTLS using Go; inspect handshakes and verify failure cases. Document trust/key assumptions. Builds on `go-http-server`; informs Raft's optional mTLS milestone. Tools: Go `crypto/tls`/`crypto/x509`, OpenSSL CLI, curl.

**12. `network-tracer`** — Safe local network diagnostics: interfaces, routes, neighbor/ARP entries, active sockets, and traceroute-style reachability. Add a status homepage only after the CLI is correct. Observe Docker networks and relate connectivity to Raft experiments. Tools: Go, OS network interfaces, `ip`/`ss`/`traceroute` as available. No broad scanning or packet capture in this project.

### Phase 4 — Distributed systems and telemetry

**13. `raft-adv`** — Implement Raft from scratch in Go (no consensus library): leader election, replication, safety tests, Python clients/workers, HTML status visualization, controlled Docker partitions and recovery. Start with paper/state-machine reasoning; keep persistence and scale explicitly out of the first learning version. Document APIs and invariants. Tools: Go tests with controlled time/transport, Docker Compose, Python, browser UI; optional mTLS after core correctness. Split-brain discussion must distinguish multiple perceived leaders from multiple committed histories.

**14. `telemetry-hub`** — Python API + PostgreSQL, a Go OpenTelemetry collector/pipeline, and a local log destination. Trace a request across API and database; show useful service/status pages. Document API with OpenAPI. Tools: Python web stack, PostgreSQL, OpenTelemetry SDK/OTLP, Go, syslog-compatible local sink, Docker Compose. Learn logs, metrics, traces, context propagation, and basic profiling of a defined workload.

### Phase 5 — Caching and event streaming

**15. `redis-cache`** — Go and Python clients; cache-aside, TTL/invalidation, pub/sub, and Redis Streams consumer groups. Integrate cache with DRF only after isolated behavior is tested; compare reliability semantics with Kafka. Tools: Redis in Docker, `redis-py`, `go-redis`, metrics for hit ratio/latency.

**16. `kafka-basics`** — Local single-node KRaft, topics, keys/partitions, producers, consumer groups, offsets, retries, lag, idempotent processing. Use Go and Python clients and optionally feed telemetry events. Tools: Kafka-compatible local container, client libraries, CLI inspection tools. Document delivery guarantees precisely; no unsupported “exactly once” claims.

### Phase 6 — Identity and platform engineering

**17. `keycloak-setup`** — Required identity project: local Keycloak, OIDC/OAuth flows, PKCE, roles/scopes, JWKS/token validation, and API integration with DRF or Go. Include documented auth flows and a simple protected-resource homepage where useful. Tools: Keycloak container, DRF/Go service, curl/browser, OpenAPI security schemes.

**18. `k3s-helm`** — Deploy understood services to local k3s; learn Kubernetes resources, probes, config/secrets, rollouts, resource limits, Helm charts and debugging. Deploy telemetry and Keycloak only after their local versions work. Tools: k3s, kubectl, Helm, Docker.

**19. `terraform-k3s`** — Learn Terraform by provisioning reproducible local infrastructure and configuring a local k3s environment where the chosen provider supports it. Treat provider limits explicitly; Terraform may provision the local VM/network while Helm or Kubernetes providers manage cluster resources. Tools: Terraform/OpenTofu, a local virtualization provider (e.g. libvirt if available), k3s, Helm. Keep state local and secrets out of version control; no cloud account required.

### Optional extension — packet-tracer

After safe local diagnostics, learn packet capture and protocol dissection on an isolated lab network only. This is distinct from Raft's partition simulation. Requires deliberate OS capabilities (often `CAP_NET_RAW`); begin with supplied PCAP files before live capture. Tools: Go pcap bindings, Wireshark/tshark, container capability controls. No capturing third-party traffic.

## Reuse map

| Learn/build first | Reuse later |
|---|---|
| Go fundamentals: errors, contexts, tests, bounded concurrency | All Go projects |
| Profiling lab: measurement discipline and tool literacy | Compressor, HTTP/API services, telemetry, Raft |
| Go HTTP service patterns | TLS server, network status UI, Raft status/API |
| PostgreSQL fundamentals | DRF and telemetry-hub persistence |
| DRF API/testing conventions | Keycloak-protected Python API; telemetry API |
| TLS and cryptographic primitives | Optional Raft mTLS and Keycloak token validation concepts |
| Network diagnostics | Understanding Docker links and Raft partition experiments |
| Redis Streams and Kafka comparison | Telemetry/event-ingestion extensions |
| Local k3s + Helm | Terraform-managed local infrastructure and deployed apps |

Reuse should follow demonstrated need: understand a component in its original project first, then extract or reuse it. Avoid creating a shared library prematurely.

## Repository structure

Each numbered project has a folder with a `README.md` containing goal, scope/non-goals, prerequisites, chosen tools, architecture/API/UI surfaces, milestones, test strategy, documentation checklist, and profiling plan where relevant. Implementation starts only when the learner chooses that project and milestone.

Current directories:

1. `go-fundamentals/`
2. `python-refresh/`
3. `sudoku-solver/`
4. `file-hash-finder/`
5. `data-compressor/`
6. `profiling-lab/`
7. `go-http-server/`
8. `postgres-lab/`
9. `drf-basics/`
10. `crypto-utils/`
11. `tls-setup/`
12. `network-tracer/`
13. `raft-adv/`
14. `telemetry-hub/`
15. `redis-cache/`
16. `kafka-basics/`
17. `keycloak-setup/`
18. `k3s-helm/`
19. `terraform-k3s/`
**20. `packet-tracer/` (optional extension)

Each project directory includes `README.md` (brief orientation) and `Project.md` (the in-depth learning specification). Python project environment setup is standardized in [`uv-setup.md`](uv-setup.md).

## Working agreement

At the start of each project, first discuss the relevant concepts and tradeoffs. Then define a small milestone and its acceptance criteria together. The learner writes the implementation; assistance should ask guiding questions, review, and explain implications. Do not move to the next milestone just because code runs: the learner should be able to explain its invariants, abstractions, failure modes, and tests.

No implementation code is generated by this curriculum update. The next step is to review this order and adjust scope before beginning project 1.
