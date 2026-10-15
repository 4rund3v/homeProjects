# Milestones

> Coarser than phases — these are the "you can now do X" moments. Each bundles
> phases into a capability you can demonstrate. Phases are in
> [`phases.md`](phases.md); the gates are in [`checkpoints.md`](checkpoints.md).

---

## M1 — A reproducible Python project
**Phases:** 0
**You can:** create a deterministic, linted Python project with `uv` + `ruff` that any
machine can rebuild from the lockfile.
**Demonstrate:** delete `.venv`, `uv sync`, run tests — identical result.
**Unlocks:** everything else sits on this base.

---

## M2 — A working, documented REST API
**Phases:** 1, 2
**You can:** stand up DRF with a real Postgres schema, constraints, migrations, and a
validated OpenAPI contract.
**Demonstrate:** a constraint violation rejected by the DB; `EXPLAIN` proving an index;
the OpenAPI doc rendering.
**Unlocks:** auth, the domain slice, and eventually the container build.

---

## M3 — A secured API with real ownership
**Phases:** 3, 5
**You can:** authenticate with JWT, log in socially, enforce per-user ownership, and
expose a consistent, tested, paginated API with a generated client.
**Demonstrate:** user A gets 404 on user B's data; a spoofed `user_id` is ignored; the
UI client compiles and works against the contract.
**Unlocks:** the domain logic has a secure front door; Kafka can trust the data.

---

## M4 — A modeled, defensible domain
**Phase:** 4
**You can:** decompose the problem into entities, value objects, invariants, and
boundaries — and defend every decision.
**Demonstrate:** the 5-minute verbal walkthrough; every invariant mapped to one
enforcement point.
**Unlocks:** everything downstream inherits correct boundaries. (Cross-cutting — proves
M2 and M3 are built on solid ground.)

---

## M5 — A reliable event pipeline
**Phases:** 6, 7
**You can:** record an expense durably, publish an Avro event through a transactional
outbox, and consume it idempotently to update loan balances — surviving Kafka and
consumer failures.
**Demonstrate:** stop Kafka → queue drains on recovery; kill the consumer mid-batch →
no double-applied balance; poison message → DLQ.
**Unlocks:** the async core of the system works and is trustworthy.

---

## M6 — A self-healing data lifecycle
**Phase:** 8
**You can:** partition, archive, verify, and drop old data, and rebuild state from
archived events.
**Demonstrate:** break a balance → reconciliation alerts → rebuild from archive →
recovered.
**Unlocks:** bounded storage growth *and* a disaster-recovery path. This is the
"enterprise" data-operations milestone.

---

## M7 — A deployable, packaged system
**Phases:** 9, 10
**You can:** containerize every component, package it with Helm, and provision the
whole stack reproducibly with Terraform.
**Demonstrate:** `terraform destroy` + rebuild from scratch; a Helm rolling update and
rollback.
**Unlocks:** the system exists on your k3s cluster, not just your laptop.

---

## M8 — A privately accessible, protected edge
**Phase:** 11
**You can:** expose the system over Tailscale with TLS, load balancing, and layered
rate limiting — and nowhere else.
**Demonstrate:** reachable on the tailnet, unreachable publicly; edge 429s working.
**Unlocks:** real access control; you can use it from your devices.

---

## M9 — An observable, operable system
**Phases:** 12, 13
**You can:** see metrics/logs/traces across the async boundary, trip alerts on
purpose, and recover using runbooks; back up and restore; and rebuild everything from
a fresh clone.
**Demonstrate:** follow one expense end-to-end by correlation ID; recover from an
incident via runbook; fresh clone → running system.
**Unlocks:** you can operate, not just build, the system.

---

## The end state

When all nine are done you have, more importantly than the app itself:

- **Domain modeling** — you can break a fuzzy problem into defensible entities and
  boundaries.
- **DRF + JWT + Postgres hands-on** — you can build and secure a real REST API against
  a real database and *reason* about both.
- **Event-driven thinking** — outbox, Avro, idempotency, retention, and reconciliation
  are tools you understand, not incantations.
- **Infrastructure fluency** — Terraform's plan/state/drift loop, Helm packaging, k3s
  primitives, and the edge layer are no longer magic.
- **Operations** — you can observe, alert, runbook, back up, and rebuild.

That skill set — not the expense tracker — is the deliverable. The app is just the
thing you broke and rebuilt enough times to earn it.
