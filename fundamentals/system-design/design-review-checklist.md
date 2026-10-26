# Design review checklist

## Problem and contract
- [ ] Define users, workloads, burstiness, data size, and skew.
- [ ] State SLOs for latency, availability, freshness, and durability.
- [ ] Write correctness invariants and externally visible semantics.

## Architecture and data
- [ ] Mark trust boundaries, service ownership, and source of truth.
- [ ] Define keys, partitioning, hot-key behavior, schema evolution, and retention.
- [ ] Explain consistency guarantees at each read and write boundary.

## Failure and overload
- [ ] Walk through timeout, duplicate, reorder, partial completion, partition, and failover.
- [ ] Bound queues and concurrency; define shedding or degradation behavior.
- [ ] Make retries safe with idempotency and bounded backoff.
- [ ] Define backup, restore, replay, reconciliation, and disaster recovery objectives.

## Operations and economics
- [ ] Identify actionable metrics, traces, logs, alerts, and runbooks.
- [ ] Estimate steady-state and peak resource use, including replication and egress.
- [ ] Explain capacity headroom, scaling limits, and saturation behavior.
- [ ] Review abuse, authorization, data exposure, and resource-exhaustion risks.

## Decision quality
- [ ] Compare at least one viable alternative.
- [ ] Name the assumption that would change the decision.
- [ ] Add a test or experiment that could falsify the design.
