# Kafka Guide — Topics, Retention, Delivery

> Covers the Kafka concepts you named: **topics, retention, delivery semantics,
> partitions**, and how they apply to the expense→loan flow. No code — concepts,
> decisions, and exercises.

---

## 1. The five concepts that explain Kafka

If you understand these, the rest is configuration:

1. **Topic** — an append-only, ordered log of events. Producers append; consumers
   read. You don't "query" a topic; you read it from a position forward.
2. **Partition** — a topic is split into partitions for parallelism. **Ordering is
   guaranteed only within a partition**, not across the topic. This single fact
   drives your keying decisions.
3. **Offset** — a consumer's position in a partition. Committing an offset = "I've
   processed up to here." This is the unit of progress and the source of
   at-least-once/at-most-once behavior.
4. **Consumer group** — a set of consumers sharing the work. Each partition is
   consumed by exactly one member of the group. Add members → more parallelism, up to
   the partition count.
5. **Retention** — how long Kafka keeps messages. Time-based (`retention.ms`),
   size-based (`retention.bytes`), or compaction (`cleanup.policy=compact`). Kafka is
   **not** a permanent store; it's a buffer with a policy.

---

## 2. The core design decision: your keying strategy

Because order is per-partition, **the key determines correctness**, not just
distribution.

For the expense→loan flow, the invariant is: *balance changes for a given loan must
be applied in order.* Therefore:

- **Key every event by `loan_id`** (or by the aggregate whose order matters).
- All events for loan 42 land on the same partition → consumed in order → balance
  updates applied in order.
- If you keyed by `expense_id` or round-robin, two events for the same loan could
  land on different partitions and be applied out of order → a wrong balance.

**Rule of thumb:** *key by the entity whose ordering you must preserve.* That's the
aggregate ID (loan), not the triggering entity (expense). Write this decision down.

**Consequence to plan for:** one very hot loan becomes one hot partition. Accept it
for correctness, or design a finer-grained aggregate if a single loan genuinely has
enormous throughput (it won't here). Correct ordering beats even distribution for
financial state.

---

## 3. Delivery semantics — the trade-off triangle

You must choose, per consumer, where you land:

| Semantics | Offsets committed | Failure behavior | Use when |
|-----------|-------------------|------------------|----------|
| **At-most-once** | before processing | can lose messages | metrics, logs — loss OK |
| **At-least-once** | after processing | can duplicate | financial state — the usual choice |
| **Exactly-once** | transactional (Kafka transactions) | no loss, no dup | hard; needs transactions + idempotent sink |

**For loan balance updates: at-least-once + idempotent consumer.** Reasoning:
- Committing the offset *after* applying the balance means a crash mid-processing
  reprocesses the message → a possible duplicate.
- So you make the consumer **idempotent**: applying `BalanceChange(event_id=X)` twice
  has the same effect as once. Enforce this with a unique constraint on `event_id`
  in the database (a natural idempotency key — ties to
  [`postgres-guide.md`](postgres-guide.md) §2).
- Exactly-once (Kafka transactions) is real but adds operational complexity; learn it,
  but at-least-once + idempotency is the pragmatic enterprise default and it's what
  most payment systems actually do.

**The decision to record:** offsets committed after processing (at-least-once), and
the idempotency key is `event_id` with a DB unique constraint.

---

## 4. The producer side — durability before ack

The producer must not acknowledge success to the API until the event is **durably in
Kafka**, or you get "expense saved but event lost." Use `acks=all` (all in-sync
replicas acknowledge) with a sane `min.insync.replicas`. This is slower than
`acks=1` and correct — for financial events, choose correct.

**The transactional-outbox pattern (learn this — it's the enterprise answer):**
The classic bug is: insert expense in Postgres (commits), then publish to Kafka
(crashes) → expense exists, event doesn't → loan never updates. The fix:

1. In the **same DB transaction** as the expense insert, write a row to an
   `outbox` table (the event, marked unsent).
2. A separate process reads unsent outbox rows, publishes them to Kafka, then marks
   them sent.
3. The consumer applies the balance change idempotently.

This gives you **atomicity between your database and Kafka without distributed
transactions**. It's the pattern to use here. Full flow in
[`event-flows.md`](event-flows.md).

---

## 5. Topics for this project (design, not a list to copy)

You'll converge on a small set. The *reasoning* matters more than the names:

- **One topic per event type** (e.g. an expense-recorded topic, a balance-updated
  topic). Don't dump unrelated events into one topic — schemas and consumers diverge.
- **Naming convention:** `<domain>.<entity>.<event>.<version>`, e.g.
  `expenses.expense.recorded.v1`. Version in the topic name *or* rely on schema
  registry subject versioning — pick one strategy and be consistent (see
  [`avro-guide.md`](avro-guide.md)).
- **Partition count:** start small (e.g. 3–6). Partitions are cheap to add but
  **adding partitions breaks key→partition ordering** (a key that mapped to partition
  2 may map elsewhere after a change). For order-sensitive data, choose your partition
  count deliberately up front. Over-provisioning is not free.
- **Replication factor:** on a single-node k3s you can't replicate. Learn RF=3 for
  production, but accept RF=1 locally and *know that a node loss loses data*. This is
  a "local dev is not prod" lesson worth internalizing.
- **`cleanup.policy`:** `delete` (time/size retention — the default) vs `compact`
  (keep the latest value per key — good for changelog/state topics). For an event
  stream of expenses, `delete`. For a "current loan state" changelog, `compact`.

---

## 6. Retention — the decision you asked about

Retention is a **policy per topic**, driven by "how long might we need to reprocess?"

| Topic type | Suggested policy | Why |
|-----------|------------------|-----|
| Live event stream (expense recorded) | `retention.ms` = days (e.g. 7) | Consumers keep up; only backlog/replay needs history |
| Anything a slow consumer might lag on | longer retention | don't lose data to a lagging consumer |
| State/changelog topics (compact) | `compact` | keep latest per key indefinitely |

**The relationship between retention and archival:** Kafka retention is *short* by
design; long-term history lives in your archival store ([`data-lifecycle.md`](data-lifecycle.md)).
Kafka is a pipe with a memory, not an archive. When retention expires a message you
needed, that's a policy bug — set retention longer than your worst-case reprocessing
window.

**Reprocessing:** with consumer groups, you can reset offsets to replay from a point
in time (if retention allows). This is your disaster-recovery tool: "rebuild loan
balances from the event stream." Design your events so this is possible — which is
exactly why the consumer is idempotent (§3).

---

## 7. Consumer group mechanics & lag

- **Lag** = difference between the latest offset in a partition and the consumer
  group's committed offset. **Lag is your #1 health metric.** Rising lag = consumer
  can't keep up. Alert on it (see [`observability.md`](observability.md)).
- **Rebalancing:** when a consumer joins/leaves, partitions are reassigned. During a
  rebalance, processing pauses. Frequent rebalances = a problem (session timeouts too
  low, slow processing, unstable pods).
- **Scaling:** add consumers up to the partition count; beyond that they idle. So
  partitions cap your parallelism. Balance this against the ordering constraint (§2).
- **Commit cadence:** commit too often = slow; too rarely = large replay on crash.
  Commit after processing a batch, at-least-once.

---

## 8. Local development with Kafka

You don't need a cluster to learn:
- **Docker Compose** with a single-broker Kafka (KRaft mode, no ZooKeeper — modern
  Kafka) is enough for Phase 6–7. Add a schema registry container (see
  [`avro-guide.md`](avro-guide.md)).
- In k3s (Phase 9+), run Kafka via a Helm chart (or a lightweight operator). For a
  learning deployment, a single-broker or 3-broker bitnami/strimzi setup is fine —
  but remember §5's replication caveat on one node.

---

## 9. Exercises (Phase 6–7)

1. **Prove ordering:** key events by `loan_id`, send 100 events for one loan, consume
   and confirm order. Then re-key by `expense_id` and watch order break. *Lesson:
   keying = correctness.*
2. **Prove at-least-once:** commit offsets *after* processing, kill the consumer
   mid-batch, observe reprocessing. Add the idempotency key and watch the duplicate
   become a no-op. *Lesson: delivery semantics.*
3. **Prove the outbox:** comment out the outbox write, crash between DB commit and
   Kafka publish, observe the lost event. Restore the outbox and observe atomicity.
   *Lesson: why the outbox exists.*
4. **Tune retention:** set a short `retention.ms`, produce messages, wait, watch them
   expire. Then try to replay and fail. *Lesson: retention is a policy.*
5. **Watch lag:** throttle the consumer, watch group lag climb in your metrics, then
   unthrottle and watch it drain. *Lesson: lag as a health signal.*

Checkpoints in [`checkpoints.md`](checkpoints.md).

---

## 10. Decisions to record in `design.md`

- Message key (`loan_id`) and the ordering invariant it protects.
- Delivery semantics (at-least-once) and the idempotency key (`event_id`).
- Producer `acks` and replication settings (and the single-node caveat).
- Topic naming and versioning strategy (topic-name version vs registry subject).
- Partition count per topic and why (ordering vs parallelism).
- `cleanup.policy` per topic (delete vs compact).
- Retention per topic, tied to the reprocessing window.
- Whether you use the transactional outbox (yes) and how it's operated.
