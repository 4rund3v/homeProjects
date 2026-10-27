# Event-Driven Architecture — in Depth

> The whole async spine of this system, explained end-to-end: topics, consumer groups,
> the outbox that makes publishing atomic, schema evolution, and the consistency model
> that comes with going event-driven.

---

## 1. Why event-driven, and what it costs you

```
   SYNCHRONOUS CALL                         EVENT-DRIVEN
   ─────────────────                        ────────────
   API ──directly──► loan updater           API ──publish──► topic ──consume──► loan updater
   one system knows about the other         two systems meet at a contract

   ✓ simple, immediate                     ✓ decoupled: the API doesn't know a
   ✗ the API blocks on the whole thing         loan-updater exists
   ✗ can't add a second reacter without       ✓ durable: the event outlives the call
      editing the API                        ✓ independently deployable
   ✗ a slow loan update slows the API         ✗ eventual consistency (balance lags)
```

Going event-driven buys decoupling, durability, and independent deployment. It costs
you **eventual consistency** and an operational surface (lag, DLQ, retention). That
trade *is* the decision. It's the right one here because the loan update is not on the
user's critical path and because a second consumer (analytics, alerts) will be trivial.

---

## 2. The topic layout

```
   producer (outbox relay)                    consumer (loan updater)
   ───────────────────────                    ────────────────────────
   topic: expenses.v1                         consumer group: loan-updaters
   key:    loan_id                            (order preserved per loan_id)
   value:  Avro ExpenseRecorded               offset committed after DB write

   ┌──────────────┐   ┌──────────────┐
   │  partition 0 │   │  partition 1 │        ← consumer groups split partitions
   │  loan 7, 42  │   │  loan 43, 91 │        between members; one member per
   └──────────────┘   └──────────────┘              partition
```

**The keying rule that makes correctness real:** key by the **aggregate id**
(`loan_id`), so all events for one loan land on one partition and are consumed in
order. Key by `expense_id` and two expenses on the same loan can be applied out of
order → wrong balance. See
[`kafka-guide.md`](../kafka-guide.md) §2.

---

## 3. The transactional outbox (the part that makes it atomic)

The naive "write expense, then produce to Kafka" fails: crash between the two →
expense without event. The outbox fixes it:

```
   with transaction.atomic():
       expense_repo.save(expense)
       outbox_repo.enqueue(EventRecord(event_id, topic, key, payload))   # same txn

   relay (separate process):
       rows = outbox.pending_for_update_skip_locked().limit(N)
       for row in rows:
           kafka.produce(topic=row.topic, key=row.key, value=avro(row.payload))
           outbox.mark_sent(row.id)          # after the produce succeeds
```

**Why this beats direct production:**
- **Atomicity** — the event and the expense are one DB transaction. No dual-write bug.
- **Durability before publish** — the event survives the API process; the relay can
  retry indefinitely.
- **Back-pressure is natural** — if Kafka is down, outbox rows accumulate; the relay
  drains when it recovers. The API never blocks on the broker.

**The cost:** eventual consistency between "expense saved" and "balance updated" —
documented in the API contract ([`api-contracts-guide.md`](../api-contracts-guide.md) §5).

---

## 4. Consumer groups and scaling

```
   consumer group "loan-updaters":  3 members, 6 partitions
   ┌──────────────────────────────────────────────────────┐
   │ member 1 ──► partition 0, 3                          │
   │ member 2 ──► partition 1, 4                          │
   │ member 3 ──► partition 2, 5                          │
   └──────────────────────────────────────────────────────┘
   Add a 4th member → partitions REBALANCE (one per member, no more)
   Throughput ceiling = partition count. More consumers than partitions = idle.
```

**Lag is the #1 health metric:** lag = (latest offset in partition) − (committed
offset of the group). Rising lag = consumers falling behind. Alert on it
([`observability.md`](../observability.md) §5).

---

## 5. Schema evolution (the Avro half)

Events are **contracts**, not free-form JSON. A schema registry + Avro gives you:

- **Compatibility checks at registration** — a breaking change (removing a field)
  is *rejected* before it reaches a topic.
- **Versioned subjects** — `expenses.v1-value`, `expenses.v2-value`, coexisting during
  a migration.
- **Wire-format stability** — producer and consumer use the *same* schema id, so a
  new producer doesn't emit a shape an old consumer can't read.

**The evolution rule:** design for *additive* changes (new optional fields with
defaults). Breaking changes get a **new topic version** (`expenses.v2`), run both in
parallel, then retire v1. See [`avro-guide.md`](../avro-guide.md) §5.

---

## 6. The consistency model, made explicit

```
   ┌────────────────────────────────────────────────────────────────┐
   │  STRONG within one transaction:                                 │
   │    expense + outbox row commit together                          │
   │                                                                 │
   │  EVENTUAL across the async boundary:                             │
   │    balance updates *after* the expense is recorded              │
   │    window = outbox relay lag + consumer processing time          │
   │                                                                 │
   │  ORDERED per loan_id (partition key)                            │
   │  IDEMPOTENT per event_id (unique constraint) → replay is safe    │
   └────────────────────────────────────────────────────────────────┘
```

**The discipline:** never *pretend* the balance is updated when the API returns 201.
The honest contract is "expense recorded, balance updating." If a client must see the
fresh balance, it polls a read endpoint (or a projection) — that's the light-CQRS move
([`../architecture-patterns.md`](../architecture-patterns.md)).

---

## 7. Event-driven vs. a plain API call (the comparison to keep straight)

| Concern | Plain sync call | Event-driven |
|---------|-----------------|--------------|
| Coupling | API knows the loan-updater | meet at a contract |
| Failure | one slow thing stalls the API | outbox absorbs it |
| Adding a reacter | edit the API | add a consumer (trivial) |
| Consistency | immediate | eventual (bounded) |
| Replay | not a concept | offset reset / rebuild |

---

## 8. How this shows up here

- **The producer** writes to the outbox (in the expense transaction); the **relay**
  moves outbox rows to the `expenses.v1` topic.
- **The consumer** is the loan-updater, keyed by `loan_id`, idempotent on `event_id`.
- **The contract** is honest about the eventual-consistency window.
- **The second consumer** (spend analytics / budget alerts) slots in without touching
  the API — that's the payoff.
- See the full flow in [`event-flows.md`](../event-flows.md).
