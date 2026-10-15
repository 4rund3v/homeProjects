# Checkpoints

> Stop-and-verify gates. Close the docs and answer from memory. If you can't, repeat
> the phase's exercise — don't advance. Each checkpoint maps to a phase in
> [`phases.md`](phases.md).

---

## Phase 0 — Tooling

- [ ] What problem does `uv` solve that `pip` + `venv` + `pyenv` did not?
- [ ] What's the difference between `pyproject.toml` and `uv.lock`, and which do you
      commit?
- [ ] Why is a lockfile the basis of reproducibility? What breaks without it?
- [ ] Name three things `ruff` does that you'd otherwise need separate tools for.
- [ ] You deleted `.venv`. What's the exact command that brings the project back, and
      why does it come back *identically*?

**Gate:** rebuild the environment from the lockfile and prove it works.

---

## Phase 1 — DRF + OpenAPI

- [ ] Trace a request from HTTP to response through the DRF pipeline, naming each stage.
- [ ] Where does authentication happen, and where does authorization happen? Why are
      they different stages?
- [ ] What is a serializer's job, and what should *never* live in one?
- [ ] What makes a generated OpenAPI doc wrong even if it's valid OpenAPI?
- [ ] Which endpoints in your API are public, and why?

**Gate:** render the OpenAPI doc, point at the security scheme, and confirm the health
endpoint is public while the resource endpoint is not.

---

## Phase 2 — Postgres

- [ ] What is MVCC, and what problem does it create? What reclaims it?
- [ ] Why store money as `numeric`, never `float`? What goes wrong with `float`?
- [ ] Why `timestamptz` and not `timestamp`?
- [ ] Name an invariant from your domain and the exact constraint that enforces it.
- [ ] How do you prove an index is being used? What if `EXPLAIN` still shows a seq scan?
- [ ] What does `pg_stat_statements` give you that nothing else does?

**Gate:** insert a constraint-violating row and watch it fail; show an `EXPLAIN
(ANALYZE)` proving an index scan.

---

## Phase 3 — Auth

- [ ] Draw the JWT login → access/refresh → refresh-rotation flow from memory.
- [ ] Why can't you instantly revoke a JWT, and what do you do about it?
- [ ] Why must `user_id` come from `request.user` and never the request body?
- [ ] Why return 404 and not 403 for "exists but isn't yours"?
- [ ] What's the difference between "login with Google" (OIDC) and being an OAuth2
      authorization server? Which are you building?
- [ ] Where do tokens live in the SPA, and what's the trade-off you accepted?
- [ ] How do DRF throttling and NGINX rate limiting differ, and why use both?

**Gate:** with two users, demonstrate the 404-on-other-user's-data behavior and the
ignored spoofed `user_id`.

---

## Phase 4 — Domain

- [ ] List your entities and say which have identity and which are value objects.
- [ ] Name three invariants and the single place each is enforced.
- [ ] Why does behavior live on the entity/service and not the view?
- [ ] Is a credit card a Source subtype or a separate entity? Defend your choice. **(LSP)**
- [ ] Why split into apps on the *second* concept rather than pre-creating them?
- [ ] Where does the UI sit, and what's the only thing it may depend on?
- [ ] **OOP:** name a class and its one reason to change (SRP). Show where a `Money`
      value object removes a duplicated *rule* (DRY-as-knowledge).
- [ ] **Patterns:** what's your **aggregate**, and what invariant defines its boundary?
      Where does a domain service *orchestrate* without stealing an entity's rule?
- [ ] **Architecture:** does your domain layer import any HTTP/Kafka/ORM internals?
      Which dependency did you invert so a rule is testable without Postgres? (DIP)

**Gate:** give a 5-minute verbal walkthrough of your model, boundaries, and the
principles/patterns you applied — defending each decision.

---

## Phase 5 — API slice

- [ ] What's in your error envelope, and why is consistency across endpoints valuable?
- [ ] Cursor vs offset pagination — which did you choose and why?
- [ ] How do you enforce ownership on a list endpoint vs a detail endpoint?
- [ ] What does the generated client buy you over hand-copying types?
- [ ] Which behaviors live in a service rather than a view, and why?
- [ ] **System design:** where is this system **eventually consistent**, and does the
      contract say so honestly? What's the consistency boundary between the expense
      insert and the balance update?

**Gate:** the full expense workflow works through the API; ownership and error tests
pass; the UI client compiles against the generated contract.

---

## Phase 6 — Kafka foundation

- [ ] Why is ordering only guaranteed within a partition? What does that force you to
      key by?
- [ ] Explain the transactional outbox: what atomicity does it buy, and what bug does
      it prevent?
- [ ] Why is the relay a separate process from the API?
- [ ] What does `acks=all` protect against, and what does it cost?
- [ ] Why Avro over JSON on the wire — name two concrete benefits.

**Gate:** stop Kafka, record expenses, restore Kafka, watch the outbox drain; a
round-trip Avro test passes; a breaking schema change is rejected.

---

## Phase 7 — Consumer

- [ ] At-least-once vs at-most-once: where do you commit the offset, and why?
- [ ] What makes the consumer idempotent, and is that enforced in app code or the DB?
- [ ] What happens if the relay crashes between publishing and marking the outbox row
      sent?
- [ ] Why key by `loan_id` and not `expense_id`?
- [ ] What's a poison message and where does it go?

**Gate:** kill the consumer mid-batch; show the balance is not double-applied; show a
poison message in the DLQ.

---

## Phase 8 — Lifecycle

- [ ] Why is `DROP PARTITION` better than `DELETE` for old data?
- [ ] Why must you verify an archive *before* dropping the partition?
- [ ] What's the relationship between Kafka retention and your reprocessing window?
- [ ] Why is "sum of balance changes = balance" a scheduled check and not a constraint?
- [ ] How do you rebuild a drifted balance, and why is it safe?

**Gate:** archive+verify+drop a partition; break a balance and rebuild it from
archived events; reconciliation alerts on injected drift.

---

## Phase 9 — Helm

- [ ] What's the difference between a chart version and an image tag?
- [ ] Why Deployment for the API but StatefulSet for Postgres?
- [ ] What do liveness, readiness, and startup probes each protect against?
- [ ] What does `helm rollback` actually do?
- [ ] Why must infra reference images by tag, never source path?

**Gate:** `helm lint`/`template` clean; a rolling update and a rollback both succeed.

---

## Phase 10 — Terraform

- [ ] What is state, why is it critical, and how do you protect it?
- [ ] What does `terraform plan` show you, and why read every line?
- [ ] What's the difference between a resource and a data source?
- [ ] Why install Helm releases through Terraform's helm provider instead of the CLI?
- [ ] What is drift, and what's the discipline that prevents it?
- [ ] When would you extract a module?

**Gate:** `terraform plan` is clean after you make a manual cluster change (you
understand drift); a full destroy-and-rebuild works.

---

## Phase 11 — Edge

- [ ] What does Tailscale control, and what does NGINX control? Where's the line?
- [ ] Where is TLS terminated, and why there?
- [ ] NGINX rate limiting vs DRF throttling — per-what, and why both?
- [ ] How do you prove the app is reachable over Tailscale and *not* the public
      internet?

**Gate:** private-only access verified; edge rate limiting returns 429; you can explain
the two-layer throttling division.

---

## Phase 12 — Observability

- [ ] What's the difference between metrics, logs, and traces, and when do you reach
      for each?
- [ ] Why alert on consumer lag and not CPU?
- [ ] How do you chart Kafka ingress vs egress, and what does the gap mean?
- [ ] What is the correlation ID and why is it in the event envelope?
- [ ] What's the cache hit ratio, and what does a drop tell you?
- [ ] Why send metrics/traces to Datadog but think twice about logs?

**Gate:** follow one expense from SPA to loan update by correlation ID; every starter
alert has a runbook; you've recovered from one incident via a runbook.

---

## Phase 13 — Hardening

- [ ] What secrets exist in this system and where does each come from?
- [ ] What would you check before committing that no PII leaks into logs?
- [ ] Walk the backup/restore drill for Postgres and the archive.
- [ ] From a fresh clone, list every command to reach a running system.

**Gate:** fresh clone + `uv sync` + `terraform apply` reproduces the running system;
you can give a 15-minute tour.
