# Backup & Restore — PITR, pg_dump, and the Recovery Drill

> The one rule that matters more than any other: **a backup you have never restored is
> not a backup.** Mechanism first, then the single-node reality of this project, then the
> drill you actually run.

## Two families of backup

```
   ┌─────────────────────────────────────────────────────────────────────┐
   │  LOGICAL                              PHYSICAL                      │
   │  ─────────────────────                ─────────────────             │
   │  pg_dump / pg_dumpall                pg_basebackup + WAL archive    │
   │                                                                     │
   │  reads rows via SQL                   copies the data files + WAL    │
   │  portable across major versions      same version/platform only      │
   │  slow, per-object selective          fast, whole-cluster             │
   │  no PITR by itself                   enables PITR                    │
   │                                                                     │
   │  use: extract a table, migrate,      use: disaster recovery,         │
   │        clone to another version           point-in-time recovery     │
   └─────────────────────────────────────────────────────────────────────┘
```

They solve different problems and you need both.

---

## Logical: `pg_dump` family

```bash
# whole database, custom (compressed, restorable selectively) format
pg_dump -Fc -d app -f app.dump

# plain SQL (portable, human-readable, restores with psql)
pg_dump -d app -f app.sql

# one table, selectively restorable later
pg_dump -Fc -d app -t expenses -f expenses.dump

# everything, all databases, roles and tablespaces (the "get me out of here" dump)
pg_dumpall -f everything.sql

# parallel restore (custom format only, -j = jobs)
pg_restore -d app -j 4 --clean --if-exists app.dump
```

**Strengths:** portable across major versions (PG15 dump → PG17 restore), selective
(`-t table`), human-inspectable in plain format.

**Weaknesses:** slow (reads every row through SQL), no point-in-time recovery on its
own, and a `pg_dump` taken at 02:00 represents 02:00 — everything after is gone.

**Use here:** exporting a partition to cold storage during archival
([`partitioning-and-queries.md`](partitioning-and-queries.md) §Archival), and as a
portable snapshot for major-version upgrades.

---

## Physical: base backup + WAL archive = PITR

**Point-in-time recovery** is the real answer to "how much data can we lose." You take a
base backup once, then archive every WAL segment continuously, then replay to any second
between the backup and the crash.

### The pieces

```
   the durable WAL archive directory (outside the cluster!)

   ┌──────────────────────────────────────────────────────────────┐
   │ /var/backups/pg/wal_archive/                                  │
   │   000000010000000000000001                                    │
   │   000000010000000000000002                                    │
   │   000000010000000000000003   ...one file per 16MB segment     │
   └──────────────────────────────────────────────────────────────┘
            ▲
            │  archive_command copies each completed segment here
            │
   ┌────────┴───────────────────────────────────────────────────┐
   │  the live cluster                                           │
   │    pg_wal/  ──► (segment completes) ──► archive_command      │
   │    postgresql.conf:                                          │
   │      wal_level = replica          (already set)              │
   │      archive_mode = on                                       │
   │      archive_command = 'test ! -f /var/backups/pg/wal_archive/%f │
   │                         && cp %p /var/backups/pg/wal_archive/%f'│
   └──────────────────────────────────────────────────────────────┘
```

`%p` is the WAL file's path, `%f` its filename. The `test ! -f` guard makes re-archiving
idempotent (Postgres retries `archive_command` on failure).

### `pg_basebackup`

```bash
# take a base backup (files + enough WAL to start), to a directory or a tar stream
pg_basebackup -D /var/backups/pg/base -Ft -z -P -X stream -R

#  -X stream   include WAL as it's generated (no gap between backup and WAL)
#  -R          write standby.signal + primary_conninfo (for a replica) or
#              recovery.signal semantics on restore
#  -Ft -z      tar format, gzipped
#  -P          progress
```

### The PITR timeline

```
   time ───────────────────────────────────────────────────────────────────►

        base backup taken                        CRASH
            │                                    │
            ▼                                    ▼
   ┌────────┴─────────┬──────────┬──────────┬────┴────┬──────────┬─────────┐
   │  base backup     │  WAL     │  WAL     │  WAL    │  WAL     │  WAL    │
   │  (data files at  │  seg 01  │  seg 02  │  seg 03 │  seg 04  │  seg 05 │
   │   14:00)         │          │          │         │          │         │
   └──────────────────┴──────────┴──────────┴─────────┴──────────┴─────────┘
                                              ▲
                                              │
                                     recovery target (14:47)
                                     "replay forward, then stop"

   to recover:  restore base backup → point recovery at the archive →
                replay WAL 01..04 up to the target → open the DB.
                Everything up to 14:47 is present. Everything after is not.
```

### The recovery procedure

```bash
# 1. restore the base backup files into a fresh data directory
cp -a /var/backups/pg/base/* /var/lib/postgresql/16/main/

# 2. tell Postgres it's recovering, and where the WAL archive is
#    (create this file; its presence puts the cluster into recovery)
touch /var/lib/postgresql/16/main/recovery.signal

cat >> /var/lib/postgresql/16/main/postgresql.auto.conf <<'EOF'
restore_command = 'cp /var/backups/pg/wal_archive/%f %p'
recovery_target_time = '2026-10-15 14:47:00+00'
recovery_target_action = 'promote'
EOF

# 3. start Postgres — it replays WAL to the target, then promotes
pg_ctl -D /var/lib/postgresql/16/main start
```

**Three kinds of recovery target:**

| Target | Setting | Use |
|--------|---------|-----|
| by time | `recovery_target_time` | "roll back to just before the bad DELETE" |
| by transaction | `recovery_target_xid` | exact xid |
| by name | `recovery_target_name` (a named restore point) | "to the last known-good state" |

`recovery_target_action = 'pause'` lets you inspect the database *at* the target before
committing to it — invaluable when you don't know the exact time of the mistake.

---

## Restore granularity

| Need | Tool |
|------|------|
| one table back | `pg_dump -t` / `pg_restore -t` into a scratch DB, then `INSERT ... SELECT` |
| one database back | `pg_dump -Fc` + `pg_restore` |
| whole cluster to now | streaming replica (see [`replication.md`](replication.md)) |
| whole cluster to a past second | **PITR** (base backup + WAL archive) |
| single row back | PITR to a scratch cluster, extract the row, re-insert |

**The recovery drill — do this, don't just read it:**

1. Take a base backup.
2. Run a known write (`INSERT INTO expenses ...` with a distinctive marker).
3. Take another base backup (or reuse the same one + more WAL).
4. Delete the marker row.
5. Recover to a target *before* the delete, into a **scratch data directory**.
6. Confirm the marker row exists.
7. Recover to *after* the delete; confirm it's gone.
8. Time the whole thing. **That number is your RTO.**

**Rule:** run this drill on a schedule and record the RTO in
[`../runbooks.md`](../runbooks.md). An untested backup is a hope, not a control.

---

## This project's reality: a single node

```
   ┌───────────────────────────────────────────────────────────────────┐
   │                     WHAT WE HAVE                                    │
   │                                                                     │
   │   ┌──────────────┐         ┌──────────────────────┐                │
   │   │  k3s node    │────────►│  PVC (local disk)    │                │
   │   │  postgres    │         │  data files          │                │
   │   └──────────────┘         └──────────────────────┘                │
   │          │                                                          │
   │          └────────► /var/backups/pg/wal_archive  (also a PVC)       │
   │                                                                     │
   │   backups: nightly pg_dump + continuous WAL archive                 │
   └───────────────────────────────────────────────────────────────────┘

   ┌───────────────────────────────────────────────────────────────────┐
   │                     WHAT WE DO NOT HAVE                            │
   │                                                                     │
   │   ✗ a standby to fail over to        (RTO = restore time)          │
   │   ✗ zero data loss on crash          (RPO = last archived WAL)     │
   │   ✗ off-box durability if the node's disk dies                     │
   └───────────────────────────────────────────────────────────────────┘
```

**What this means, stated honestly:**

- **RPO (data loss) = the WAL archive lag** — usually seconds to a minute, if
  `archive_command` is healthy. Monitor it: `pg_stat_archiver.failed_count` and the
  archive directory's newest segment age.
- **RTO (downtime) = restore time** — base backup copy + WAL replay. Minutes to tens of
  minutes. This is why the recovery drill is timed.
- **If the node's disk dies, everything on it dies**, including the archive if the
  archive lives on the same PVC. **The archive must go somewhere else** — an object
  store, another machine, or a Tailscale-reachable NAS. This is the single most important
  hardening step for this project and it belongs in [`../infrastructure.md`](../infrastructure.md).
- The mitigations that don't require a replica: frequent `pg_dump` off-box, WAL archive
  off-box, and the **rebuild-by-replay path** below.

### Rebuild by replay — the event log as a second source of truth

This project has an unusual asset: the **outbox + Kafka event log** is a durable,
ordered record of every domain change that mattered.

```
   two independent durability paths:

   ┌─────────────────────────────┐     ┌─────────────────────────────┐
   │  Postgres                    │     │  Kafka                      │
   │  ─────────                   │     │  ──────                     │
   │  expenses (source of truth)  │     │  expenses.v1 topic          │
   │  balance_changes (log)      │     │  retained for N days        │
   │  loans.outstanding (derived) │     │  ordered by loan_id         │
   └──────────────┬───────────────┘     └──────────────┬──────────────┘
                  │                                     │
                  └──────────────┬──────────────────────┘
                                 ▼
                  derived state (loan balances) can be
                  REBUILT by replaying balance_changes
                  or the Kafka log — see data-lifecycle.md
```

**Concretely:** if `loans.outstanding` is corrupted, you don't need a Postgres backup —
you replay `balance_changes` (or the Kafka topic) to reconstruct it. That's a
**projection rebuild**, and it's the same machinery as the reconciliation job
([`../data-lifecycle.md`](../data-lifecycle.md) §5).

**What replay cannot recover:** the `expenses` rows themselves. If the expenses table is
lost and it wasn't archived, it's gone. So: partition + archive + off-box backup for
`expenses`, and treat replay as the fast path for *derived* state.

---

## The backup schedule that fits here

| What | How often | Where | Retention |
|------|-----------|-------|-----------|
| WAL archive | continuous (`archive_command`) | **off-box** (object store / NAS) | 7–14 days |
| `pg_basebackup` | nightly | off-box | 7 days |
| `pg_dump -Fc` | nightly | off-box | 14 days |
| partition exports | monthly, on archival | off-box cold storage | 1 year+ |
| restore drill | quarterly (timed) | scratch cluster | record RTO |

**The two things that make this schedule real:** the archive goes **off-box**, and the
restore drill actually runs. Everything else is configuration.

---

## Interview angle

- **"RPO vs RTO?"** — RPO = how much data you can lose (a function of archive lag);
  RTO = how long to be back (a function of restore time). They're independent knobs and
  you must state both.
- **"How do you recover to 5 minutes ago?"** — base backup + continuous WAL archive +
  `recovery_target_time`, into a scratch directory, with `recovery_target_action='pause'`
  to inspect first.
- **"`pg_dump` vs `pg_basebackup`?"** — logical vs physical; portable vs fast; selective
  vs whole-cluster; no-PITR vs PITR.
- **"Your backup lives on the same disk as the database. Problem?"** — yes: a disk
  failure takes both. Backups must be off-box. This is a classic gotcha and a good
  signal to mention unprompted.
- **"How do you know your backups work?"** — you restore them, on a schedule, and you
  record how long it took.
- **"What's your recovery story for a single-node system?"** — off-box WAL archive +
  base backups for RPO/RTO, plus rebuild-by-replay for derived state, with the
  single-node limitation documented explicitly.

---

## How this shows up here

- `wal_level=replica` is already set (see [`wal.md`](wal.md)) — that's the prerequisite
  for archiving and for adding a standby later.
- The archival job exports partitions with `pg_dump -t` / `COPY` **before**
  `DETACH`/`DROP`, so archived partitions are independently restorable
  ([`partitioning-and-queries.md`](partitioning-and-queries.md)).
- Loan balances are recoverable by replay, not just by restore
  ([`../data-lifecycle.md`](../data-lifecycle.md) §5).
- The single-node limitation and the off-box requirement are recorded in
  [`../design.md`](../design.md) and the restore drill in
  [`../runbooks.md`](../runbooks.md).
- The one hardening step that matters most: **move the WAL archive off the node's disk.**
