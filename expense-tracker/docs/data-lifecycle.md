# Data Lifecycle — Records, Events, Cleanup, Archival

> Answers the question you asked directly: **what happens to records and events over
> time — when do we keep them, move them, and delete them?** This is where Postgres
> ([`postgres-guide.md`](postgres-guide.md)), Kafka
> ([`kafka-guide.md`](kafka-guide.md)), and storage meet.

---

## 1. The principle: data has a lifecycle, not a permanent home

Every piece of data is born **hot**, cools to **warm**, and eventually goes **cold**
or is **deleted**. The mistake is treating the primary database as the permanent home
for everything. It isn't — it's the hot tier. Design the tiers deliberately.

| Tier | What lives there | Storage | Access pattern | Cost |
|------|------------------|---------|----------------|------|
| **Hot** | active loans, current expenses, recent events | Postgres (indexed) | constant, low-latency | high |
| **Warm** | older events still occasionally queried | Postgres (less indexed) or archive | rare, tolerant | medium |
| **Cold** | historical events, audit trail | PVC-backed files / object storage | almost never, restorable | low |
| **Streaming buffer** | recent events in flight | Kafka (short retention) | replay/reprocess | transient |

The transitions between tiers are **policies**, and policies must be explicit,
automated, and observable — never ad-hoc `DELETE`s.

---

## 2. Map your data to tiers

For this project, decide per entity (record answers in [`design.md`](design.md)):

**Expenses**
- Hot: the current user's recent expenses (the default query).
- Warm: older expenses, still queryable for reports.
- Cold/archive: expenses past the retention horizon (e.g. > 2 years), kept for audit.
- Delete: rarely — expenses are financial records; keep them, archive don't delete.

**Loans / credit accounts**
- Hot: active (open) loans — always.
- Closed loans: move to a "closed" state; keep the record (financial history),
  de-index the hot path.

**Events (balance changes, expense-recorded stream)**
- Kafka: short retention, sized to your reprocessing window (see
  [`kafka-guide.md`](kafka-guide.md) §6).
- Postgres event tables: hot for the recent window, then archived.
- Cold: the full immutable audit trail — this is the data you'd rebuild from.

**The audit-trail insight:** your events are the *source of truth for reconstruction*.
If loan balances can be rebuilt by replaying events, then balances are derived state
and events are the durable record. That framing decides your archival priorities:
**archive the events; the balances can be recomputed.** This is event-sourcing
thinking applied lightly — you don't need full event sourcing, but the "events are the
truth, state is a projection" lens is what makes archival coherent.

---

## 3. The mechanics: how to move data between tiers

### Partitioning enables cheap lifecycle (do this first)
Partition time-series tables (events, expenses) by month/range
([`postgres-guide.md`](postgres-guide.md) §6). Then tier transitions become metadata
operations, not row-by-row churn:

```
Hot partition (indexed, in default tablespace)
   → DETACH (instant; no longer in the hot path)
   → archive: COPY/export to compressed file on PVC or object storage
   → verify the archive (row counts, checksums)
   → DROP the partition (instant; no bloat, no long DELETE)
```

Contrast with the naive approach — `DELETE FROM events WHERE occurred_at < ...` —
which creates massive dead-tuple churn, bloat, and long transactions. **Partition
drops are the enterprise answer to "how do I clean up old data."**

### Archival format and location
- **Format:** compressed, columnar if you'll query it later (Parquet), or a simple
  compressed dump if it's pure audit. Parquet is the better default for "I might
  analyze this."
- **Location:** a **PVC** (PersistentVolumeClaim) in k3s for local archival, or object
  storage (S3-compatible, e.g. MinIO on your cluster) for durability. You asked for
  PVC archival — PVC is fine and cheap locally, but understand a PVC is bound to a
  node; back it up. Object storage is the more durable answer if you can run MinIO.
- **Verification is mandatory:** after archiving, verify the copy (counts + checksum)
  *before* dropping the partition. An unverified archive is not an archive.

### Cleanup for non-partitioned tables
When you can't partition, batch your deletes to avoid long transactions and bloat:
delete in bounded chunks, in a loop, with pauses for autovacuum. This is a fallback,
not the plan.

---

## 4. Retention policy — write it down, then automate it

A retention policy answers, per data type:

1. **How long does it stay hot?** (queryable in the main path)
2. **How long does it stay warm?** (queryable but off the hot path)
3. **When is it archived, and where?**
4. **When is it deleted, if ever?**
5. **What's the reprocessing window?** (Kafka retention must exceed this)
6. **What's the compliance/audit horizon?** (financial data often must be kept N years)

Example shape (fill in your numbers in [`design.md`](design.md)):

| Data | Hot | Warm | Archive | Delete |
|------|-----|------|---------|--------|
| Expenses | 90 days | 2 years | > 2y, Parquet on PVC/object | never (audit) |
| Loan balance events | 30 days | 90 days | > 90d | never (rebuild source) |
| Kafka event topic | 7 days retention | — | — | auto-expire |
| Outbox sent rows | 7 days | — | — | after 7d |

**Automate every row of this table.** A lifecycle policy a human runs by hand is a
policy that silently stops happening. Use a scheduled job (CronJob in k3s — see
[`infrastructure.md`](infrastructure.md)) that: detaches old partitions, archives,
verifies, drops, and **logs what it did**. Alert on failures.

---

## 5. Event archival and the rebuild path

The payoff of good lifecycle design is a **rebuild capability**:

1. Loan balances are a **projection** of the event stream.
2. If balances drift (a bug, a bad consumer deploy), you **replay** the archived
   events to recompute them.
3. This works because the consumer is idempotent ([`kafka-guide.md`](kafka-guide.md)
   §3) — replaying is safe.

**So archival isn't just cost-saving — it's your disaster-recovery mechanism.** That
reframing is the reason to get it right. It's also a great exercise: intentionally
corrupt a balance, then rebuild it from archived events.

**The reconciliation invariant** (from [`postgres-guide.md`](postgres-guide.md) §2):
"sum of balance changes = current balance." Run it as a scheduled check. Drift =
either a bug or a needed replay. This is both an observability signal and the trigger
for the rebuild path.

---

## 6. Observability of the lifecycle itself

Lifecycle automation that fails silently is worse than none. Watch:

- **Partition count and age** — is the archiver detaching on schedule?
- **Table sizes over time** — hot tables should plateau, not grow forever. A table
  that only grows means cleanup isn't running.
- **Dead tuples / bloat** — climbing bloat means deletes without vacuum (i.e. you
  should have partitioned).
- **Archive job success/failure** — alert on failure; a failed archive blocks the
  safe drop.
- **Kafka retention expiry** — messages expiring before consumers read them = lag
  problem (see [`observability.md`](observability.md)).
- **Rebuild/replay runs** — log and alert; a rebuild is a significant event.

All of these belong on the Datadog/Grafana dashboards
([`observability.md`](observability.md)).

---

## 7. Exercises (Phase 8)

1. **Partition the event table** by month; insert data spanning months.
2. **Detach + archive + verify + drop** an old partition, watching each step.
3. **Break the balance**, then **rebuild from archived events** to prove the
   projection is recoverable.
4. **Run the reconciliation check** and watch it pass; then inject drift and watch it
   fail.
5. **Automate it** as a CronJob in k3s and alert on failure.
6. **Set Kafka retention shorter** than your reprocessing window, lose data to
   expiry, then fix the policy. *Lesson: retention must exceed the replay window.*

Checkpoints in [`checkpoints.md`](checkpoints.md).

---

## 8. Decisions to record in `design.md`

- Tier boundaries per data type (hot/warm/cold/delete durations).
- Partitioning scheme (range by month? which tables?).
- Archival format (Parquet vs dump) and location (PVC vs object storage).
- Verification method before dropping a partition.
- Retention policy table (§4), filled in with your numbers.
- The rebuild-from-archive procedure and when it's triggered.
- The reconciliation check: query, schedule, and alert threshold.
- How lifecycle automation runs (CronJob) and how it's observed.
