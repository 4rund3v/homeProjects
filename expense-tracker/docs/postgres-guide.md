# PostgreSQL Guide — Model, Tune, Observe

> Covers the three things you asked for: **basics + modeling**, **tuning**, and
> **observability**. Plus the operational pieces that show up later: connection
> pooling (PgBouncer), archival, and cleanup. No code — concepts, decisions, and
> exercises.

---

## 1. Core mental model

Internalize these five ideas and most Postgres behavior stops surprising you:

1. **Everything is a transaction.** Every statement runs inside one. ACID is the
   deal; MVCC (multiversion concurrency control) is how it's kept — readers don't
   block writers, writers don't block readers.
2. **MVCC creates dead tuples.** `UPDATE`/`DELETE` don't modify rows in place; they
   write new versions and mark old ones dead. Dead tuples are reclaimed by
   **VACUUM**. Bloat is un-reclaimed dead tuples. This one fact explains most
   performance problems.
3. **The planner uses statistics.** It estimates row counts to choose a plan. Stale
   stats → bad plans. `ANALYZE` (run by autovacuum) keeps them fresh.
4. **Indexes are a trade.** They speed reads, slow writes, cost space, and must be
   maintained by vacuum. Index what you query, not everything.
5. **Constraints are cheaper than app logic.** A `CHECK`, `FOREIGN KEY`, `UNIQUE`, or
   `NOT NULL` enforced by the database is correct even when your app has a bug.

---

## 2. Modeling for this domain

Your entities come from [`domain-decomposition.md`](domain-decomposition.md). Turn
them into tables using these rules:

### Types
- **Money:** `numeric(19,4)` (or your precision choice) — **never** `float`/`double`.
  Store currency separately (`char(3)` ISO code) or in a composite type. This maps to
  the `Money` value object.
- **Time:** `timestamptz` (with time zone), always. Store UTC; convert at the edges.
  Naive `timestamp` is a bug factory.
- **IDs:** `bigint` identity or `uuid`. `bigint` is smaller/faster and fine for a
  single-tenant app; `uuid` if you want non-guessable IDs or future sharding. Pick
  one deliberately.
- **Enums:** native `enum` type or a lookup table. Native enums are fast but awkward
  to change; lookup tables are flexible and joinable. For categories that users might
  extend, use a **table**, not an enum.
- **JSON:** `jsonb` when you genuinely have variable shape. Don't use it as an excuse
  to avoid modeling — queryable structure beats a JSON blob for anything you filter on.

### Relationships & integrity
- Foreign keys on every relationship (`expense.user_id`, `expense.category_id`,
  `expense.loan_id` nullable).
- `ON DELETE` behavior decided explicitly: `RESTRICT` (don't let a referenced row be
  deleted), `CASCADE` (delete children), or `SET NULL`. For expenses→user, `CASCADE`
  on account deletion is fine; for expense→category, `RESTRICT` or `SET NULL` so you
  don't silently orphan history.
- `NOT NULL` by default; make nullability a conscious choice (e.g. `loan_id` is
  nullable *because* only credit-paid expenses have one — that's a real rule).

### Invariants → constraints (the payoff from decomposition)
Every invariant you wrote in [`domain-decomposition.md`](domain-decomposition.md)
§3 should become a constraint:

| Invariant | Constraint |
|-----------|-----------|
| Expense amount positive | `CHECK (amount > 0)` |
| Loan balance never negative | `CHECK (outstanding >= 0)` |
| Credit-paid expense must have a loan | `CHECK ((payment_kind = 'credit') = (loan_id IS NOT NULL))` |
| Sum of changes = balance | enforce in the service *and* verify with a periodic reconciliation job |
| One currency per loan | `CHECK` or composite type |
| Unique category name per user | `UNIQUE (user_id, name)` |

**The reconciliation invariant is special.** "Sum of balance changes equals current
balance" can't be a pure DB constraint (it spans rows), so you enforce it in the
service transaction *and* run a scheduled reconciliation query that alerts on drift.
This is a great observability exercise later.

### Normalization stance
- Normalize to 3NF for the core (no duplicated facts).
- Denormalize **deliberately** for read-heavy summaries — e.g. a materialized view or
  a summary table for "spend by category this month," refreshed on a schedule. Don't
  denormalize before you've measured a slow query.

---

## 3. Indexing strategy

Index for your **query patterns**, not your schema. For each list/report endpoint,
ask: what's the `WHERE`, `JOIN`, and `ORDER BY`?

Likely indexes here:
- `expenses(user_id, occurred_at DESC)` — the main "my recent expenses" query.
- `expenses(user_id, category_id)` — spend-by-category.
- `expenses(loan_id)` — "all expenses on this loan" (also a FK, so index it).
- `loans(user_id)` — "my loans."
- Partial index for a hot subset, e.g. `WHERE payment_kind = 'credit'` if you query
  that slice constantly.
- Unique index to enforce "one open loan per card" if that's a rule.

**Discipline:**
- Composite index column order matters — equality columns first, range/sort last.
- Use `EXPLAIN (ANALYZE, BUFFERS)` before *and* after adding an index. If the plan
  didn't change, the index isn't helping.
- Watch for unused indexes (`pg_stat_user_indexes`); drop them — they cost writes.
- Every FK should generally have an index on the referencing column, or
  cascades/deletes get slow.

---

## 4. Tuning: what actually matters on a small box

You're on a single k3s node, so tuning is about **not misconfiguring**, not about
squeezing a data center. Priorities in order:

### Memory
- `shared_buffers` — the shared cache. A common starting point is ~25% of RAM. Don't
  set it to 80% because a blog said so; leave room for the OS and per-connection work.
- `effective_cache_size` — tells the planner how much RAM is effectively available
  for caching (OS cache included). Set it to ~50–75% of total RAM. It's a *hint*, not
  an allocation.
- `work_mem` — per-sort/hash operation memory. Raise modestly; too high × many
  connections = OOM. Start small, raise for known heavy reports.

### Connections (this is where PgBouncer comes in)
- Postgres forks a **process per connection**. Hundreds of connections = hundreds of
  processes = memory pain and context-switch overhead.
- `max_connections` is often set high "just in case" — that's a trap. Keep it
  moderate and put **PgBouncer** in transaction-pooling mode in front. Your app opens
  many cheap connections to PgBouncer; PgBouncer maintains few real Postgres
  connections.
- **PgBouncer transaction pooling caveat:** session-level features (prepared
  statements, `SET`, advisory locks, temp tables) don't behave as expected. Plan for
  it — e.g. statement-level features or disabling them. This is a real gotcha; read it
  before you enable pooling.

### Writes & durability
- `wal_level`, `checkpoint_timeout`, `max_wal_size` — defaults are sane for a small
  box; tune only when you see checkpoint spikes.
- `synchronous_commit` — `on` (default) is durable per-commit. If you batch-insert
  historical events and can tolerate losing the last few ms on crash, `off` is a
  legitimate speedup — *know the trade-off before using it*.

### Autovacuum
- On a write-heavy event table, autovacuum may fall behind. Watch
  `n_dead_tup` vs `autovacuum_vacuum_threshold`. For hot tables, lower
  `autovacuum_vacuum_scale_factor` (e.g. 0.02–0.05) so it runs sooner.
- Never turn autovacuum off. Tune it.

### The tuning method (memorize this)
1. **Measure first.** `pg_stat_statements` for slow queries; `pg_stat_activity` for
   what's running; `EXPLAIN (ANALYZE, BUFFERS)` for a specific query.
2. **Change one thing.** Two changes at once teach you nothing.
3. **Re-measure.** Compare plans and timings. Keep or revert.
4. **Record it.** Every setting change and why goes in [`runbooks.md`](runbooks.md)
   and [`design.md`](design.md).

---

## 5. Observability on the database

You explicitly want DB observability. Three layers:

### Layer 1 — Extensions (turn these on early)
- **`pg_stat_statements`** — the single most valuable extension. Records normalized
  query text, call counts, total/mean time, rows. This is where you find your slow
  queries. Add it to `shared_preload_libraries` and restart once.
- **`pg_stat_activity`** (built-in) — live view of running queries, wait events,
  states. Your first stop when "the DB is slow."
- **`auto_explain`** — automatically logs plans for slow queries. Great for catching
  the query you didn't know to look for.

### Layer 2 — Built-in statistics views
| View | What it tells you |
|------|-------------------|
| `pg_stat_user_tables` | seq scans vs index scans, dead tuples, last vacuum/analyze |
| `pg_stat_user_indexes` | index usage (find unused ones) |
| `pg_stat_bgwriter` | checkpoint/buffer behavior |
| `pg_stat_replication` | replica lag (if/when you add replicas) |
| `pg_locks` | who's blocking whom |

**The habit to build:** before optimizing, look at `pg_stat_user_tables`. A climbing
`seq_scan` count on a big table with an available index is your bug.

### Layer 3 — External monitoring
- **Metrics to export** (to Datadog/Grafana): connection count, cache hit ratio,
  dead tuples, replication lag, transaction rate, lock waits, checkpoint frequency,
  table/index sizes.
- **`postgres_exporter`** is the standard Prometheus exporter — it reads these stats
  views and exposes them. In k3s you run it as a sidecar/agent; Datadog can scrape or
  you point Grafana at Prometheus. See [`observability.md`](observability.md).
- **Key derived signals:** cache hit ratio (`blks_hit / (blks_hit + blks_read)`) —
  should be high (>0.99) on a warm system; a drop means you're hitting disk.

### Logging
- `log_min_duration_statement` — log any query slower than N ms. Start at, say,
  200–500ms, then lower as you tune. This is your cheapest continuous profiler.
- `log_lock_waits`, `log_checkpoints` — turn on when debugging contention/checkpoints.
- Use **structured logging** (JSON) so your log pipeline can parse it.

---

## 6. Records, events, cleanup, archival

This ties directly to [`data-lifecycle.md`](data-lifecycle.md). The DB-side view:

**Three tiers of data:**
1. **Hot** — current expenses, active loans, recent events. Fast storage, fully
   indexed, queried constantly.
2. **Warm** — older events still occasionally queried (last 90 days?). Indexed less
   aggressively.
3. **Cold** — historical events, archived. Not in the hot path; restored on demand.

**Postgres mechanisms per tier:**
- **Table partitioning** — partition the event/expense tables by time (monthly
  ranges). Partitioning makes archival and cleanup *cheap*: you `DETACH`/`DROP` an old
  partition instead of `DELETE`-ing millions of rows (which creates dead tuples and
  bloat). Design the tables partition-ready from the start — retrofitting is painful.
- **Archival** — copy the old partition's data to object storage or a PVC-backed
  archive (e.g. `COPY TO` a compressed file, or a Parquet export), verify, then drop
  the partition. Never archive without verifying the copy.
- **Cleanup** — for non-partitioned tables, batch your deletes (`DELETE ... WHERE id
  IN (SELECT ... LIMIT 10000)` in a loop) to avoid long transactions and bloat
  spikes. Prefer partition drops over deletes whenever you can.
- **Retention policy** — decide explicitly: "expenses kept hot for 2 years, events
  partitioned monthly, partitions older than 12 months archived then dropped." Write
  it down; automate it; alert on it.

**The gotcha:** `DELETE` doesn't free space to the OS — it creates dead tuples that
VACUUM reclaims *internally*. If you're deleting huge volumes regularly, either
partition (drop) or schedule `VACUUM FULL`/`pg_repack` during maintenance windows
(`VACUUM FULL` takes an exclusive lock — use `pg_repack` to avoid downtime).

---

## 7. Migrations & schema evolution

- Every schema change is a **migration**, versioned in git, applied by your deploy
  pipeline — never by hand in `psql` on the server.
- **Expand/contract** for anything live: add the new column (nullable) → backfill →
  start writing it → stop reading the old → drop the old. Never rename/drop in one
  step against live traffic.
- Add indexes **concurrently** (`CREATE INDEX CONCURRENTLY`) so you don't lock the
  table for writes.
- Test migrations against a production-sized dataset. A migration that's instant on
  100 rows can lock a 10M-row table for minutes.

---

## 8. Hands-on exercises (Phases 2, 8)

1. **Model it:** write the `CREATE TABLE` for expenses and loans with every invariant
   as a constraint. Try to insert a violating row and watch it fail. *Lesson:
   constraints as truth.*
2. **Prove MVCC:** run a slow `UPDATE` in one session and a `SELECT` in another; watch
   the read not block. Then check `n_dead_tup` climb. *Lesson: MVCC + bloat.*
3. **Index by plan:** `EXPLAIN (ANALYZE)` a query with no index (seq scan), add the
   index, run it again (index scan). Then drop an unused index you find in
   `pg_stat_user_indexes`. *Lesson: index for queries.*
4. **Tune one knob:** set `shared_buffers`, measure a heavy query before/after. Change
   exactly one thing. *Lesson: the tuning method.*
5. **Find the slow query:** enable `pg_stat_statements`, run some queries, find the
   slowest by `total_exec_time`. *Lesson: observability-first optimization.*
6. **Partition + archive:** partition the events table by month, insert data across
   months, then archive+drop an old partition. *Lesson: cheap archival.*
7. **PgBouncer:** put it in transaction mode, hit the API, and deliberately trip over
   the prepared-statement caveat, then fix it. *Lesson: pooling reality.*

Matching checkpoints are in [`checkpoints.md`](checkpoints.md).

---

## 9. Decisions to record in `design.md`

- ID strategy (`bigint` identity vs `uuid`).
- Money representation and currency handling.
- Enum vs lookup table for category/payment kind.
- Partitioning scheme (range by month? which tables?).
- Retention/archival policy per data tier.
- Connection pooling approach and how you handle the session-feature caveat.
- Key tuning settings chosen, with before/after measurements.
- Which observability signals you alert on.
