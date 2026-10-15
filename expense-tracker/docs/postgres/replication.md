# Replication — Physical, Logical, and the Single-Node Truth

> How a second Postgres stays in sync, what "synchronous" really promises, and why a
> single-node deployment can't have HA no matter how you configure it.

## Physical (streaming) replication

The standby is a **byte-for-byte copy** of the primary. It works by continuously
receiving and replaying the WAL stream — the same WAL that makes crash recovery possible
(see [`wal.md`](wal.md)).

```
                    PRIMARY                                    STANDBY
   ┌───────────────────────────────────────┐        ┌──────────────────────────────────┐
   │  clients write                        │        │                                  │
   │      │                                │        │                                  │
   │      ▼                                │        │                                  │
   │  buffer cache (dirty pages)           │        │                                  │
   │      │                                │        │                                  │
   │      ▼  WAL records                   │        │                                  │
   │  ┌──────────────┐   wal_sender        │        │   wal_receiver                   │
   │  │  pg_wal      │═════════════════════╪════════╪══►  ┌──────────────┐             │
   │  │  (flushed)   │   (protocol: STARTUP,│        │     │ receive pg_wal│             │
   │  └──────────────┘    DATA, KEEPALIVE) │        │     └───────┬──────┘             │
   │                                       │        │             ▼                     │
   │  pg_stat_replication ◄─────────────── ┼─ KEEPALIVE/reply ──┤  startup/replay       │
   │    (flush_lsn, replay_lsn, state)     │        │             ▼                     │
   │                                       │        │     data files (replica)          │
   └───────────────────────────────────────┘        └──────────────────────────────────┘

   The standby cannot be written to (read-only) except for replay.
   Failover = promote the standby: it stops replay and accepts writes.
```

**Setup skeleton:**

```bash
# on the standby
pg_basebackup -h primary -D /var/lib/postgresql/data -U replicator -P -R
# -R writes standby.signal and primary_conninfo into postgresql.auto.conf
```

```conf
# primary
wal_level = replica
max_wal_senders = 10
# synchronous replication (optional):
synchronous_standby_names = 'ANY 1 (s1, s2)'
```

```conf
# standby (auto.conf, written by -R)
primary_conninfo = 'host=primary user=replicator'
primary_slot_name = 'standby_1'      # prevents WAL removal the standby still needs
```

**Reading `pg_stat_replication`** — your primary-side view of replica health:

| Column | Meaning |
|--------|---------|
| `application_name` | matches `synchronous_standby_names` |
| `state` | `streaming`, `catchup`, `startup`, `stopped` |
| `sent_lsn`, `write_lsn`, `flush_lsn`, `replay_lsn` | how far the WAL has traveled |
| `write_lag`, `flush_lag`, `replay_lag` | time between each stage |
| `sync_state` | `sync`, `async`, `potential`, `quorum` |

Lag = `pg_current_wal_lsn()` on primary minus `replay_lsn` on standby. It's in **bytes**,
not seconds — convert with the observed replay rate.

---

## Asynchronous vs synchronous — what "synchronous" actually guarantees

This is the most misunderstood topic in replication. Be precise.

```
   ASYNCHRONOUS (default)

     client ──COMMIT──► primary flushes WAL locally ──ack──► client
                                   │
                                   └──► ships WAL to standby (later, best-effort)

     ► primary crash: any WAL not yet shipped is LOST. Standby may be missing the last
       few commits that were acknowledged to clients. This is data loss on failover.
     ► RPO > 0. Fastest writes.


   SYNCHRONOUS (synchronous_standby_names configured)

     client ──COMMIT──► primary flushes WAL locally
                              │
                              ├──► ships to standby ── standby flushes WAL
                              │                          │
                              ◄──── "flush_lsn >= commit LSN" ──┘
                              │
                            ack ──► client

     ► a commit is acknowledged only after the WAL is durable on a standby.
     ► primary crash: no acknowledged commit is lost. RPO = 0 (for acked transactions).
     ► writes pay a network round-trip per commit.
```

**The subtleties people get wrong:**

1. **"Synchronous" refers to WAL *flush* on the standby, not *apply*.** With
   `synchronous_commit=remote_apply`, the primary additionally waits for the standby to
   *replay* the change, so a read on the standby sees it. `remote_write` (default for sync)
   only waits for the WAL to be *written* on the standby, not applied.
2. **`synchronous_standby_names` syntax matters:**
   - `'s1'` — wait for that one standby.
   - `'ANY 1 (s1, s2)'` — wait for **any one** of the group to flush. Survives losing a
     specific standby without blocking writes.
   - `'FIRST 2 (s1, s2, s3)'` — wait for the first two that *connect*, in priority order.
3. **A sync standby going silent stalls writes.** If your only sync standby dies and
   `synchronous_standby_names` still names it, the primary blocks on commit. `ANY n (...)`
   avoids single-standby lock-in but you must size `n` ≤ actual standbys.
4. **Sync replication does not make failover automatic.** It bounds data loss; something
   still has to notice the primary is gone and promote the standby (repmgr, Patroni,
   Stolon, or a manual `pg_ctl promote`). See the HA section below.
5. **Split-brain is the real danger.** If the network partitions and both old primary and
   promoted standby accept writes, you now have two divergent histories. This is what
   fencing/quorum/etcd solves — and it's why "we have a replica" ≠ "we have HA."

---

## Replica lag — causes and consequences

```
   primary LSN:    ───────────────────────────────────────────────►  0/9000
   standby replay: ────────────────────────────►  0/7000

                          lag = 0/2000 bytes (8KB × 4 pages of WAL behind)
```

Common causes:
- **Long-running query on the standby** holding back replay (hot standby conflicts).
- **Recovery conflict** — a standby query needs a row version that vacuum wants to remove
  on the primary; `max_standby_streaming_delay` (default 30s) delays replay, then cancels
  the query.
- **Network saturation** between primary and standby.
- **Single-threaded replay** for a heavy write workload (PG13+ allows parallel apply for
  some cases, but replay is largely serial).
- **Primary I/O saturation** slowing WAL generation and shipping.

**Consequences:** stale reads on the standby (your loan balance is a few seconds behind),
longer failover time, and — with async replication — the data-loss window.

**`hot_standby_feedback`** tells the primary not to vacuum rows the standby's queries
still need. It reduces conflicts but can cause **bloat on the primary** — a classic
trade-off, so leave it `off` unless standby queries are being cancelled.

---

## Logical replication

Where physical replication ships WAL bytes, **logical replication decodes WAL into
row-level changes** and applies them table by table.

```
   PHYSICAL                             LOGICAL
   ┌──────────┐   WAL bytes   ┌──────┐  ┌──────────┐ decode  ┌──────────┐ apply  ┌──────────┐
   │ primary  │══════════════►│standby│  │ publisher│════════►│subscriber│═══════►│  table   │
   │ (whole   │  byte-identical│(whole│  │ (publication       │ (subscription       │ (subset, │
   │  cluster)│   cluster      │cluster│  │  = set of tables)  │  = link + slot)     │  writable)
   └──────────┘               └──────┘  └──────────┘          └──────────┘          └──────────┘

   same major version, whole cluster    different major versions, table subsets, both writable
```

```sql
-- publisher
CREATE PUBLICATION app_pub FOR TABLE expenses, loans, balance_changes;

-- subscriber (a different cluster, possibly a different version)
CREATE SUBSCRIPTION app_sub
  CONNECTION 'host=publisher dbname=app'
  PUBLICATION app_pub;
```

**When logical beats physical:**
- **Major-version upgrades** (PG14 → PG16) with minimal downtime.
- **Selective replication** — only some tables, or only some rows (`FOR TABLE ... WHERE`).
- **Different schemas / transformations** between publisher and subscriber.
- **Merging several databases into one** (shard consolidation).
- **CDC into Kafka** via a decoding plugin (Debezium, pgoutput) — this is the same
  machinery that would replace our outbox if we ever wanted true change-data-capture.

**Costs:** no DDL replication (you manage schema by hand), higher overhead, replication
slots that can bloat `pg_wal` if a subscriber stops consuming, and **row identity
requirements** (a replica identity / PK on every replicated table).

---

## PITR and HA — pointers

- **Point-in-time recovery** (base backup + archived WAL) is in
  [`backup-restore.md`](backup-restore.md). It gives you an **RTO/RPO story for disaster**,
  not live failover.
- **Live HA** — automatic detection + promotion + client redirection — needs a tool
  (Patroni, repmgr, pg_auto_failover) and, for real safety, an odd number of nodes or an
  external quorum (etcd/Consul) to prevent split-brain.

---

## The single-node reality (be honest about this)

This project runs **one Postgres pod on one k3s node**. Say this plainly:

```
   what we have                                what we'd need for real HA
   ─────────────────────────────────           ─────────────────────────────────
   1 Postgres pod                              3+ Postgres nodes (or 2 + witness)
   WAL on a PVC (survives pod restart)         quorum (etcd) to fence a failed primary
   backups + PITR for disaster                 Patroni/repmgr for auto-failover
   no replica, no failover, no RPO=0           a connection pooler that follows the leader
                                               load balancing reads across replicas

   blast radius today: the node dies ⇒ the DB is down until the node returns,
   and the last committed transactions since the last backup are at risk.
```

**What the single node *does* give you:** a PVC means a pod restart (crash, upgrade,
reschedule) is **not** data loss — Postgres restarts, replays WAL, and continues. That's
crash recovery, not HA, and the distinction is exactly what an interviewer probes.

**Documented stance for [`../design.md`](../design.md):** single node + scheduled
backups + tested PITR + the "rebuild balances by replaying the event log" path
([`../data-lifecycle.md`](../data-lifecycle.md) §5). RTO ≈ time to restore a node and
recover; RPO ≈ backup interval. Write those numbers down — an unstated RPO is an
unstated acceptance of data loss.

---

## Interview angle

- **"Difference between async and sync replication?"** — sync waits for standby WAL flush
  before acking (RPO=0 for acked txns, slower); async doesn't (fast, loses recent commits
  on failover).
- **"Does a replica give you HA?"** — No. It gives you a copy. HA needs detection,
  promotion, client redirection, and split-brain protection.
- **"What is replica lag and how do you measure it?"** — LSN difference between primary
  and standby replay; in bytes, converted to time by replay rate.
- **"When would you use logical replication?"** — version upgrades, partial/table-level
  replication, cross-version, CDC.
- **"How does replication relate to WAL?"** — a standby replays the primary's WAL; the
  durability mechanism and the replication mechanism are the same log.
- **"What breaks sync replication?"** — standby down (writes stall unless `ANY n`),
  network partition (split-brain risk), and slow standby fsync.

## How this shows up here

- Today: **no replica.** PVC + backups + PITR is the durability story; state it in
  [`../design.md`](../design.md).
- `wal_level=replica` is set now so adding a standby later needs no config change
  (see [`wal.md`](wal.md)).
- If a read-heavy reporting dashboard appears, a **physical hot standby** for reads is the
  first scaling step — before any sharding conversation.
- The "rebuild balances by replay" path
  ([`../data-lifecycle.md`](../data-lifecycle.md) §5) is our substitute for a standby
  during a logical-data disaster: replay `balance_changes` to reconstruct `outstanding`.
- Logical replication is the "for scale / for interviews" story: CDC into Kafka,
  cross-version upgrade, multi-region.
