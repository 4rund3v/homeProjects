# Tuning & Observability

> The settings that actually matter on a small box, the methodology that keeps you from
> guessing, and the exact triage order when someone says "the database is slow."
> Mechanism first, then the PgBouncer trap, then the triage flow.

## The tuning methodology (memorize this before any setting)

```
   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
   │ 1. MEASURE   │ ──► │ 2. CHANGE    │ ──► │ 3. RE-MEASURE│ ──► │ 4. RECORD    │
   │              │     │    ONE THING │     │              │     │              │
   │ pg_stat_*    │     │              │     │ same metric, │     │ runbooks.md  │
   │ EXPLAIN      │     │ never two    │     │ same load    │     │ + design.md  │
   │ ANALYZE      │     │ at once      │     │              │     │              │
   └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘

   two changes at once teach you NOTHING — you don't know which one helped,
   and when it breaks in prod you don't know which one to revert.
```

Every setting change goes in [`../runbooks.md`](../runbooks.md) with the reason and the
before/after numbers. Six months from now, "why is `work_mem` 64MB?" has an answer.

---

## Memory: the hierarchy

```
   ┌───────────────────────────────────────────────────────────────────────┐
   │  CPU / process memory                                                 │
   │                                                                       │
   │   per-connection work_mem (sorts, hashes)      ◄── NOT shared         │
   │   per-connection maintenance_work_mem (vacuum) ◄── NOT shared         │
   ├───────────────────────────────────────────────────────────────────────┤
   │  shared_buffers  ── Postgres's own page cache (shared by all backends)│
   ├───────────────────────────────────────────────────────────────────────┤
   │  OS page cache  ── the kernel caches the same data files             │
   ├───────────────────────────────────────────────────────────────────────┤
   │  disk (PVC)                                                            │
   └───────────────────────────────────────────────────────────────────────┘
```

The key insight beginners miss: **Postgres doesn't cache exclusively in
`shared_buffers`.** Blocks it evicts from `shared_buffers` are usually still in the OS
page cache, so a "miss" in shared_buffers is often a hit in the OS cache. That's why
`effective_cache_size` exists — to tell the planner the *combined* size.

### `shared_buffers`

- Postgres's shared page cache. A common starting point: **~25% of RAM**.
- Don't set it to 80% because a blog said so — the OS cache needs room too, and
  Postgres doesn't use it as efficiently as the kernel does for raw file caching.
- Raising it reduces eviction and the double-copy cost; the returns diminish fast.
- It's a **hard allocation** (reserved at start), unlike `effective_cache_size`.

### `effective_cache_size`

- **A hint, not an allocation.** Tells the planner how much memory is effectively
  available (shared_buffers + OS cache).
- Set to ~**50–75% of total RAM**.
- Effect: a higher value makes index scans look cheaper relative to seq scans, so the
  planner prefers them. Set it too low and the planner chooses seq scans on tables that
  would have been fast with an index.

### `work_mem`

- Memory for **one** sort or hash operation (ORDER BY, DISTINCT, hash join, aggregate).
- **The multiplication danger:**

```
   total memory used by work_mem ≈
        work_mem
      × number of connections (well, active sessions)
      × number of sort/hash operations per query

   work_mem = 64MB × 100 connections × 3 sorts = 19.2 GB ── OOM on a small box
```

- Start modest (16–64MB), raise **only** for known heavy reports, and prefer raising it
  per-session for those reports (`SET work_mem = '512MB'`) over raising it globally.
- When a sort exceeds `work_mem` it **spills to disk** — you'll see
  `Sort Method: external merge Disk: 1234kB` in `EXPLAIN ANALYZE`. That's your signal.

### `maintenance_work_mem`

- For `VACUUM`, `CREATE INDEX`, `ANALYZE`, and some DDL. Not per-connection-critical in
  the same way, because maintenance is usually one operation at a time.
- Raise it (128–512MB) if autovacuum or index creation is slow.

---

## Connections and the PgBouncer trap

Postgres forks a **process per connection**. Hundreds of connections means hundreds of
processes — memory, context switching, and a scheduler that hates you.

```
   WITHOUT a pooler:

   100 app threads ──► 100 Postgres backends ──► 100 processes
                                            └── memory + context-switch pain

   WITH PgBouncer (transaction pooling):

   many cheap          few real
   client conns        server conns
   ┌─────────┐         ┌─────────┐
   │ app 1   │────────►│ server 1│──┐
   │ app 2   │────────►│ server 2│  │
   │ app 3   │─┐       │ server 3│  ├──► Postgres
   │ app 4   │ └──────►│ server 4│  │
   │ ... 100 │  mux    │  ...    │  │
   └─────────┘         └─────────┘──┘
                        (e.g. only 10 real)
```

- Keep `max_connections` moderate (e.g. 100) and put **PgBouncer** in front in
  **transaction pooling** mode.
- The app opens many cheap connections to PgBouncer; PgBouncer maintains few real
  Postgres connections and multiplexes.

### The transaction-pooling gotchas — a real production trap

Transaction pooling means a server connection is shared across clients **between
transactions**. Anything that assumes "this server connection is mine for my whole
session" breaks:

| Feature | Works? | Why | Fix |
|---------|--------|-----|-----|
| `SET` / `RESET` session vars | ✗ | next client gets the same server conn | `SET LOCAL` inside the txn |
| Prepared statements (protocol-level) | ✗ | prepared on one server, executed on another | disable (`max_prepared_statements=0`) or use statement pooling |
| `LISTEN`/`NOTIFY` | ✗ | notifications go to whoever holds the conn | don't use with pooling |
| Advisory locks (**session-scoped**) | ✗ | lock held on a server conn that gets reused | **always use `pg_advisory_xact_*`** |
| Temp tables | ✗ | visible to the next client on that conn | avoid, or use `pg_temp` with care |
| `LOAD` of a library | ✗ | session-scoped | avoid |

**The specific bite for this project:** the archival job's advisory lock
([`locking-concurrency.md`](locking-concurrency.md) §Advisory locks). If it used
`pg_advisory_lock` (session-scoped) through a pooled connection, the lock could persist
on a server connection handed to a different client. Always use
`pg_try_advisory_xact_lock`.

**Django's gotcha:** the default Postgres backend uses server-side prepared statements
after 5 executions. Under transaction pooling this breaks. Options: set
`max_prepared_statements=0` in PgBouncer (PG14+ PgBouncer handles it), or disable
prepared statements in Django (`'OPTIONS': {'prepared_statements': False}` — Django 4.2+
has connection-level support). Decide deliberately and record it.

---

## Write-path and checkpoint settings

| Setting | Default | What it does | When to touch |
|---------|---------|--------------|---------------|
| `wal_buffers` | auto (~1/32 shared_buffers) | WAL buffer before flush | rarely; raise under heavy concurrent write bursts |
| `checkpoint_timeout` | 5 min | time-based checkpoint trigger | raise if recovery time can be longer |
| `max_wal_size` | 1 GB (PG14+) | WAL target between checkpoints | **raise** to prevent checkpoint storms |
| `min_wal_size` | 80 MB | floor for recycled segments | rarely |
| `checkpoint_completion_target` | 0.9 | spread flushing over this fraction of the interval | keep high (0.9) |
| `synchronous_commit` | `on` | durability per commit | see [`wal.md`](wal.md) |
| `full_page_writes` | on | FPIs after checkpoints | **never turn off** unless you accept corruption risk |

**`checkpoint_completion_target` and storms:** a checkpoint must flush all dirty pages.
If it does that in a burst at the end, latency spikes. Setting the target to 0.9 spreads
the writes across 90% of the checkpoint interval. This is the single most effective
smoothing knob.

**`random_page_cost` on SSD:**

```
   default random_page_cost = 4.0   (tuned for spinning disks, where a random
                                     read really is ~4× a sequential read)

   on an SSD, a random read is nearly as cheap as a sequential one:
     random_page_cost = 1.1        (the widely-used SSD value)

   effect: index scans (random-ish heap access) look cheaper → the planner
           prefers them over seq scans. On a small SSD-backed PVC this is one
           of the highest-leverage one-line changes.
```

Confirm your storage is actually SSD-backed before setting it — on a network PVC it may
not be.

### `default_statistics_target`

- Controls how many rows `ANALYZE` samples per column (default **100**).
- Higher = better plans on skewed columns, at the cost of slower `ANALYZE` and more
  planning time.
- Raise per-column for the ones the planner gets wrong:
  `ALTER TABLE expenses ALTER COLUMN user_id SET STATISTICS 500;`

---

## `pg_stat_statements` — finding the offenders

```sql
-- enable once, then restart
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
-- (or add to postgresql.conf and restart)

-- the query that starts every optimization session
SELECT calls,
       round(total_exec_time::numeric, 1)  AS total_ms,
       round(mean_exec_time::numeric, 2)   AS mean_ms,
       round((100 * total_exec_time / NULLIF(sum(total_exec_time) OVER (), 0))::numeric, 1) AS pct_of_total,
       left(query, 90)                     AS query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 15;
```

**Read it in two directions:**

| Sort by | Answers |
|---------|---------|
| `total_exec_time DESC` | "where is the database's time actually going?" — start here |
| `mean_exec_time DESC` (with `calls > 100`) | "which single query is pathologically slow?" |

**Normalization:** identical queries with different literals are normalized to
`$1, $2` and counted together — that's what makes this view useful. But it also means
**a generic plan can hide a bad parameter's cost**, and it means `pg_stat_statements`
aggregates across plans.

**The plan-caching warning:** with prepared statements, Postgres may pick a **generic
plan** that's bad for your actual parameters. If `pg_stat_statements` shows a query
whose `mean_exec_time` is wildly worse than a manual `EXPLAIN` with real values,
suspect a generic plan (see [`partitioning-and-queries.md`](partitioning-and-queries.md)).

**Discipline:** `pg_stat_statements_reset()` after a deploy or a schema change, or
you're comparing across plans and stats views that no longer mean the same thing.

---

## Cache hit ratio math

```sql
SELECT blks_hit, blks_read,
       round(blks_hit::numeric / NULLIF(blks_hit + blks_read, 0), 5) AS hit_ratio
FROM pg_stat_database WHERE datname = current_database();
```

```
   hit_ratio = blks_hit / (blks_hit + blks_read)

   warm, healthy system:  > 0.99   (nearly every block served from cache)
   cold / just restarted:  lower, and rising as it warms
   a drop below 0.99 on a warm system means:
       • the working set no longer fits in shared_buffers + OS cache, OR
       • a query is scanning data it never touches twice (a bad plan), OR
       • you just deployed something that reads far more than before
```

**The nuance interviews reward:** a high cache hit ratio is *necessary but not
sufficient*. A seq scan of a 1M-row table has a 1.0 hit ratio after the first pass and is
still terrible. Pair the ratio with `pg_stat_user_tables` scan counts and actual
`EXPLAIN (ANALYZE, BUFFERS)` output.

---

## "The database is slow" — the triage order

Run this in order. Each step rules something in or out, so you never guess.

```
   ┌─────────────────────────────────────────────────────────────────────┐
   │  STEP 1 — Is anything even running?                                  │
   │    SELECT state, wait_event, query, now()-query_start               │
   │      FROM pg_stat_activity WHERE state <> 'idle';                    │
   │    ► rules IN: a long-running query, lock waits (wait_event =       │
   │                Lock), idle-in-transaction sessions                    │
   │    ► rules OUT: the database itself (nothing is executing)           │
   ├─────────────────────────────────────────────────────────────────────┤
   │  STEP 2 — Who is blocking whom?                                      │
   │    the pg_blocking_pids() query in locking-concurrency.md            │
   │    ► a blocking chain means a lock problem, not a tuning problem     │
   ├─────────────────────────────────────────────────────────────────────┤
   │  STEP 3 — Where is time going overall?                               │
   │    pg_stat_statements ORDER BY total_exec_time DESC                  │
   │    ► names the top offenders; compare mean vs total                  │
   ├─────────────────────────────────────────────────────────────────────┤
   │  STEP 4 — For each offender, read the actual plan                    │
   │    EXPLAIN (ANALYZE, BUFFERS) <the query>;                           │
   │    ► look for: estimated ≫ actual rows (stale stats),                │
   │                seq scan on a big table, external-merge sorts         │
   ├─────────────────────────────────────────────────────────────────────┤
   │  STEP 5 — Is it the write path?                                      │
   │    pg_stat_bgwriter (checkpoints_timed vs checkpoints_req)           │
   │    pg_stat_archiver (failed_count)                                   │
   │    ► checkpoints_req climbing = checkpoint storm (raise max_wal_size)│
   ├─────────────────────────────────────────────────────────────────────┤
   │  STEP 6 — Is it vacuum falling behind?                               │
   │    pg_stat_user_tables.n_dead_tup vs autovacuum threshold            │
   │    ► bloat makes every scan slower; see vacuum-bloat.md              │
   ├─────────────────────────────────────────────────────────────────────┤
   │  STEP 7 — Only now, consider a setting change                         │
   │    and change exactly ONE thing. Then re-run steps 1–6.              │
   └─────────────────────────────────────────────────────────────────────┘
```

**The reason the order matters:** steps 1–2 catch the majority of "the database is slow"
incidents (a runaway query or a lock), and they require **no tuning at all**. Jumping
straight to settings is how people make things worse.

---

## What to export to Datadog/Grafana

| Metric | Source | Alert threshold (starting point) |
|--------|--------|----------------------------------|
| cache hit ratio | `pg_stat_database` | < 0.99 on a warm system |
| connections (by state) | `pg_stat_activity` | > 80% of `max_connections` |
| dead tuples (hot tables) | `pg_stat_user_tables` | > `autovacuum_vacuum_scale_factor` × n_live_tup |
| replication lag | `pg_stat_replication` | > 30s (if a standby exists) |
| checkpoint requests | `pg_stat_bgwriter.checkpoints_req` | any sustained climb |
| WAL archive failures | `pg_stat_archiver.failed_count` | > 0 |
| longest transaction | `pg_stat_activity` | > 5 min |
| lock waits | `pg_stat_activity` wait_event | any transaction waiting > 10s |
| seq scans (hot tables) | `pg_stat_user_tables` | climbing on a table with a usable index |

The full dashboard spec is in [`../observability.md`](../observability.md); this table is
the Postgres-specific subset with the thresholds to start from.

---

## Interview angle

- **"How do you tune a Postgres you didn't set up?"** — measure first
  (`pg_stat_statements`, `EXPLAIN ANALYZE`), change one thing, re-measure, record.
  Never two changes at once.
- **"`shared_buffers` vs `effective_cache_size`?"** — the first is an allocation; the
  second is a hint that includes the OS cache. Set ~25% and ~50–75% respectively.
- **"`work_mem` gotcha?"** — it's per-sort-per-connection; the real usage is
  work_mem × connections × sorts. Raise per-session for reports, not globally.
- **"What breaks under PgBouncer transaction pooling?"** — session `SET`, prepared
  statements, LISTEN/NOTIFY, session advisory locks, temp tables. Use xact-scoped
  advisory locks and disable prepared statements.
- **"A query got 100× slower after a deploy, no settings changed. Where do you look?"**
  — `EXPLAIN (ANALYZE, BUFFERS)`: estimated vs actual rows (stale stats → `ANALYZE`), a
  new seq scan (missing index), a generic plan (prepared statement), or a parameter
  that's now non-selective.
- **"Is a 0.99 cache hit ratio always good?"** — no; a seq scan also has a great hit
  ratio. Pair it with scan counts and real plans.

---

## How this shows up here

- `shared_buffers` ~25% of the node's RAM; `effective_cache_size` ~50–75%;
  `work_mem` modest with per-session raises for reports.
- `random_page_cost = 1.1` if the PVC is SSD-backed (verify first).
- PgBouncer in transaction pooling, **prepared statements disabled in Django**, and all
  advisory locks are `pg_advisory_xact_*`.
- `max_wal_size` raised above default before `balance_changes` write bursts cause
  checkpoint storms (watch `checkpoints_req`).
- `pg_stat_statements` and `auto_explain` on from day one, reset per deploy.
- Every setting change recorded in [`../runbooks.md`](../runbooks.md) with before/after
  numbers.
- The triage order above is the first section of the "DB is slow" runbook.
