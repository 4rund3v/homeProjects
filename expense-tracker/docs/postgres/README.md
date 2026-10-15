# PostgreSQL Internals — Deep Dive

> Reference-grade explanations of how PostgreSQL actually works underneath, written for
> **L5/L6 interview prep** and as the engineering reference for this project. This folder
> extends the overview in [`../postgres-guide.md`](../postgres-guide.md) — go there for
> the modeling/observability sketch, come here for mechanism.

Every doc follows the same shape: **mechanism first** (how it truly works), a **worked
example** on this project's tables (`expenses`, `loans`, `balance_changes`, `outbox`,
`processed_events`), a **trade-off/pitfall** callout, and an **interview angle** where
the topic is a classic.

Scope honesty: this project runs on a **single small k3s node**. Some discussions
(logical replication sharding, Patroni/etcd HA, sharding a write-heavy cluster) are
marked **"for interviews / for scale"** — know them cold for the conversation, but you
will not deploy them here.

## The docs

| File | What it covers | Read when |
|------|----------------|-----------|
| [`mvcc.md`](mvcc.md) | Tuples, xmin/xmax, xids, snapshot vs serializable isolation, visibility map, hint bits, how readers never block writers | Before touching concurrency or `SELECT FOR UPDATE` |
| [`storage.md`](storage.md) | 8KB pages, heap layout, TID/line pointers, HOT chains, TOAST, buffer cache vs OS cache | When a plan says "heap fetches" or updates bloat |
| [`indexes.md`](indexes.md) | B-tree internals, composite column order, index-only scans, fillfactor, BRIN/GIN/GiST/hash, partial/covering/expression, reading `EXPLAIN (ANALYZE, BUFFERS)` | Before adding any index; the most-tested topic |
| [`wal.md`](wal.md) | The WAL: LSNs, segments, `wal_level`, fsync durability, every `synchronous_commit` level, checkpoints, checkpoint storms; full trace of one UPDATE | **The single most important doc** for interviews |
| [`replication.md`](replication.md) | Streaming physical replication, sync vs async and what "sync" really guarantees, lag, logical replication, PITR pointer, single-node HA reality | When someone says "replica" or "RPO/RTO" |
| [`vacuum-bloat.md`](vacuum-bloat.md) | Dead tuples, bloat, `VACUUM` vs `VACUUM FULL` vs `CLUSTER`, autovacuum triggers, wraparound & freeze, bloat detection query | When tables grow and never shrink |
| [`locking-concurrency.md`](locking-concurrency.md) | Isolation levels & anomalies, SSI, lock types & compatibility matrix, deadlock detection, `FOR UPDATE`/`SKIP LOCKED`, advisory locks | Before writing the consumer's row-lock path |
| [`partitioning-and-queries.md`](partitioning-and-queries.md) | Range/list/hash partitioning, pruning, partitioned indexes, drop-vs-DELETE archival, planner-vs-optimizer, when a seq scan is right | When tables are append-heavy and need archival |
| [`backup-restore.md`](backup-restore.md) | `pg_dump` family, WAL archiving for PITR, `pg_basebackup`, recovery targets, the "test your backup" rule, the replay rebuild path | Before you trust anything you can't restore |
| [`tuning-and-observability.md`](tuning-and-observability.md) | Deep settings, PgBouncer pooling gotchas, `random_page_cost` on SSD, the tuning methodology, `pg_stat_statements`, cache-hit-ratio math, "DB is slow" triage order | When something is slow and you must not guess |

## Suggested reading order

**If you have an interview tomorrow:**
`mvcc` → `wal` → `locking-concurrency` → `indexes` → `vacuum-bloat`. These five cover
the questions that actually get asked.

**If you are building this feature:**
`storage` + `indexes` (model well) → `mvcc` + `locking-concurrency` (the consumer's row
locks) → `wal` (durability settings) → `vacuum-bloat` + `partitioning-and-queries`
(the `outbox`/`balance_changes` tables) → `backup-restore` (sleep at night).

**Reference-as-needed:** `replication` (scale story), `tuning-and-observability`
(when slow).

## The one-paragraph mental model

Postgres keeps a **WAL** (append-only log) it must fsync before acknowledging a commit,
a **buffer cache** of 8KB **pages** read/written in transactions, and **multiple row
versions** per logical row (**MVCC**) so readers never block writers. Dead versions are
reclaimed by **vacuum**; space for future reads is organized by **indexes**; concurrent
access is mediated by **locks** and **isolation levels**; big/append-heavy tables get
**partitioned**; durability across crashes is **WAL + checkpoints + backups**; and
everything is observable through `pg_stat_*` views. Every doc below is one of those
sentences expanded.
