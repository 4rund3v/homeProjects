# Partitioning & Query Planning

> How to keep append-heavy tables fast and cheap to archive, and how to read the planner
> well enough to know when a seq scan is the *right* answer. Mechanism first, then this
> project's `expenses` and `balance_changes`.

## Why partition at all

Partitioning splits one logical table into physical children, chosen by a key. Three
reasons, in order of how often they actually matter:

1. **Cheap archival** — `DROP` a partition instead of `DELETE`-ing millions of rows
   (the big win; see §Archival).
2. **Pruning** — the planner skips partitions that can't match, so queries touch less
   data.
3. **Vacuum/autovacuum per child** — a hot recent month vacuums without the whole table's
   dead-tuple count.

**What partitioning does NOT do:** it does not automatically parallelize, does not put
partitions on different disks (unless you use tablespaces deliberately), and does not
help unless your queries filter on the partition key.

---

## The three strategies

```sql
-- RANGE: the fit for time-series data. Our case.
CREATE TABLE expenses (
  id           bigserial,
  user_id      bigint NOT NULL,
  occurred_at  timestamptz NOT NULL,
  amount_cents bigint NOT NULL
) PARTITION BY RANGE (occurred_at);

CREATE TABLE expenses_2026_09 PARTITION OF expenses
  FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE expenses_2026_10 PARTITION OF expenses
  FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');

-- LIST: discrete keys, e.g. sharding by region
CREATE TABLE expenses_eu PARTITION OF expenses_by_region
  FOR VALUES IN ('DE', 'FR', 'NL');

-- HASH: even distribution when there's no natural range or list
CREATE TABLE expenses_h0 PARTITION OF expenses_hashed
  FOR VALUES WITH (MODULUS 4, REMAINDER 0);
```

| Strategy | Choose when | Watch out for |
|----------|-------------|---------------|
| **RANGE** | time-series, append-heavy, archived by age | skew if a key range gets most writes |
| **LIST** | a small, known, uneven set (region, kind) | new values need a new partition or a DEFAULT |
| **HASH** | you only want even spread, no query benefit | **no pruning** — every query scans all partitions |

**For this project:** RANGE on `occurred_at` for `expenses`, and on `created_at` for
`balance_changes`. Both are append-only-in-practice and both get archived by age.

---

## The layout, and pruning

```
   logical table: expenses
   ┌────────────────────────────────────────────────────────────────────┐
   │  partition key = occurred_at                                        │
   │                                                                     │
   │  expenses_2026_07   [2026-07-01, 2026-08-01)      ◄── cold, archive │
   │  expenses_2026_08   [2026-08-01, 2026-09-01)      ◄── cold, archive │
   │  expenses_2026_09   [2026-09-01, 2026-10-01)      ◄── warm          │
   │  expenses_2026_10   [2026-10-01, 2026-11-01)      ◄── HOT, all new  │
   │  expenses_default   everything else (catch-all)   ◄── warning sign  │
   └────────────────────────────────────────────────────────────────────┘
```

**Pruning** is the planner deciding, from the `WHERE` clause, which partitions cannot
contain matching rows:

```
   query:  SELECT * FROM expenses
            WHERE occurred_at >= '2026-10-01'
              AND occurred_at <  '2026-11-01'
              AND user_id = 42;

   planner's pruning:
   ┌────────────────────┬──────────────────────────────────────────────┐
   │ expenses_2026_07   │ SKIP  (range entirely < query range)         │
   │ expenses_2026_08   │ SKIP                                          │
   │ expenses_2026_09   │ SKIP                                          │
   │ expenses_2026_10   │ SCAN  (range overlaps)                        │
   │ expenses_default   │ SCAN  (contents unknown — cannot be pruned)   │
   └────────────────────┴──────────────────────────────────────────────┘

   EXPLAIN output shows it directly:
     Seq Scan on expenses_2026_10  (cost=... rows=...)
     Seq Scan on expenses_default  (cost=... rows=...)   ◄── the giveaway
```

**Two pruning gotchas:**

- **`expenses_default` is always scanned** — Postgres can't know what's in it. Rows
  landing in the default partition usually mean a partition wasn't created in time.
  Alert on it.
- **Pruning happens at plan time, and (for prepared statements) at execution time.**
  A generic `WHERE occurred_at >= $1` prunes at *execution* (runtime pruning), but only
  if the parameter is stable; a `WHERE occurred_at + interval '1 day' >= $1` defeats
  pruning entirely because the key is wrapped in an expression.

```
   pruning destroyed by an expression on the key:

   ✗ WHERE date_trunc('month', occurred_at) = '2026-10-01'
       → planner can't reason about the partition key → scans ALL partitions

   ✓ WHERE occurred_at >= '2026-10-01' AND occurred_at < '2026-11-01'
       → prunes to one partition
```

**Rule: never wrap the partition key in a function.**

---

## Constraints and indexes on partitioned tables

**The PK/UNIQUE gotcha — the #1 partitioning surprise:**

```
   ✗ CREATE TABLE expenses (id bigserial PRIMARY KEY, occurred_at ...)
       PARTITION BY RANGE (occurred_at);

   ERROR: unique constraint on partitioned table must include all partition columns
```

A unique index on a partitioned table **must include the partition key**. Otherwise
uniqueness would have to be checked across every partition on every insert, which
Postgres refuses to do. The fix is a composite key:

```sql
PRIMARY KEY (id, occurred_at)
```

**Practical consequences:**

- You lose the single-column `id` unique guarantee. Enforce it with a **global
  sequence** (`bigserial` is per-partition by default — use an explicit `SEQUENCE`) or
  accept that `id` is only unique *within* a partition and always query by
  `(id, occurred_at)`.
- Indexes are **created per partition**, either individually or via
  `CREATE INDEX ... ON expenses` which (PG11+) creates it on all partitions including
  future ones via the parent's definition.
- `ONLY` and `ATTACH` let you add an existing table as a partition later — the basis of
  the archival flow.

```
   index topology (each partition gets its own physical index):

   expenses_2026_10 ──► expenses_2026_10_pkey (on id, occurred_at)
                    ──► expenses_2026_10_user_idx (on user_id, occurred_at DESC)
   expenses_2026_11 ──► ... (same shape, created automatically for future partitions)
```

---

## Maintenance

**Creating partitions ahead of time** is the whole game — a missing partition means
writes fail (or land in `default`). Options, in increasing sophistication:

| Approach | Mechanism | Good enough here? |
|----------|-----------|-------------------|
| Cron + `CREATE TABLE ... PARTITION OF` | simplest, most explicit | **yes** |
| A trigger/default + alert | writes never fail | maybe |
| `pg_partman` extension | automates creation, retention, and optional time-based interval/ native partitioning | the standard answer at scale |

**For this project:** a monthly cron that creates `expenses_<next month>` three days
before month end, alerting if `expenses_default` is non-empty. Simple, reviewable, and
it fails loudly rather than silently.

**Autovacuum/analyze runs per partition** — so a hot current partition gets vacuumed on
its own dead-tuple count, and a cold archived one is never touched again. That's a real
operational win over one giant table (see [`vacuum-bloat.md`](vacuum-bloat.md)).

---

## Archival: DROP vs DELETE

This is the reason to partition. The comparison is not subtle.

```
   DELETE 5M rows from expenses_2026_07:

   ┌───────────────────────────────────────────────────────────────────┐
   │ 1. finds rows (index or seq scan)        ── cost: read 5M rows   │
   │ 2. writes a WAL record PER ROW           ── cost: 5M WAL records │
   │ 3. marks rows dead (MVCC)                ── creates dead tuples  │
   │ 4. indexes need cleanup too              ── 5M index entries     │
   │ 5. autovacuum must later reclaim         ── another full pass    │
   │ 6. table file DOES NOT SHRINK            ── bloat remains        │
   └───────────────────────────────────────────────────────────────────┘
      result: minutes to hours, heavy WAL, and you need VACUUM FULL after

   DROP TABLE expenses_2026_07  (after archiving):

   ┌───────────────────────────────────────────────────────────────────┐
   │ 1. one catalog entry removed             ── O(1) metadata         │
   │ 2. unlink the file                      ── O(1) filesystem        │
   │ 3. no row-level WAL                     ── nothing                │
   │ 4. no dead tuples, no vacuum needed     ── nothing                │
   └───────────────────────────────────────────────────────────────────┘
      result: milliseconds
```

**The safe archival sequence** (the one in [`../data-lifecycle.md`](../data-lifecycle.md)):

```sql
BEGIN;
-- 1. take the partition out of the live table without dropping it
ALTER TABLE expenses DETACH PARTITION expenses_2026_07 CONCURRENTLY;

-- 2. export it to cold storage (COPY TO, or pg_dump -t)
--    VERIFY the archive is complete and readable BEFORE proceeding

-- 3. only now, drop it
DROP TABLE expenses_2026_07;
COMMIT;
```

`DETACH ... CONCURRENTLY` (PG14+) avoids taking an `ACCESS EXCLUSIVE` lock on the parent
while detaching, so live traffic doesn't stall. Without `CONCURRENTLY`, the detach blocks
all reads/writes to `expenses` for the duration.

**Why DETACH before DROP:** if the export fails or the archive is corrupt, the partition
is still intact and you can `ATTACH` it back. The irreversible step is last, and only
after verification.

---

## Table inheritance — the legacy alternative

Before declarative partitioning (PG10), people used `INHERITS`:

```sql
CREATE TABLE expenses_2026_10 (CHECK (occurred_at >= '2026-10-01' AND ...))
  INHERITS (expenses);
```

Differences that matter:

- **Pruning requires an explicit `CHECK` constraint** and `constraint_exclusion` — the
  planner doesn't infer ranges from the inheritance.
- **Inserts don't route automatically** — you need a trigger or `INSERT ... ON ...` into
  the parent with a rule.
- No `ATTACH`/`DETACH` semantics, no parent-wide index management.

**When it's still the right tool:** when children have **different columns**, not just
different rows (declarative partitioning requires identical schemas). Otherwise prefer
declarative partitioning.

---

## The planner is a planner, not an optimizer

This distinction is the single most impressive thing you can say precisely in an
interview.

```
   A true OPTIMIZER (e.g. some research engines, Volcano/Cascades family):
     ┌──────────────────────────────────────────────────────────────┐
     │  enumerate a large space of equivalent plans, cost each one, │
     │  apply rewrite rules (predicate pushdown, join reordering,   │
     │  subquery unnesting) to GENERATE candidates, then pick       │
     └──────────────────────────────────────────────────────────────┘

   PostgreSQL's PLANNER:
     ┌──────────────────────────────────────────────────────────────┐
     │  a fixed, mostly hard-coded plan skeleton (scan → join →     │
     │  aggregate → sort → limit), with:                            │
     │    • a bounded set of join-order heuristics                   │
     │      (dynamic programming up to geqo_threshold join rels,    │
     │       then GEQO genetic search)                              │
     │    • a cost model over that skeleton                         │
     │    • limited equivalence rewrites                             │
     │  It does NOT discover a novel plan shape.                    │
     └──────────────────────────────────────────────────────────────┘
```

Consequences you can act on:

- **It will not rewrite your query into a smarter one.** A badly-shaped query is
  planned badly, reliably. Fix the SQL.
- **Join order** matters and is chosen heuristically. Beyond ~12 tables
  (`geqo_threshold`) it switches to a genetic algorithm — plans become less
  predictable. **Keep joins small.**
- **Statistics are the cost model's whole world.** Bad stats → bad plans. `ANALYZE`
  after bulk loads; consider raising `default_statistics_target` on skewed columns.
- `effective_cache_size` is a **hint**, not an allocation: it tells the planner how much
  memory it may assume is cached, biasing index scans up and seq scans down. Set it to
  ~50–75% of RAM (see [`tuning-and-observability.md`](tuning-and-observability.md)).

---

## When a seq scan is the RIGHT plan

Beginners see `Seq Scan` and reach for an index. Often that's wrong.

```
   seq scan wins when:
   ┌────────────────────────────────────────────────────────────────┐
   │ • the table is small (a few hundred rows) — one page read beats │
   │   an index descent + heap fetch per row                        │
   │ • the query returns a large fraction of the table (> ~5–10%)   │
   │   — random I/O via the index is slower than reading it all     │
   │ • rows are physically clustered in the query's order (a fresh  │
   │   table, or a HOT-inserted append-only log)                    │
   │ • the index would need many heap fetches anyway (low           │
   │   correlation between index order and heap order)              │
   └────────────────────────────────────────────────────────────────┘

   seq scan is suspicious when:
   ┌────────────────────────────────────────────────────────────────┐
   │ • the table is large AND the predicate is highly selective     │
   │ • pg_stat_user_tables shows seq_scan climbing on that table    │
   │ • the plan's estimated rows ≫ returned rows (stale statistics) │
   └────────────────────────────────────────────────────────────────┘
```

**The diagnostic that settles it:** `EXPLAIN (ANALYZE, BUFFERS)`. Compare
`rows=` (estimated) with `rows=` (actual, in parentheses) and look at
`shared read` vs `shared hit`. A seq scan reading 8 buffers for 8 rows is *correct*; a
seq scan reading 800,000 buffers for 8 rows is the bug.

---

## Query-shape gotchas worth memorizing

**`NOT IN` vs `NOT EXISTS` with NULLs:**

```sql
-- if the subquery returns ANY NULL, NOT IN returns NO ROWS AT ALL
SELECT * FROM expenses WHERE category_id NOT IN (SELECT id FROM categories WHERE ...);
-- because: x NOT IN (1, 2, NULL)  ≡  x<>1 AND x<>2 AND x<>NULL  ≡  x<>1 AND x<>2 AND UNKNOWN

-- NOT EXISTS has no NULL pathology
SELECT * FROM expenses e WHERE NOT EXISTS (SELECT 1 FROM categories c WHERE c.id = e.category_id);
```

**Prepared statements and plan caching:** Postgres caches plans for prepared statements
after 5 executions. A generic plan is used when it's expected to be cheaper than custom
plans — good for stable queries, bad when a parameter's selectivity varies wildly (a
`user_id` that's usually selective but sometimes matches 90% of rows). `PLAN CACHE MODE
FORCE_CUSTOM_PLAN` overrides per-statement (PG12+).

**`pg_prewarm`** loads a relation into `shared_buffers` before it's needed — useful after
a restart for a hot index you know will be hit, and a nice thing to know exists.

**Correlated subqueries** are often planned as nested loops — fine for small driving
sets, terrible for large ones. Rewrite as a join or a `LATERAL` when the driving set is
big.

---

## Interview angle

- **"How would you design an append-heavy event table?"** — RANGE partitioning by time,
  monthly partitions created ahead, index on the hot access path, archive by
  DETACH→export→verify→DROP, monitor `default` partition occupancy.
- **"Why is Postgres not a true optimizer?"** — fixed plan skeleton, bounded heuristics,
  GEQO past a threshold; it costs plans rather than discovering them. Hence: write good
  SQL, keep joins small, keep stats fresh.
- **"When is a seq scan the right choice?"** — small tables, low-selectivity predicates,
  clustered physical order. Back it with `EXPLAIN (ANALYZE, BUFFERS)`.
- **"How do you delete a billion rows?"** — don't. Partition and DROP; or batch with
  `DELETE ... WHERE ctid IN (SELECT ... LIMIT 10000)` in a loop with commits, if you
  must stay in one table.
- **"Unique constraint on a partitioned table?"** — must include the partition key;
  plan the PK accordingly.

---

## How this shows up here

- `expenses` and `balance_changes` are RANGE-partitioned by month
  ([`../data-lifecycle.md`](../data-lifecycle.md)).
- The archival job is exactly `DETACH CONCURRENTLY` → export → verify → `DROP`, guarded
  by an advisory lock ([`../runbooks.md`](../runbooks.md)).
- A cron creates next month's partition; an alert fires if `expenses_default` is
  non-empty.
- The main query path — "my expenses this month by category" — prunes to one or two
  partitions and uses `(user_id, occurred_at DESC)` ([`indexes.md`](indexes.md)).
- We keep the join count low (expenses → categories → sources → loans) to stay well
  under `geqo_threshold`.
