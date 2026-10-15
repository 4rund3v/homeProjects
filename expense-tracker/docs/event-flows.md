# Event Flows

> The detailed end-to-end trace of the async flow, with failure modes and the
> reconciliation loop. [`architecture.md`](architecture.md) §2–3 gives the shape;
> this is the drill-down, including what happens when things go wrong.

---

## 1. Flow 1 — Record an expense (synchronous, transactional)

```
                ┌─────────────┐
   POST /expenses/ │  DRF view   │
                  └──────┬──────┘
                         │ validate + auth (JWT + ownership)
                         ▼
                  ┌────────────────────────┐
                  │  ExpenseService.record │
                  │  BEGIN transaction     │
                  │   1. build Money VO    │
                  │   2. INSERT expenses   │
                  │   3. INSERT outbox     │
                  │   4. COMMIT            │
                  └────────────┬───────────┘
                               │
                  ┌────────────▼───────────┐
                  │ return expense to SPA  │
                  │ (202: recorded, queued)│
                  └────────────────────────┘
```

**Invariant:** the `expenses` row and the `outbox` row commit or both roll back.
There is no crash point between them. If Kafka is down, the outbox still fills; the
relay publishes later. The API never blocks on Kafka.

**Outbox row shape (concept):** `id`, `event_id`, `topic`, `key`, `payload`, `sent_at`,
`attempts`, `created_at`. `event_id` is unique and stable — it's the same idempotency
key the consumer uses.

---

## 2. Flow 2 — Publish the event (outbox relay)

```
     ┌──────────────────┐
     │  Outbox relay    │   (separate process; can be a CronJob or a loop)
     │  loop:           │
     │  1. SELECT unsent rows (FOR UPDATE SKIP LOCKED)
     │  2. serialize payload → Avro (lookup schema by id)
     │  3. publish (key=loan_id, acks=all)
     │  4. UPDATE sent_at = now()
     │  on error: increment attempts, back off, keep retrying
     └──────────────────┘
```

**`FOR UPDATE SKIP LOCKED`:** lets multiple relay replicas each grab distinct rows
without contention. Standard outbox pattern.

**Why a separate process:** the API must return fast and never fail because Kafka is
slow. Pushing to Kafka is best-effort and retried independently. This separation is
the whole point of the outbox pattern.

**Failure modes:**
- *Kafka down:* outbox rows accumulate unsent; they publish when Kafka returns. Bounded
  by disk, not by API latency. Watch outbox depth as a metric.
- *Poison message (bad payload):* cap `attempts`, then route to a **dead-letter
  topic** and alert. Never block the loop forever on one row.
- *Relay crash between publish and UPDATE:* the same row republishes → a duplicate
  event. The **consumer is idempotent**, so this is harmless. Design the consumer for
  this; don't fight it.

---

## 3. Flow 3 — Consume and update the loan (asynchronous)

```
     ┌──────────────────────────────┐
     │  Consumer (loan updater)     │   consumer group, keyed order by loan_id
     │  for each event:             │
     │  1. deserialize (Avro, via registry)
     │  2. idempotency: seen event_id? → ack & skip
     │  3. BEGIN transaction        │
     │     a. INSERT balance_change  (unique on event_id)  ← idempotency
     │     b. UPDATE loans SET outstanding = outstanding - amount
     │     c. COMMIT                │
     │  4. commit Kafka offset (AFTER db commit)          │
     └──────────────────────────────┘
```

**The two invariants this flow protects:**
1. **Ordering:** key by `loan_id` → same partition → applied in order
   ([`kafka-guide.md`](kafka-guide.md) §2).
2. **Idempotency:** `event_id` unique constraint on `balance_changes` → applying an
   event twice is a no-op ([`kafka-guide.md`](kafka-guide.md) §3).

**Offset commit after DB commit:** at-least-once. A crash after DB commit but before
offset commit → the event is reprocessed → the unique constraint makes it a no-op. A
crash before DB commit → the event is simply reprocessed normally. Both paths are
safe. Committing *before* the DB commit would be at-most-once and could silently lose
a balance update — never do that for financial state.

**Idempotency scope:** `event_id` must be globally unique per topic, and the unique
constraint must cover it. This is a **DB constraint**, not just app logic — see
[`postgres-guide.md`](postgres-guide.md) §2.

---

## 4. Flow 4 — Reconciliation & rebuild (the self-healing loop)

```
     ┌──────────────────────────────┐
     │  Scheduled reconciliation     │   (CronJob)
     │  for each loan:               │
     │    expected = sum(balance_changes)
     │    actual     = loans.outstanding
     │    if drift → ALERT           │
     └──────────────────────────────┘
        │
        ▼  on drift
     ┌──────────────────────────────┐
     │  Rebuild: reset loan state,   │
     │  replay events from archive/  │
     │  stream, re-apply idempotently│
     └──────────────────────────────┘
```

**Why this exists:** eventually every distributed system accumulates drift — a bad
deploy, a missed message, a bug. Rather than trusting state forever, you *verify* it
continuously against the source of truth (the events).

**Rebuild works because:**
- Events are the source of truth; balances are a projection
  ([`data-lifecycle.md`](data-lifecycle.md) §5).
- The consumer is idempotent → replay is safe.
- Archived events cover the full history ([`data-lifecycle.md`](data-lifecycle.md) §3).

This loop is your **drift detector and your disaster recovery**. It's also a great
learning exercise: break a balance on purpose, watch reconciliation alert, then rebuild
and confirm recovery.

---

## 5. Failure-mode summary table

Memorize this. It's the whole operational model of the async path.

| Failure | Where it shows | Recovery |
|---------|----------------|----------|
| API crash after COMMIT | nothing — it's committed | none needed |
| Kafka down | outbox accumulates | relay catches up on recovery |
| Relay crash mid-publish | duplicate event | consumer idempotency absorbs it |
| Poison message | relay stuck on a row | DLQ + alert + manual fix |
| Consumer crash mid-event | offset not committed | event reprocessed, idempotent |
| Consumer deployed with bad schema | consumer can't read | rollback, or schema compat enforced (see [`avro-guide.md`](avro-guide.md)) |
| Loan balance drift | reconciliation alert | rebuild from events |
| Kafka retention expires | lost messages | retention policy too short; extend it |

**The design principle behind every row:** *make failures cheap and recoverable, not
impossible.* You can't prevent crashes; you make them harmless via the outbox,
idempotency, and reconciliation.

---

## 6. Exercises (Phase 7)

1. **Trace the happy path** end-to-end with logs at each hop. Prove the outbox row and
   the expense insert are atomic (kill the API after commit, confirm the outbox fills).
2. **Stop Kafka**, record expenses, confirm they're queued but not updated. Restart
   Kafka and watch the relay drain the outbox.
3. **Kill the consumer mid-batch**, confirm the event is reprocessed and the balance
   is not double-applied. *Lesson: at-least-once + idempotency.*
4. **Inject a poison message**, watch it route to the DLQ and the loop continue.
5. **Break a balance**, run reconciliation, watch it alert, then rebuild from events
   and confirm recovery. *Lesson: the self-healing loop.*

Checkpoints in [`checkpoints.md`](checkpoints.md).
