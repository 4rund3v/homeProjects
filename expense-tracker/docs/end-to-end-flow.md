# End-to-End Flow Walkthrough

> One expense, traced through **every component**, from the user's click to long-term
> archival and dashboards. This is the "movie" of the whole system once all phases are
> built. Each step names the component, what it does, why, and which failure it
> survives. Component details live in the linked guides.

---

## The cast of components

| # | Component | Role | Built in |
|---|-----------|------|----------|
| 1 | React UI (LLM-generated) | records the expense; never touches the DB | out of scope |
| 2 | Tailscale + NGINX Ingress | private network path in; load balancing, rate limiting | Phase 11 |
| 3 | Django/DRF API (Gunicorn) | validates, authenticates, applies domain rules, writes DB | Phases 1–5 |
| 4 | Postgres (+ PgBouncer) | durable source of truth: expenses, loans, **outbox** | Phases 2–3 |
| 5 | Outbox relay | moves committed outbox rows to Kafka | Phase 6 |
| 6 | Schema registry | stores/validates the `ExpenseRecorded` Avro schema | Phase 6 |
| 7 | Kafka (+ KRaft) | durable, ordered event log keyed by `loan_id` | Phase 6 |
| 8 | Kafka consumer | idempotent loan-balance updater | Phase 7 |
| 9 | Dead-letter topic | isolates poison events for inspection | Phase 7 |
| 10 | Archival job | moves old events to PVC-backed cold storage | Phase 8 |
| 11 | Helm / k3s | runs all of the above as pods, reproducibly | Phases 9–10 |
| 12 | Datadog / dashboards | metrics, logs, traces, Kafka health | Phase 12 |

**The journey, in one line:**
`UI → Ingress → API → Postgres (expense + outbox, one txn) → relay → registry → Kafka → consumer → Postgres (balance) → metrics → archive`

---

## Step 0 — Before any of this: the environment is up

You deployed with `terraform apply` (Phase 10), which provisioned the k3s node and
kicked off `helm install` (Phase 9) for each component. So when the request arrives:

- **NGINX Ingress controller** is running, routing by host/path.
- **API pods** are behind a Service, scaled and ready.
- **Postgres** runs as a StatefulSet with a PVC; **PgBouncer** pools connections to it.
- **Kafka** runs (in-KRaft mode) with a PVC; **topics pre-created** (`expenses.v1`,
  `expenses.v1.dlt`).
- **The consumer** runs as a Deployment in a consumer group; **the relay** runs
  alongside the API (same image, `RELAY_ENABLED=1`).
- **Tailscale** gives you a private route to the node's Ingress from your machine.
- **Datadog agent** runs as a DaemonSet, scraping every pod.

All of this is described as code (Terraform + Helm), so the environment is reproducible
— you can tear it down and rebuild it identically
([`infrastructure.md`](infrastructure.md)).

---

## Step 1 — The user records an expense

In the React UI, you fill in: **$42.50**, category *Groceries*, source *Amex Gold*,
today's date. The UI calls:

```
POST /api/v1/expenses/
Authorization: Bearer <access-token>
Idempotency-Key: 8f3c...            (optional; lets the UI retry safely)
{
  "amount": "42.50",
  "currency": "USD",
  "category_id": "…",
  "source_id": "…",                 // the Amex card
  "spent_at": "2026-10-14T18:30:00Z"
}
```

The UI knows nothing about the database or Kafka. Its only contract is OpenAPI
([`api-contracts-guide.md`](api-contracts-guide.md)), and its client was generated from
the API's spec — so if the contract drifts, the UI build fails, not production.

**Why this matters:** the UI↔API boundary is the one seam that lets you regenerate the
frontend freely without touching the backend.

---

## Step 2 — The request enters through the edge

The packet leaves your laptop over **Tailscale** (encrypted mesh VPN, Phase 11), lands
on the node, and hits **NGINX Ingress**:

- **TLS termination** at the edge.
- **Rate limiting** (per-IP, coarse): a burst from one IP is throttled here, before it
  can consume app resources.
- **Load balancing** across API pod replicas (round-robin/least-conn).
- **Routing** by host/path to the `api` Service.

**Two layers of rate limiting exist on purpose:** NGINX protects the *infrastructure*
(per-IP, blunt); DRF throttling protects the *domain* (per-user, semantic)
([`drf-jwt-guide.md`](drf-jwt-guide.md) §6). You need both; neither replaces the other.

---

## Step 3 — The API authenticates and validates

Inside the **Django/DRF** pod:

1. **Auth middleware** validates the **JWT** (signature, expiry, `aud`) — no DB hit,
   it's stateless ([`drf-jwt-guide.md`](drf-jwt-guide.md) §4).
2. **Permission check** — the user must own the source they're spending from.
3. **Serializer validation** — amount is a valid positive decimal, category and source
   exist, currency is supported.
4. **Throttling** — the user's per-minute limit is checked (the semantic layer).

If any of this fails, a structured error comes back with a consistent envelope and the
right status code (400/401/403/429) — and it's documented in OpenAPI, so the generated
UI client handles it.

**The design note:** the view stays thin. It parses, delegates, and renders. It does not
contain business rules ([`architecture-patterns.md`](architecture-patterns.md)).

---

## Step 4 — The domain logic runs

The view calls **`ExpenseService.record_expense(...)`** (a domain service,
[`design-patterns.md`](design-patterns.md)). This is where the *rules* live:

- **`Money` value object** is constructed — amount + currency, with arithmetic that
  refuses to mix currencies. This is where "you can't add USD to EUR" is enforced, once,
  as knowledge ([`oop-principles.md`](oop-principles.md)).
- **The invariant is checked** — a valid expense has a positive amount, a category, a
  source owned by the user. Each invariant has exactly one enforcement point
  ([`domain-decomposition.md`](domain-decomposition.md) §3).
- **The Loan aggregate is consulted** — is this source linked to a credit account? If so,
  the balance must be updated, so an event is warranted.

The service returns an **`Expense`** entity and a decision: *publish an event or not*.
It has **no idea** Kafka exists — that's a detail for the layer above
([`oop-principles.md`](oop-principles.md), DIP).

---

## Step 5 — One transaction: expense + outbox

Now the critical step. Inside **`transaction.atomic()`**:

```python
with transaction.atomic():
    expense = expense_repo.save(expense)          # the expense row
    outbox_repo.save(                              # the event row, SAME transaction
        event_id=new_uuid(),
        topic="expenses.v1",
        key=str(loan_id),                          # the Kafka key
        value=serialize_expense_recorded(expense), # canonical JSON/Avro payload
        produced_at=now(),
    )
```

**This is the heart of the reliability design** ([`event-flows.md`](event-flows.md) §2).
The expense and its event commit **together or not at all**. There is no distributed
transaction, no two-phase commit — just one Postgres transaction that writes two tables.

**What this buys you:**
- If the API crashes *after* this commit → the event is safely in the outbox, waiting.
- If Kafka is *down* → doesn't matter; the event is already durable in Postgres.
- There is **no window** where an expense exists without its event. The classic
  dual-write bug is gone.

---

## Step 6 — The API responds immediately

The API returns `201 Created` with the expense representation and a
`Location` header. **The response does not wait on Kafka** — publishing is asynchronous
by design. This keeps the API's latency budget tight and available
([`system-design.md`](system-design.md)).

**The honest contract:** the response means *"expense recorded; the loan balance is
updating."* Not *"everything is done."* The eventual-consistency window is documented in
OpenAPI ([`api-contracts-guide.md`](api-contracts-guide.md) §5), not hidden — because
right now, the balance is ~seconds stale, and pretending otherwise is a lie that will
surface as a bug report.

---

## Step 7 — The relay publishes to Kafka

A **relay** process (Phase 6) is polling the outbox:

```sql
SELECT * FROM outbox
WHERE published_at IS NULL
ORDER BY produced_at
FOR UPDATE SKIP LOCKED           -- multiple relay replicas won't double-publish
LIMIT 100;
```

For each unpublished row:

1. **Fetch/verify the schema** from the **schema registry** by subject
   `expenses.v1-value`. The registry checks compatibility on registration — a breaking
   change is *rejected* here, not discovered in prod
   ([`avro-guide.md`](avro-guide.md) §5).
2. **Serialize** the payload with that schema (Avro, binary).
3. **Produce** to Kafka topic `expenses.v1`, keyed by `loan_id`, `acks=all` (durability:
   don't ack until replicas have it).
4. **Mark published** — `UPDATE outbox SET published_at=now() WHERE id=...`.

**If the relay dies mid-loop:** some rows are published, some aren't. On restart, it
re-reads unpublished rows. A row published-but-not-marked will be **republished** →
a **duplicate** event. That's fine, because Step 9 makes the consumer idempotent.
The whole design assumes duplicates are possible and handles them
([`kafka-guide.md`](kafka-guide.md) §3).

**Back-pressure in action:** if Kafka is slow, unpublished rows pile up in the outbox.
The API is unaffected (it never waited). **Outbox depth becomes a first-class metric** —
when it climbs, you know egress < ingress ([`system-design.md`](system-design.md)).

---

## Step 8 — Kafka stores the event, ordered

Kafka appends the message to topic `expenses.v1`, partition chosen by
`hash(loan_id) % partition_count`.

**Why the key is `loan_id` (not the expense id):** all events for the *same loan* land
on the *same partition*, and Kafka guarantees ordering **within a partition**. So the
balance changes for one loan apply **in the order they happened** — no out-of-order
corruption ([`kafka-guide.md`](kafka-guide.md) §2). The partition count is also your
consumer-parallelism ceiling, set with that in mind
([`kafka-guide.md`](kafka-guide.md) §5).

Kafka stores it durably (replication factor, `min.insync.replicas`) for the **retention
period**, which you set longer than your worst-case reprocessing window
([`kafka-guide.md`](kafka-guide.md) §6).

---

## Step 9 — The consumer applies it, idempotently

The **consumer** (Phase 7), part of consumer group `loan-updaters`, is assigned the
partition holding our event. It polls, deserializes (schema-aware), and processes:

```python
def handle(event):                       # event: ExpenseRecorded
    with transaction.atomic():
        # 1. Idempotency gate — the unique constraint is the real guard
        try:
            ProcessedEvent.objects.create(event_id=event.event_id)
        except IntegrityError:
            return                        # already applied → no-op

        # 2. Apply through the aggregate — the invariant stays in the domain
        loan = loan_repo.get_for_update(loan_id=event.loan_id)   # row lock
        loan.apply_expense(event.amount, event.currency)         # domain rule
        loan_repo.save(loan)                                     # outstanding updated
        BalanceChange.objects.create(...)                        # the audit trail
```

**Three things make this correct:**

1. **Idempotency key** — the `processed_events` unique constraint on `event_id` means a
   redelivery is a no-op ([`kafka-guide.md`](kafka-guide.md) §3). This is what turns
   Kafka's at-least-once delivery from a hazard into a feature (safe replay).
2. **Row lock** — `SELECT ... FOR UPDATE` serializes concurrent events for the same
   loan, so `outstanding` never races ([`postgres-guide.md`](postgres-guide.md) §1).
3. **Domain rule in the aggregate** — the balance update logic lives on `Loan`, not in
   the consumer, so it's testable without Kafka
   ([`architecture-patterns.md`](architecture-patterns.md)).

**Offset commit happens *after* the DB transaction commits.** If the consumer crashes
between DB write and offset commit, the event is reprocessed — and the idempotency gate
makes that harmless.

**Poison message?** If an event fails repeatedly (bad data, a bug), after N attempts it
goes to the **dead-letter topic** `expenses.v1.dlt`, and an alert fires. The pipeline
keeps moving; the bad message is quarantined for inspection
([`kafka-guide.md`](kafka-guide.md) §4).

---

## Step 10 — The balance is now updated

`loans.outstanding` reflects the new expense. This is a **projection** — the true source
of truth is the `balance_changes` log. That framing is deliberate: it means you can
**rebuild** the balance by replaying the log, which is your disaster-recovery path
([`data-lifecycle.md`](data-lifecycle.md) §5). The loan balance caught up a few seconds
after the expense was recorded — that's the eventual-consistency window, made real.

---

## Step 11 — The whole thing is observable, continuously

At every step, signals are emitted (Phase 12):

- **API:** request rate, error rate, latency percentiles (RED method,
  [`observability.md`](observability.md) §3). Every log line carries the
  **correlation ID**.
- **Relay:** outbox depth, publish rate, publish errors.
- **Kafka:** consumer group **lag**, ingress/egress rates, under-replicated partitions.
- **Postgres:** connections (via PgBouncer), query latency, cache hit ratio, replication.
- **Edge:** NGINX request rate, 429s, upstream latency.
- **Traces:** the correlation ID threads the API request → outbox → produced event →
  consumed event, so one expense is traceable end-to-end across the async boundary.

**Dashboards** show the Kafka health you specifically asked about — streams/ingress,
consumer lag, processing latency, egress — alongside the domain dashboards (spending by
category/source, loan balances) ([`observability.md`](observability.md) §5).

**Alerts** fire on the signals that mean "act now": consumer lag climbing, outbox depth
rising, DLQ non-empty, error rate spiking ([`observability.md`](observability.md) §4).
Silence is not success — a monitor that only watches the happy path misses the crash.

---

## Step 12 — Time passes; data ages and gets archived

Months later, this expense is historical (Phase 8):

- **Expenses table is partitioned by month** ([`postgres-guide.md`](postgres-guide.md)
  §6), so old data lives in old partitions.
- An **archival job** moves events older than the hot window to **PVC-backed cold
  storage** (e.g. Parquet on a mounted volume / object storage), **verifying** the copy
  before dropping the hot partition ([`data-lifecycle.md`](data-lifecycle.md) §3).
- The **rebuild path** still works: because balances are projections over
  `balance_changes`, and the log is retained (Kafka retention > reprocessing window,
  plus archives), you can replay to reconstruct state
  ([`data-lifecycle.md`](data-lifecycle.md) §5).
- A **reconciliation job** periodically checks `sum(balance_changes) == outstanding`
  and alerts on drift — the continuous correctness check
  ([`data-lifecycle.md`](data-lifecycle.md) §5).

---

## The failure matrix — what survives what

This is the payoff of the whole design. Each row is a real failure and the mechanism
that absorbs it:

| Failure | What happens | Mechanism |
|---------|--------------|-----------|
| API pod crashes after commit | nothing lost | expense + event already committed |
| Kafka down for 10 minutes | API keeps accepting expenses | **outbox** queues durably |
| Relay crashes mid-publish | some events republished | **idempotent consumer** absorbs dupes |
| Consumer crashes after DB write, before offset commit | event reprocessed | idempotency gate → no-op |
| Poison message | quarantined, pipeline continues | **dead-letter topic** + alert |
| Balance drift detected | reconstruct from event log | **rebuild-by-replay** |
| Old data bloats the DB | hot window stays fast | **partitioning + archival** |
| Bad deploy | previous release restored | **Helm rollback** |
| Node dies | **outage** (single node) | backups + documented caveat |
| Schema breaking change | rejected at registration | **registry compatibility** |

Read the table top to bottom: the design's whole personality is **"fail safely and
recover fast,"** not "never fail" ([`system-design.md`](system-design.md)).

---

## What to notice about this flow

A few principles recur, and they're the real curriculum:

- **The async boundary is drawn deliberately** — the API responds without waiting on
  Kafka, trading a few seconds of balance staleness for availability and decoupling
  ([`system-design.md`](system-design.md) §Consistency).
- **Durability comes before speed** — `acks=all`, commit-after-DB-write, retention >
  reprocessing window. Every one of those is a dial set toward not-losing-money-events
  ([`system-design.md`](system-design.md)).
- **The domain is the center** — services and entities own the rules; views, consumers,
  and relays are thin adapters around them ([`architecture-patterns.md`](architecture-patterns.md)).
- **Idempotency is the keystone** — it's what lets you safely retry, replay, and rebuild.
  Almost every reliability row above rests on it.
- **Observability is designed in** — the correlation ID and outbox-depth metric exist
  *because* the async boundary would otherwise be invisible.
- **Everything is reproducible** — Terraform + Helm mean this entire movie can be torn
  down and re-run identically ([`infrastructure.md`](infrastructure.md)).

---

## Checkpoint: can you narrate this yourself?

Walk the flow aloud without the doc. For each step, be ready to answer:

1. Why does the API **not** wait on Kafka? What's the cost?
2. What guarantees the expense and its event commit **together**? Why is that better
   than publishing after the response?
3. Why is the Kafka key `loan_id` and not `expense_id`?
4. A duplicate `ExpenseRecorded` arrives. Walk exactly what stops a double balance
   update.
5. The consumer crashes *after* the DB write but *before* the offset commit. What's the
   outcome, and why is it correct?
6. Kafka retention expires while a consumer is 3 days behind. What's lost, and how do
   you prevent it?
7. Where is this system **eventually consistent**, and where is it strongly consistent?
8. Name the metric that tells you the pipeline is backing up *before* users notice.
9. The loan balance is wrong. How do you prove whether it's drift, and how do you fix it
   without losing data?
10. Which single component, if it died, causes a user-visible outage today — and what
    would it take to change that?

If you can answer these, you understand the system as a whole — not just the parts.

---

## Decisions to record in `design.md`

- The consistency posture and how the contract communicates the async window.
- The outbox schema, relay concurrency, and `FOR UPDATE SKIP LOCKED` choice.
- The Kafka key, partition count, and the reasoning linking them.
- The idempotency mechanism (unique constraint on `event_id`) and DLQ policy.
- The retention window vs reprocessing window, and how you verified retention > window.
- The archival trigger, verification step, and the rebuild-by-replay procedure.
- The single-node availability limitation and your documented stance on it.
