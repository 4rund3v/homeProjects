# Raft Advanced Learning Lab

## What this project exists to solve
Understand distributed consensus by implementing Raft from scratch in Go and observing its behaviors — elections, replication, safety violations, and partition effects — in a controlled local cluster. Python worker nodes exercise the API surface. A browser UI makes system state visible.

## Success criteria / completion metrics
- Three-node Raft cluster in Go that elects a leader and replicates client writes under normal conditions.
- Controlled Docker network partitions and recoveries; observed behaviors match Raft's safety/liveness guarantees.
- Deterministic tests for election and replication invariants.
- Python worker nodes that submit work to the leader and observe committed results.
- HTML status page visualizing node role, term, log, commit index, and worker activity.
- mTLS milestone is optional and explicitly decoupled from core correctness.
- Local CI gates format, vet, tests, and image build; cluster runs locally via Docker Compose or equivalent.

## Prerequisites and dependencies
- `go-fundamentals`, `go-http-server` (status API, logging, graceful shutdown).
- `tls-setup` cert helpers are an optional later milestone.
- `network-tracer` for context on how partitions look at the OS level.
- `profiling-lab` discipline before any performance optimization.

## Tools, libraries, and runtime
- Go toolchain; standard library preferred for learning.
- Python workers via `uv` (see `../uv-setup.md`).
- Docker Compose or equivalent for multi-node local cluster.
- Local CI for Go tests and images; Python tests via `uv` for workers.
- Optional: basic JS for status page; do not add a framework.

## Learning objectives (skills practiced)
- Raft subprotocols: election, log replication, safety, and why each is necessary.
- Why randomized election timeouts prevent persistent split votes.
- Majority quorum, commit index, and why minority partitions cannot commit.
- Why "leader exists" is a liveness property and "only one leader can commit" is a safety property; how these relate to split-brain.
- Deterministic testing: mocked time, channel-based transport, and invariant checks.
- Network partitions: observing unavailability, stale reads, log divergence, and catch-up.
- mTLS as a later security extension, not a prerequisite for correctness.

## Architecture / design note
```
cmd/node/main.go           # one binary; port and node ID configured
internal/
  raft/                    # Raft state machine
    state.go
    election.go
    replication.go
    log.go
    transport.go            # interface over HTTP or in-process channels
  server/
    api.go                  # client + worker API
    status.go               # status page data
    html/                   # minimal status page template
pkg/
  types/                   # term, index, entry types shared across packages
docker/
  Dockerfile
  compose.yaml
python-workers/
  worker.py                 # submit work, observe result
tests/
  integration/              # Docker-based cluster tests
  unit/                     # deterministic transport tests
```

Key design decisions to make explicitly:
- Transport: in-process channels for unit tests; HTTP over Docker network for integration. The transport is a boundary; design for testability.
- Persistence: in-memory log is acceptable for learning; explain what real Raft adds (fsync, WAL, snapshot).
- Time: deterministic clocks in tests; wall clock in integration. Mocking time is essential for election tests.
- mTLS: optional and decoupled. Add only after core correctness is proven; it should not influence the correctness tests.

## Test strategy
- Deterministic unit tests for: election with 1, 2, 3 nodes; log replication; safety (committed entries are not lost); leader step-down.
- Integration tests with Docker Compose: start cluster, elect leader, write, partition, heal, verify commit.
- Python worker integration: submit work, observe result, observe behavior under partition.
- Negative tests: network partitions that would break an incorrect implementation; document which invariants each test exercises.

## Documentation checklist
- `README.md` with architecture, setup, and how to run the cluster.
- `NOTES.md` with invariant list, safety/liveness discussion, and observed failure modes.
- Architecture decision notes for each major design choice and its tradeoff.
- Status page explanation: what each field means and how to read it during a partition.

## API contract
- Worker API: submit work, query status, observe committed results.
- Status API: node role, term, log length, commit index, peer state.
- Errors documented: not leader, not committed, partition detected.

## UI / status surfaces
HTML status page served by the shared service patterns; visualize role, term, log, and commit index. Visualization should be the primary debugging surface — it is the reason to build this from scratch.

## Security boundaries to think about
- mTLS between Raft nodes is an optional security milestone; it is not required for correctness and should be implemented only after the core is stable.
- Validate worker input; reject malformed or oversized entries.
- The status page shows internal state; do not expose it on a public interface by default.
- Do not simulate attacks; focus on correctness and observability.

## Profiling plan
Profile only when the cluster is correct and a performance question arises (e.g., throughput under load, latency of commit). Do not profile before correctness. Use `profiling-lab` methodology.

## How this project fits into the curriculum
This is the capstone. It combines Go concurrency, HTTP services, deterministic testing, container orchestration, and Python interop. `network-tracer` provides OS-level context for the same partitions. `keycloak-setup` and `tls-setup` are later extensions.

## Suggested milestone walkthrough
1. **Paper + design.** Read the Raft paper. Draw state machines. Explain election, replication, and safety back before writing code.
2. **Single-node no-op.** Heartbeat and no-op entries; prove the node is stable.
3. **Three-node election.** Randomized timeouts; deterministic tests with mocked time; visualize via HTML.
4. **Log replication.** Client write goes to leader; followers apply; commit index advances.
5. **Controlled partition.** Partition with Docker network controls; observe minority unavailability, stale reads, and split-brain leader perception. Document that multiple leaders can be perceived but only one can commit.
6. **Heal and recover.** Heal the network; observe log divergence and catch-up; confirm committed entries are preserved.
7. **Python workers.** Submit work from Python; observe committed results and behavior under partition.
8. **Deterministic tests.** Prove Raft invariants under mocked transport and time; include a fuzz-style randomized test if feasible.
9. **Optional mTLS.** Add cert-based authentication between Raft nodes using `tls-setup`'s cert package; explain why mTLS does not replace Raft's consensus guarantees.
10. **Container + CI.** Docker image for each node; local CI runs Go tests; Python worker tests run via `uv`.

## Reference notes and resources
- Ongaro and Ousterhout, "In Search of an Understandable Consensus Algorithm" (Raft paper).
- Raft visualization: raft.github.io for intuition.
- `go test` subtest, race detector, and deterministic clock patterns.
- Docker networking and `iptables` for partition simulation.
