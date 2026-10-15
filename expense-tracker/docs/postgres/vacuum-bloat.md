# Vacuum and Bloat — Why Tables Grow and Never Shrink

> MVCC's bill comes due here. This is the most common "why is my DB slow" answer and the
> one that bites write-heavy tables like `outbox` and `balance_changes` first.

## Dead tuples and bloat — the mechanism

Every UPDATE and DELETE in Postgres leaves a **dead tuple** — a row version no snapshot
can see (see [`mvcc.md`](mvcc.md)). It occupies space in the heap *and* in every index
that references it. **Nothing reclaims that space until vacuum runs.**

```
   a page with 6 line pointers, before and after an UPDATE:

   BEFORE the update:
   ┌────────┬────────┬────────┬────────┬────────┬────────┐
   │  lp 1  │  lp 2  │  lp 3  │  lp 4  │  lp 5  │  lp 6  │
   └───┬────┴───┬────┴───┬────┴───┬────┴───┬────┴───┬────┘
       ▼        ▼        ▼        ▼        ▼        ▼
     (v1)     (v2)     (v3)     (v4)     (v5)     (v6)
     live     live     live     live     live     live

   UPDATE row at lp 3, new version doesn't fit → appended to lp 7:

   AFTER:
   ┌────────┬────────┬────────┬────────┬────────┬────────┬────────┐
   │  lp 1  │  lp 2  │  lp 3  │  lp 4  │  lp 5  │  lp 6  │  lp 7  │
   └───┬────┴───┬────┴───┬────┴───┬────┴───┬────┴───┬────┴───┬────┘
       ▼        ▼        ▼        ▼        ▼        ▼        ▼
     (v1)     (v2)    (v3)     (v4)     (v5)     (v6)    (v3')
     live     live    DEAD      live     live     live     live
                    (xmax=T_B)                  (xmin=T_B)

   ► the DEAD tuple still occupies its line pointer and its bytes.
   ► the index entry for v3 now points at v3' (or requires a new one).
   ► a VACUUM later: removes the DEAD entry, sets lp 3's line pointer to LP_UNUSED,
     and lets v3's line pointer slot be reused by a future INSERT (the reason vacuum
     makes INSERTs cheaper too).
```

**The two symptoms of bloat:**
1. **Wasted space** — tables and indexes grow without bound.
2. **Slower scans** — seq scans walk dead tuples; index scans may have to fetch dead heap
   tuples to find a visible one; vacuum itself gets more work to do.

---

## Autovacuum — the daemon that keeps bloat bounded

Autovacuum runs in-process (work process) and watches `pg_stat_all_tables`. For each
table, it computes a **trigger** and runs VACUUM (and ANALYZE) when dead-tuple count
exceeds it.

```
   trigger = autovacuum_vacuum_threshold
           + (autovacuum_vacuum_scale_factor × n_live_tup)

   default: threshold = 50, scale_factor = 0.2 (20%)

   example — expenses has 100,000 live rows:
     trigger = 50 + (0.2 × 100,000) = 20,050 dead tuples

     dead tuples accumulate:
     0 ─── 5,000 ─── 15,000 ───── 20,050 ──► 25,000
                                          VACUUM FIRES
                                          (n_dead_tup resets to 0 after)
```

**Key settings:**

| Setting | Default | Meaning |
|---------|---------|---------|
| `autovacuum` | `on` | the daemon |
| `autovacuum_vacuum_threshold` | 50 | absolute minimum dead tuples to trigger |
| `autovacuum_vacuum_scale_factor` | 0.2 | proportional threshold |
| `autovacuum_analyze_threshold` | 50 | dead tuples to trigger ANALYZE |
| `autovacuum_analyze_scale_factor` | 0.1 | proportional threshold for ANALYZE |
| `autovacuum_vacuum_cost_delay` | 2ms | throttling between I/O bursts |
| `autovacuum_max_workers` | 3 | concurrent vacuum/analyze workers |

**The scale-factor trap (the most important tuning decision):**

Autovacuum's threshold is proportional to *live* row count. That means:
- A **small** table (`categories`, ~50 rows) triggers at `50 + 10 = 60` dead tuples —
  fine, it's never busy anyway.
- A **large, write-heavy** table (`balance_changes`, millions of rows, millions of
  updates) triggers at `50 + 0.2 × 1,000,000 = 200,050` dead tuples before a vacuum
  runs. That's a *lot* of bloat accumulated between vacuums.

**So for write-heavy tables you lower `scale_factor`:**

```sql
ALTER TABLE balance_changes SET (autovacuum_vacuum_scale_factor = 0.02);   -- 2%
ALTER TABLE outbox          SET (autovacuum_vacuum_scale_factor = 0.05);   -- 5%
ALTER TABLE loans           SET (autovacuum_vacuum_scale_factor = 0.05);
-- keep the default (0.2) for small, rarely-updated tables
```

Autovacuum cost is throttled to protect interactive queries; on a small node this can be
slow. `autovacuum_vacuum_cost_delay` can be lowered for hot tables, and
`autovacuum_max_workers` raised if the queue backs up.

---

## The long-transaction hazard — the #1 operational MVCC bug

Vacuum cannot remove a dead tuple while *any snapshot* might still need it. A long-running
transaction holds a snapshot from the moment it began:

```
   t=0     transaction A opens (BEGIN; SELECT ...)   ──────────► snapshot pins everything
   t=5m    5 minutes of dead tuples accumulate; vacuum refuses to remove them
   t=10m   vacuum still blocked; bloat grows
   t=30m   someone notices disk full
   t=31m   A is killed; vacuum finally runs
```

**Diagnose with:**

```sql
SELECT pid, now() - xact_start AS xact_age,
       now() - state_change AS state_age,
       state, wait_event_type, wait_event, query
FROM pg_stat_activity
WHERE state <> 'idle'
   OR (state = 'idle' AND wait_event_type IS NULL)
ORDER BY xact_age DESC NULLS LAST
LIMIT 20;

-- the classic: state='idle', wait_event=NULL, xact_age='02:14:33'
-- that's an open transaction in a connection pool slot, probably forgotten by the app
```

**The rule:** keep transactions *short*. Never leave a connection "idle in transaction"
(both Django and pgbouncer surface this state). A 30-minute idle-in-transaction defeats
autovacuum on every table.

---

## `VACUUM` vs `VACUUM FULL` vs `CLUSTER` vs `REINDEX`

```
   tool              what it does                                  cost
   ─────────────────────────────────────────────────────────────────────────────
   VACUUM (ANALYZE)  marks dead tuples reusable; updates VM/stats   cheap, online
   VACUUM FULL       rewrites the whole table into a compact file    slow, exclusive lock
   CLUSTER (COL)     like VACUUM FULL but reorders rows by an index   slow, exclusive lock
   REINDEX           rebuilds an index from the table                slow; REINDEX
                                                             CONCURRENTLY is online
```

- **`VACUUM`** is your only recurring tool. It's online, concurrent with queries, and
  cheap. It *does not shrink the file* — free space stays in the table for future INSERTs.
- **`VACUUM FULL`** physically rewrites the table, releasing space to the filesystem. It
  takes an `ACCESS EXCLUSIVE` lock (blocks all reads and writes) and is expensive. Use
  sparingly, on maintenance windows, for genuinely bloated tables.
- **`CLUSTER`** reorders rows according to an index and then rewrites — useful when a
  query wants sequential access to clustered rows (rare; usually not worth it).
- **`REINDEX`** rebuilds an index. `REINDEX CONCURRENTLY` avoids a lock; without it, it
  takes `ACCESS EXCLUSIVE`.

For this project: **never run VACUUM FULL on `balance_changes` or `outbox` during
business hours** — they're write-heavy and exclusive locks would block the consumer.

---

## Freeze, age, and wraparound — why vacuum can't just be turned off

Recall from [`mvcc.md`](mvcc.md) that an xid is a 32-bit counter that **wraps** at ~4.3
billion. If a snapshot ever had to compare a *modern* xid against an *ancient* one across
the wraparound boundary, "which is older" becomes ambiguous and data appears corrupted.

**Freeze** solves this: vacuum periodically rewrites very old tuples' `xmin` to a special
value (`FrozenTransactionId`), which sorts as ancient but never wraps. Controlled by:

| Setting | Default | Meaning |
|---------|---------|---------|
| `vacuum_freeze_min_age` | 50M | start freezing tuples this old |
| `vacuum_freeze_table_age` | 150M | whole-table freeze if all tuples are this old |
| `autovacuum_freeze_max_age` | 200M | **hard limit**: urgent vacuum if oldest tuple exceeds this |
| `max_multixact_xid_age` | 400M | same idea for multi-transaction locks |

**Wraparound risk:**

```
   age of oldest unfrozen tuple in a table:

   0 ─── 50M ─── 150M ─── 200M ─── 2147483647
       │      │       │
   start │  │ full │ hard limit: autovacuum FREEZE (cannot be
    free │  │table│ disabled)
         │  │     │
         └──┴─────┴──► past here, Postgres enters "EMERGENCY" vacuum mode
                       and may reject commits to stop corruption

   If you turn autovacuum OFF, you will eventually hit wraparound.
   There is no safe way to run Postgres without vacuum.
```

**The one-liner:** *`autovacuum` is not a performance optimization, it's a correctness
mechanism. Turning it off guarantees eventual wraparound.*

---

## Stats and `ANALYZE`

Autovacuum also runs `ANALYZE` to refresh the planner's statistics (see
[`indexes.md`](indexes.md) for the stats' role). Manual `ANALYZE` after a big bulk load
or after a long-running change of row distribution keeps plans sane.

- `pg_stats` / `pg_statistic` — the stored statistics.
- `default_statistics_target` (100) — how many distinct values Postgres samples per
  column; raise to 500–1000 on wide tables with skewed data, lower if catalog bloats.
- **Stale stats** → planner picks wrong plans → `pg_stat_user_tables.n_live_tup` and
  `n_dead_tup` vs `last_analyze`.

---

## Detecting bloat

A widely used approximation for table bloat:

```sql
SELECT
  schemaname,
  relname AS tablename,
  pg_size_pretty(pg_table_size(relid)) AS size,
  n_dead_tup,
  n_live_tup,
  round(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS dead_pct,
  last_vacuum,
  last_autovacuum,
  last_analyze,
  last_autoanalyze
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY n_dead_tup DESC;
```

Interpretation:
- `dead_pct > 30` on a write-heavy table = autovacuum is falling behind.
- `last_autovacuum` empty or ancient = the daemon isn't firing; check thresholds.
- `n_dead_tup` climbing despite a recent `last_autovacuum` = vacuum is throttled (cost
  delay) or blocked by long transactions.

For index bloat, the go-to is a `repack`-style tool or comparing
`pg_relation_size(index)` against a fresh `CREATE INDEX CONCURRENTLY` baseline. Not worth
manualizing here — just check `pg_stat_user_indexes` and REINDEX the offenders.

---

## Interview angle

- **"Why do Postgres tables grow and never shrink?"** — MVCC leaves dead tuples; only
  VACUUM reclaims them, and VACUUM doesn't shrink the file (only VACUUM FULL does).
- **"What's the autovacuum trigger formula?"** — `threshold + scale_factor × n_live_tup`.
  Lower `scale_factor` for write-heavy tables.
- **"What is the single most dangerous vacuum misconfiguration?"** — turning autovacuum
  off (wraparound risk), and long-running transactions blocking it.
- **"What's the difference between VACUUM and VACUUM FULL?"** — online reclaim of dead
  space vs full rewrite with an exclusive lock and file shrink.
- **"What is freeze and why does it matter?"** — rewrites old xids to `FrozenTransactionId`
  to prevent xid wraparound corruption.
- **"How do you know vacuum is falling behind?"** — `pg_stat_user_tables.n_dead_tup`
  climbing, `last_autovacuum` stale, bloat queries showing high dead pct.

## How this shows up here

- **`balance_changes` and `outbox`** are append-heavy but with an occasional UPDATE
  (`published_at`). Give them tighter `autovacuum_vacuum_scale_factor` (0.02–0.05) and
  monitor `n_dead_tup`.
- **`loans`** sees a balance UPDATE on every card expense — the most update-heavy table.
  Lower `fillfactor` (see [`storage.md`](storage.md)) *and* tighter vacuum.
- **`processed_events`** is append-only → default settings fine.
- **`categories`/`sources`** are small and rarely touched → default scale factor fine.
- **Never** `ALTER SYSTEM SET autovacuum = off` under any scenario. If it seems slow, tune
  cost delay and worker count.
- Watch for idle-in-transaction connections from the app; a leaked `with
  transaction.atomic():` around a slow query is the classic cause of blocked vacuum
  (see [`locking-concurrency.md`](locking-concurrency.md)).
- Metrics to alert on: `n_dead_tup` growth rate on the hot tables, and
  `last_autovacuum` freshness — export via postgres_exporter
  (see [`../observability.md`](../observability.md)).
