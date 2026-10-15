# Phases

> The build sequence. Each phase names **what to learn**, links the guide that
> teaches it, and lists **what to build** and **what "done" means**. Work top to
> bottom; verify at each checkpoint ([`checkpoints.md`](checkpoints.md)).

Legend: 📖 = read first · 🔨 = build · ✅ = done when

---

## Phase 0 — Tooling & environment

📖 [`learning-plan.md`](learning-plan.md) §"How to learn uv and ruff"

🔨 Build:
- Initialize the project with `uv`; commit `pyproject.toml` and `uv.lock`.
- Configure `ruff` in `pyproject.toml`; run `ruff check` and `ruff format`.
- Add a pre-commit hook that runs `ruff check` and `ruff format --check`.
- Install and verify Docker; run a hello-world container.
- Write a one-paragraph `docs/design.md` entry on why uv + ruff and your chosen
  ruff rule set.

✅ Done when: you delete `.venv`, run `uv sync`, and the project rebuilds identically;
`ruff check` passes with zero warnings; pre-commit blocks a deliberately bad file.

---

## Phase 1 — DRF skeleton + OpenAPI

📖 [`drf-jwt-guide.md`](drf-jwt-guide.md) §1–2 · [`api-contracts-guide.md`](api-contracts-guide.md)

🔨 Build:
- A Django project + first app; DRF installed.
- One `ModelViewSet` for a throwaway resource to exercise the pipeline.
- Health and readiness endpoints (no auth).
- OpenAPI generation wired (drf-spectacular or your chosen tool), served at a dev URL.
- A CI step that validates the generated schema.

✅ Done when: `/healthz` returns 200 with no token; the OpenAPI doc renders in a
browser; the schema validator passes in CI; you can explain the request lifecycle from
[`drf-jwt-guide.md`](drf-jwt-guide.md) §1 without looking.

---

## Phase 2 — Postgres + ORM + migrations

📖 [`postgres-guide.md`](postgres-guide.md) §1–4, §7 · [`data-model.md`](data-model.md)

🔨 Build:
- Postgres running (local via Docker for now).
- A settings module that reads all config from the environment.
- Models for the first two entities (e.g. User is provided by Django; add Category and
  Expense) with **every invariant as a DB constraint**.
- Initial migration, generated and committed.
- Indexes for your first two query patterns; verify with `EXPLAIN (ANALYZE, BUFFERS)`.
- Enable `pg_stat_statements`.

✅ Done when: you can insert a constraint-violating row and watch Postgres reject it;
`EXPLAIN` shows an index scan (not a seq scan) for your main query; a migration applies
cleanly on a fresh DB.

---

## Phase 3 — Authentication (JWT + OAuth2/OIDC)

📖 [`drf-jwt-guide.md`](drf-jwt-guide.md) §3–6

🔨 Build:
- JWT auth (simplejwt or chosen lib): login → token pair; `/token/refresh`.
- Wire the auth class + `IsAuthenticated` onto the resource endpoints.
- Social login via one provider; exchange the verified provider token for your own JWT.
- Throttling: strict on login, per-user on the API.
- Reflect the security scheme + per-operation auth in the OpenAPI contract.
- Decide and document token lifetimes and SPA token storage.

✅ Done when: two users exist; user A gets **404** for user B's resource; a spoofed
`user_id` in the request body is ignored; login throttling returns 429 under load;
the OpenAPI security scheme is correct.

---

## Phase 4 — Domain decomposition & core entities

📖 [`domain-decomposition.md`](domain-decomposition.md) (do the exercise first) · [`oop-principles.md`](oop-principles.md) · [`design-patterns.md`](design-patterns.md) §Domain patterns · [`architecture-patterns.md`](architecture-patterns.md) §Layered, §DDD · [`project-structure-guide.md`](project-structure-guide.md) §1–3

🔨 Build:
- Complete the domain-decomposition exercise on paper; write answers into
  `docs/design.md`.
- Split into Django apps per domain concept (the second concept triggers the split —
  don't pre-create six apps).
- Value objects for Money and any other multi-field values; wire them into models.
- Services that own the behavior; keep views thin.
- The aggregate boundary (Loan + BalanceChanges) enforced — the Loan is the only way in
  ([`design-patterns.md`](design-patterns.md) §Aggregate).
- The domain layer importing no HTTP/Kafka/ORM internals (layered + DIP,
  [`architecture-patterns.md`](architecture-patterns.md), [`oop-principles.md`](oop-principles.md)).
- The UI sibling folder with a generated starter (no real features yet).

✅ Done when: you can point at each app and say what it owns in one sentence; every
invariant maps to exactly one enforcement point; no business rule lives in a view; the
domain layer imports no framework; the UI folder exists and its only dependency on the
backend is the (future) contract.

---

## Phase 5 — Full API slice + tests

📖 [`api-contracts-guide.md`](api-contracts-guide.md) · [`drf-jwt-guide.md`](drf-jwt-guide.md) · [`system-design.md`](system-design.md) §Consistency

🔨 Build:
- Full CRUD for Expenses, Categories, Sources, Loans — with consistent pagination,
  filtering, and error envelope.
- The `Money`/currency handling end-to-end.
- Ownership enforced on every endpoint (queryset + object-level).
- Tests: endpoint tests (auth, validation, pagination, errors, ownership) and service
  tests (business rules, no HTTP).
- Generated TypeScript client for the UI; UI calls real endpoints.

✅ Done when: the full expense workflow works through the API; tests cover the
ownership and error paths; the UI client compiles against the generated contract and
can list/create an expense.

---

## Phase 6 — Kafka foundation: outbox, Avro, producer

📖 [`kafka-guide.md`](kafka-guide.md) · [`avro-guide.md`](avro-guide.md) · [`event-flows.md`](event-flows.md) §1–2

🔨 Build:
- Kafka (KRaft) + schema registry locally (Docker Compose).
- The `outbox` table; write to it in the same transaction as the expense insert.
- An outbox relay process: `FOR UPDATE SKIP LOCKED`, serialize to Avro, publish
  (key = `loan_id`, `acks=all`), mark sent.
- The first `.avsc` schema; register it; round-trip test.
- CI: schema registration + compatibility check.

✅ Done when: recording an expense writes an outbox row atomically; stopping Kafka
queues events and they publish on recovery; a round-trip test produces and consumes a
real event; a breaking schema change is rejected.

---

## Phase 7 — Consumer + idempotency

📖 [`event-flows.md`](event-flows.md) §3 · [`kafka-guide.md`](kafka-guide.md) §3, §7

🔨 Build:
- The consumer: consume, deserialize, idempotency check on `event_id`, apply balance
  change in one transaction, commit offset **after** the DB commit.
- The unique constraint on `event_id` (DB-enforced idempotency).
- Dead-letter handling for poison messages.
- Ordering proof (key by `loan_id`).

✅ Done when: killing the consumer mid-batch reprocesses without double-applying a
balance; out-of-order keying demonstrably breaks ordering (so you understand why the
key matters); a poison message lands in the DLQ without stalling the loop.

---

## Phase 8 — Data lifecycle: partition, archive, rebuild

📖 [`data-lifecycle.md`](data-lifecycle.md) · [`postgres-guide.md`](postgres-guide.md) §6

🔨 Build:
- Partition the event/expense tables by time range.
- The archival job: detach → export (Parquet) to PVC → **verify** → drop.
- The reconciliation check (sum of changes = balance) as a scheduled job.
- The rebuild path: reset and replay from archive to recover a drifted balance.
- The retention policy table, filled in and automated.

✅ Done when: an old partition is archived, verified, and dropped; you break a balance
and rebuild it from archived events; reconciliation alerts on injected drift; the
archive job is observable.

---

## Phase 9 — Containers + Helm

📖 [`infrastructure.md`](infrastructure.md) §3–4

🔨 Build:
- Dockerfiles for API, consumer, relay, and a static build for the UI; push to a
  registry.
- A Helm chart per deployable, with `values.yaml` per environment.
- Liveness/readiness/startup probes; resource requests/limits.
- Rolling update and rollback demonstrated.

✅ Done when: `helm lint` and `helm template` are clean; a rolling update and a
`helm rollback` both work; images are referenced by tag, not source path.

---

## Phase 10 — Terraform provisioning

📖 [`infrastructure.md`](infrastructure.md) §1–2, §8

🔨 Build:
- Terraform with pinned providers; remote (or protected local) state.
- Namespaces, storage class, secrets structure via Terraform.
- Foundational Helm releases installed via the `helm` provider: ingress-nginx,
  Postgres, Kafka + registry, observability agents.
- Environments via variable files.

✅ Done when: `terraform plan` is clean after a manual cluster change (you understand
the drift); you can `terraform destroy` and rebuild the stack; every applied change
went through a reviewed plan.

---

## Phase 11 — Edge: NGINX + Tailscale

📖 [`infrastructure.md`](infrastructure.md) §5

🔨 Build:
- Ingress routing: `/api` → API, `/` → UI, `/metrics` restricted.
- TLS termination at the edge; cert-expiry alerting.
- Rate limiting at NGINX (per-IP), alongside DRF per-user throttling.
- Security headers, body-size limits, timeouts.
- Private access verified over Tailscale only.

✅ Done when: the app is reachable over Tailscale and not from the public internet;
rate limiting returns 429 at the edge; you can explain the NGINX vs DRF throttling
division.

---

## Phase 12 — Observability & runbooks

📖 [`observability.md`](observability.md) · [`runbooks.md`](runbooks.md)

🔨 Build:
- `postgres_exporter` + a Postgres dashboard; find your slowest query.
- Kafka dashboards: **lag, ingress, egress, latency**; throttle the consumer and watch
  lag climb.
- Structured logs with a correlation ID propagated into the event envelope.
- The starter alert set; trip each alert on purpose; write its runbook.
- Decide Datadog vs Grafana+Prometheus (or both) and document the trade-off.

✅ Done when: you can follow one expense from SPA to loan update by its correlation
ID; every starter alert has a runbook; you've recovered from at least one real incident
using the runbook.

---

## Phase 13 — Hardening & final walkthrough

📖 all guides · [`milestones.md`](milestones.md)

🔨 Build:
- Security review: no secrets committed, no PII in logs, ownership everywhere,
  CORS tight.
- Backup/restore drill for Postgres and the archive.
- A full destroy-and-rebuild drill from Terraform.
- Write the top-level README walkthrough: how to run the whole thing from zero.

✅ Done when: a fresh clone + `uv sync` + `terraform apply` reproduces the running
system; you can give a 15-minute tour explaining every boundary and decision.
