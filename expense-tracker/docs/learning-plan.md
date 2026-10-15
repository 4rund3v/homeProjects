# Learning Plan

> Start with the domain, then build a vertical slice, then add reliability and
> operations. Every phase answers: **what am I learning, why now, what do I build,
> how do I know I've learned it?** See [`phases.md`](phases.md) for the hands-on task
> sequence and [`checkpoints.md`](checkpoints.md) for gates.

---

## Learning principles

1. **One concept at a time.** Don't introduce Kafka, Kubernetes, and OAuth in the same
   week. Each phase isolates one new idea; everything else stays simple.
2. **Build vertical slices.** A working end-to-end path beats a "perfect" model in
   isolation. Each phase ends with something you can run and explain.
3. **Write the decision before the code.** For every meaningful choice, write the
   alternatives, why you chose one, and what would make you revisit it. Use
   [`design.md`](design.md).
4. **Learn by breaking it.** Kill the consumer, stop Postgres, expire a token, fill a
   disk. If you haven't seen the failure, you don't understand the recovery.
5. **Infrastructure last, but not too late.** First prove behavior locally; then
   containerize; then deploy. Learning Terraform against an app that changes daily
   just creates churn.
6. **Don't optimize without measurement.** Baseline first, change one thing, measure
   again. See [`postgres-guide.md`](postgres-guide.md) §4.

---

## Dependency order

```
Problem decomposition
        ↓
Python tooling (uv, ruff) → Django + DRF + OpenAPI
        ↓                         ↓
Domain model → Postgres + ORM + migrations
        ↓                         ↓
JWT/Auth → CRUD slice → tests
        ↓
Docker + local services (Postgres, Kafka)
        ↓
Outbox → Avro → Kafka consumer → idempotency
        ↓
Data lifecycle (partition, archive, rebuild)
        ↓
Helm charts → k3s → Terraform → NGINX/Tailscale
        ↓
Observability → runbooks → final walkthrough
```

Auth and Postgres can be learned in parallel once DRF starts; Kafka waits until the
synchronous path works. Infra comes only once you have deployable images.

---

## How much time

The guide is task-sized, not date-sized. A reasonable pace is **one phase per week**
if you have a few hours a week, or 2–3 days per phase if you have more time. Do not
rush through the checkpoints to meet a calendar. The point is retention, not speed.

---

## Before starting (preflight)

- [ ] You can reach your k3s node over Tailscale (already done).
- [ ] Python 3.12+ installed (verify with `python --version`).
- [ ] `uv` installed and you can explain the difference between `uv sync` and
  `uv run`.
- [ ] Docker installed and can run a container.
- [ ] `kubectl` can reach your k3s cluster (you don't need it yet).
- [ ] Git repository initialized in `expense-tracker`.
- [ ] You have read [`domain-decomposition.md`](domain-decomposition.md) and completed
  its exercise on paper.

---

## How to learn `uv` and `ruff` in Phase 0

**uv** replaces the collection of `pip`, `venv`, `pip-tools`, and `pyenv` workflows:
- `uv init` — start a project (understand the files it creates; don't blindly accept).
- `uv add <package>` — declare a dependency; it updates `pyproject.toml` and lockfile.
- `uv sync` — reconcile the environment to the lockfile; deterministic.
- `uv run <command>` — run inside the managed environment without manual activation.
- `uv lock` — update the lockfile deliberately.
- Commit `pyproject.toml` **and** `uv.lock`. Never commit `.venv`.

**ruff** replaces separate formatter + linter + import sorter:
- Configure in `pyproject.toml` (line length, target Python, rule sets).
- Run `ruff check` (lint) and `ruff format --check` (format verification).
- Fix with `ruff check --fix` and `ruff format` — review what they changed.
- Run in pre-commit/CI so it is automatic; never make CI's lint pass by disabling
  rules you don't understand.

**The learning test:** after setup, delete `.venv`, run `uv sync`, and prove the
project comes back exactly. That's reproducibility.

---

## Phase overview

| Phase | New concept | Proof of learning |
|-------|-------------|-------------------|
| 0 — Tooling | uv, ruff, reproducible env | Rebuild env from lockfile |
| 1 — DRF + contracts | request lifecycle, OpenAPI | Endpoint + valid schema |
| 2 — Postgres | schema, constraints, migrations | Violating data rejected by DB |
| 3 — Auth | JWT, ownership, OAuth/OIDC | User A cannot see User B's data |
| 4 — Domain | entities, classes, services | Explain model + invariants |
| 5 — API slice | CRUD + testing | Full expense workflow works |
| 6 — Kafka foundation | topics, Avro, outbox | Event survives API/Kafka failure |
| 7 — Consumer | idempotency, delivery | Restart consumer; no double charge |
| 8 — Lifecycle | partitioning, archival, rebuild | Rebuild balance from events |
| 9 — Helm + containers | packaging, probes | Rolling update and rollback |
| 10 — Terraform | state, plan/apply, providers | Destroy/recreate the cluster stack |
| 11 — Edge | NGINX, Tailscale, limits | Private access + rate limit works |
| 12 — Observability | metrics, logs, dashboards | Trip alerts; use runbooks to recover |

---

## How to use each checkpoint

At the end of a phase, close the docs and answer the checkpoint questions from
memory. If you cannot answer, go back and repeat the exercise — don't advance. The
checkpoints are intentionally a bit uncomfortable; that's how you catch the
"I followed steps but don't understand it" gap.

Track your progress in [`README.md`](../README.md). Use [`milestones.md`](milestones.md)
for the definition of "done."
