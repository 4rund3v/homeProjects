# Raft Advanced Learning Lab

**Goal:** Learn consensus by implementing Raft incrementally and observing failures in a controlled cluster.

**Scope:** Educational Go Raft nodes, leader election, log replication, Python clients/workers, HTML state visualization, deterministic tests, controlled Docker network partitions.

**Out of scope:** Production-grade persistence, large-scale deployment, and using a Raft library as the implementation. This is a learning system, not production consensus software.

**Learning focus:** Terms, votes, randomized election timeouts, majority quorum, safety invariants, commit index, partition behavior, recovery, and why split-brain leaders do not imply two committed histories.

**Depends on:** `go-fundamentals`, `go-http-server`; `tls-setup` is a later security extension.

## Milestones
- [ ] Read and diagram the Raft state machine and safety properties before coding.
- [ ] Test a single node, then a three-node election with controlled time.
- [ ] Add log replication and client writes through the leader.
- [ ] Visualize node roles, terms, logs, and commit indices.
- [ ] Partition and heal the Docker network; observe quorum and catch-up.
- [ ] Add deterministic/fuzz tests for invariants before security extensions.
