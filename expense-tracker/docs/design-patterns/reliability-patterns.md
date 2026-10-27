# Reliability Patterns — the ones this project actually depends on

> The patterns that keep an async financial pipeline trustworthy. These are the ones
> an interviewer will probe hardest, because they're where the expense→loan flow lives
> or dies. Each one here is *load-bearing*, not decorative.

---

## 1. Transactional Outbox (the most important one)

**Problem:** you must update the database *and* publish an event atomically, but you
can't do both in one transaction (the broker is a different system). Without a
mechanism, you get "expense saved but event lost" → loan never updates.

**The pattern:** in the *same* database transaction as the domain write, write a row to
an `outbox` table holding the event. A **relay** process polls the outbox, publishes
each row to Kafka, and marks it sent. The DB and the event are atomic because they're
one DB transaction; the broker is a separate, retriable step.

```
   with transaction.atomic():
       expense_repo.save(expense)     # the domain fact
       outbox.insert(EventRecord(event_id, topic, key, payload))
   # COMMIT → both persist together, or neither

   relay (separate loop):
       rows = outbox.pending().for_update_skip_locked().limit(N)
       for row in rows:
           kafka.produce(topic=row.topic, key=row.key, value=avro(row.payload))
           outbox.mark_sent(row.id)
```

**The two guarantees this buys:**
1. **Never an expense without its event** — same transaction.
2. **At-least-once, not exactly-once** — if the relay dies after producing but before
   marking sent, it republishes → a *duplicate* event. The consumer must be idempotent
   (next pattern). The outbox trades "exactly-once across two systems" (impossible
   without 2PC) for "atomic locally + at-least-once + idempotent," which is the right
   deal.

**The `FOR UPDATE SKIP LOCKED` detail:** lets multiple relay replicas each grab
disjoint rows without contention. The whole "how do I scale the relay" answer is one
SQL clause.

**Interview question it answers:** *"How do you make 'save to DB and send to Kafka'
atomic without distributed transactions?"* — the outbox. Name it unprompted.

---

## 2. Idempotent Consumer

**Problem:** at-least-once delivery (outbox + Kafka) means a message can be processed
**twice**. For a loan balance, applying a delta twice = a wrong balance.

**The pattern:** give every event a stable `event_id`; on consume, check if it's already
been applied. Enforce it with a **DB unique constraint**, not application logic, so it
survives races:

```
   INSERT INTO processed_events (event_id) VALUES (...)
   -- if it throws unique-violation → already applied → skip, ack, move on
   -- else → apply the balance change
```

**The subtle point:** idempotency must be *in the same transaction* as the effect.
"I did I" is: `BEGIN → check+insert processed_events → apply → COMMIT`, all-or-nothing.

**Why it's load-bearing:** it's what makes **replay-to-rebuild** safe. Replaying the
whole event log to reconstruct a balance is only harmless because re-applying anything is
a no-op. Idempotency turns "replay is dangerous" into "replay is my disaster recovery."

**The `event_id` source:** generate it in the domain (stable across the outbox and the
event envelope), not in the consumer. The consumer derives idempotency from *the
event's* identity, not a fresh one it invents.

---

## 3. Circuit Breaker

**Problem:** a dependency (OAuth provider, schema registry, an external API) is slow or
down. Without protection, every request waits on it → your threads/connections
exhaust → *your whole service* goes down with it.

**The pattern:** wrap the external call in a breaker with three states:

```
   CLOSED   (normal: calls pass through, failures counted)
      │  failure_rate > threshold
      ▼
   OPEN     (all calls fast-fail without touching the dependency)
      │  after a cooldown, try one request
      ▼
   HALF-OPEN (if it succeeds → CLOSED; if it fails → back to OPEN)
```

**Where it applies here:** the **synchronous** external calls — an OAuth token exchange
on login, a schema-registry lookup. The *Kafka* path does NOT need a breaker; it needs
the **outbox** (failures queue, they don't cascade) — that's a different, better
pattern for the async path.

**Pair it always with:** timeouts on the call (a breaker with no timeout is just a
slower failure) and retries *with backoff* only for idempotent calls.

---

## 4. Dead-Letter Queue (DLQ)

**Problem:** a message that *can't* be processed (poison: malformed, a bug, a missing
key). If you retry it forever you block the whole consumer; if you drop it you lose
data.

**The pattern:** after N failed attempts, route the message to a **dead-letter topic**,
alert, and let a human/operator fix it. The main pipeline keeps moving.

```
   consumer → process → fail (retry ×3) → still fails → produce to expenses.dlt + alert
   main pipeline continues with the next message
```

**The discipline:** a DLQ is not a graveyard you forget — it's a queue with an *alert*.
Any sustained DLQ depth is an incident, not a state.

---

## 5. Back-pressure & bounded buffers

**Problem:** if a consumer can't keep up, messages pile up. Where does that pile live,
and what happens when it overflows?

**The pattern:** make the buffer **durable, bounded, and observable**. In this system:
- The **outbox** is the pre-Kafka buffer (bounded by disk, observed by outbox depth).
- **Kafka retention** is the broker-side buffer (bounded by time/bytes, observed by lag).
- **Consumer lag** is the signal that ingress > egress.

The anti-pattern is an *unbounded* in-memory queue that silently grows until OOM.
Every buffer you add should answer: "what caps it, and which metric tells me it's
filling?"

---

## 6. Reconciliation (the correctness backstop)

**Problem:** even with idempotency and ordering, drift accumulates — a bad deploy, a
skipped message, a bug. You need a continuous check that *derived state matches its
source of truth*.

**The pattern:** a scheduled job verifies the invariant:

```
   for each loan:
       expected = sum(balance_changes.delta)
       actual   = loans.outstanding
       if expected != actual:  → ALERT (data integrity) → rebuild
```

**Why it's a pattern and not just a check:** it closes the loop the other patterns
leave open. Idempotency makes *replay* safe; reconciliation *detects when replay is
needed*. They're two halves of one safety net.

---

## The reliability pattern stack, in one picture

```
   ┌─────────────────────────────────────────────────────────────┐
   │  WRITE PATH (API)                                           │
   │   transactional outbox ── atomic DB + event                  │
   ├─────────────────────────────────────────────────────────────┤
   │  RELAY                                                      │
   │   SKIP LOCKED for scaling; durable, bounded buffer (outbox) │
   ├─────────────────────────────────────────────────────────────┤
   │  CONSUMER                                                   │
   │   idempotent (event_id); DLQ on poison; ordered by loan_id   │
   ├───────────────────────────────────────────────────────────────┤
   │  EXTERNAL CALLS                                             │
   │   circuit breaker + timeout + backoff                        │
   ├─────────────────────────────────────────────────────────────┤
   │  WHOLE SYSTEM                                               │
   │   reconciliation: derived state == source of truth            │
   │   back-pressure: outbox depth + consumer lag + retention      │
   └─────────────────────────────────────────────────────────────┘
```

---

## The interview synthesis (memorize this)

*"Design a system where recording an expense must reliably update a loan balance."*

```
  1. Same transaction: write the expense + an outbox row. (outbox)
  2. A relay publishes outbox rows to Kafka, keyed by loan_id. (ordering)
  3. The consumer is idempotent on event_id — replay is safe.
  4. Poison messages go to a DLQ, not retried forever.
  5. External calls are behind a circuit breaker + timeout.
  6. A reconciliation job proves sum(changes)==outstanding; drift triggers replay.
  7. Outbox depth + consumer lag are the two metrics that tell you the pipeline is
     healthy.
```

Every single one of those is a named pattern. That's the L5/L6 answer, and every piece
already exists in this project.

---

## When to skip one

- **Circuit breaker:** not needed for the async Kafka path (outbox handles it); add it
  only for *synchronous* external calls.
- **Saga:** only when a multi-step process spans *services* with compensations. This
  is two steps in one process — outbox + idempotency is enough.
- **Memento/Memento-snapshot:** only if you actually need save/restore of state; not
  needed here.
- **Bulkhead:** worth *learning* (isolating a failing dependency's resource pool so it
  can't exhaust the whole service); not yet needed at this scale, but it's the natural
  next step when you add a flaky external payment API.
