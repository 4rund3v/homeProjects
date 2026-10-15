# Indexes — B-trees, Scans, and Reading EXPLAIN

> The most-tested Postgres topic in interviews and the one that most often decides
> whether a feature is fast. Mechanism first, then the `expenses` query we actually run.

## What an index is (and isn't)

An index is a **separate data structure** that maps a search key to row locations (TIDs).
It costs storage and write time, and it buys read time — *for the queries it matches*.

```
   table (heap)                       index (B-tree on user_id, occurred_at)
   ┌───────────────────────┐          ┌───────────────────────────────────┐
   │ TID      user  amount │          │  key ────────────────► TID        │
   │ (5,1)      7    4200  │◄─────────│  (7, '2026-10-01')  ──► (5,1)     │
   │ (5,2)      7    1500  │          │  (7, '2026-10-03')  ──► (5,2)     │
   │ (5,3)      9     999  │          │  (7, '2026-10-14')  ──► (6,1)     │
   │ ...                   │          │  (9, '2026-10-02')  ──► (5,3)     │
   └───────────────────────┘          └───────────────────────────────────┘

   Finding "user 7's October expenses" = index descent (log n) + heap fetches
   Finding them WITHOUT the index      = read every page, filter as you go (seq scan)
```

**Indexes are not free.** Every `INSERT`/`UPDATE`/`DELETE` maintains every index. The
classic failure is adding ten indexes "just in case" and wondering why writes crawl.

---

## B-tree structure

Postgres's default index type is a **B-tree** (Lehman-Yao variant, which allows
concurrent inserts without global locking).

```
                          ┌─────────────────────────┐
                  ROOT    │ [30 | 60]               │
                          └───┬─────────────────┬───┘
                              │                 │
              ┌───────────────▼──┐        ┌─────▼───────────────┐
   INTERIOR   │ [10|20]         │        │ [40|50|70|80]       │
              └──┬───────────┬──┘        └──┬────┬────┬────┬────┘
                 │           │               │    │    │    │
       ┌─────────▼─┐ ┌───────▼────┐ ┌──────▼─┐┌──▼───┐┌▼──────┐┌▼─────┐
 LEAF  │ 5 8 10 12 │ │ 15 18 20 25│ │ ... 40 ││ ...50││ ...70││ ...90│
       │ TID TID  │ │  TID  TID  │ │        ││      ││      ││      │
       └──────────┘ └─────────────┘ └────────┘└──────┘└──────┘└──────┘
            └──────────── all leaves linked in key order ─────────┘
```

Key properties:
- **Leaves hold the actual index entries** (key + TID), sorted, and doubly-linked so a
  range scan walks them in order without going back up.
- **Interior pages hold separator keys** only — enough to route a descent. For a table of
  N rows with fanout F, depth is ~log_F(N): millions of rows fit in 3–4 levels.
- **All leaf pages are at the same depth** — that's what makes the B-tree balanced and
  the cost predictable.
- A B-tree supports **equality** (`=`), **range** (`<`, `BETWEEN`), **ordering**
  (`ORDER BY`), **prefix matching** (`LIKE 'abc%'`), and **uniqueness**.

---

## Composite index column order — the rule that decides everything

For an index on `(a, b, c)`, think of it as sorted by `a`, then `b`, then `c`.

```
   index on (user_id, occurred_at, category_id), some entries:

   (7, 2026-10-01, 3)
   (7, 2026-10-01, 9)
   (7, 2026-10-03, 3)     ◄── ordered by user_id, then date, then category
   (7, 2026-10-14, 3)
   (9, 2026-10-02, 3)
   (9, 2026-10-05, 9)
```

**The ordering rule:**
1. Put **equality** columns first (`WHERE user_id = 7`).
2. Then **one range/sort** column (`WHERE occurred_at > '2026-10-01'`, or
   `ORDER BY occurred_at`).
3. Additional columns after the range are useful only for **index-only scans**
   (`INCLUDE`) or as extra filters, not for seeking.

**What each query can use:**

| Query | Uses the index? | Why |
|-------|-----------------|-----|
| `WHERE user_id = 7 AND occurred_at > X` | Yes, fully seeks | equality then range |
| `WHERE user_id = 7 ORDER BY occurred_at DESC` | Yes, no sort step | index is already in that order |
| `WHERE occurred_at > X` | Poorly (scan whole index) | leading column missing |
| `WHERE category_id = 3 AND user_id = 7` | Yes (user_id part only) | order in the index ≠ order in WHERE |
| `WHERE user_id = 7 AND occurred_at > X AND category_id = 3` | Seeks user+date, filters category | range stops further seeking |

**The interview one-liner:** *equality columns first, then at most one range/sort column;
the WHERE-clause order is irrelevant, the index column order is everything.*

**DESC indexes:** `(user_id, occurred_at DESC)` is a distinct index from
`(user_id, occurred_at)`. Postgres can scan a B-tree backwards, so `ASC` often serves
`ORDER BY ... DESC` — but mixed-direction `ORDER BY a ASC, b DESC` needs a matching index
or a sort node.

---

## Index types — which one and when

| Type | Best for | Notes |
|------|----------|-------|
| **B-tree** (default) | equality, range, sort, unique | covers 95% of cases |
| **Hash** | equality only, on long keys | slightly faster `=`; no ordering; rarely worth it |
| **GIN** | multi-value: arrays, `jsonb`, full-text | bigger, slower to update; great for `@>`, `@@` |
| **GiST** | geometric, range types, nearest-neighbor | lossy; needs recheck |
| **SP-GiST** | unbalanced trees, IP ranges, phone prefixes | niche |
| **BRIN** | huge append-only tables with physical↔logical correlation | tiny index; e.g. `balance_changes` by month |
| **Bloom** (access method) | many equality columns, very wide rows | experimental-ish; needs tuning |

**For this project:** B-tree everywhere except possibly a BRIN on
`balance_changes(created_at)` if that table gets huge and correlates with insert order.

---

## Partial, covering, expression, unique

```sql
-- Partial: index only the hot slice. Smaller, faster, only serves queries
-- whose WHERE implies the predicate.
CREATE INDEX expenses_open_idx
  ON expenses (user_id, occurred_at DESC)
  WHERE payment_kind = 'credit';

-- Covering (INCLUDE): extra columns carried in the leaf so the heap is never visited.
CREATE INDEX expenses_user_date_idx
  ON expenses (user_id, occurred_at DESC)
  INCLUDE (amount_cents, category_id);

-- Expression: index a computed value.
CREATE INDEX users_lower_email_idx ON users (lower(email));

-- Unique: enforces a domain rule in the DB, not just the app.
CREATE UNIQUE INDEX one_open_loan_per_source
  ON loans (source_id) WHERE closed_at IS NULL;
```

**Partial index discipline:** the planner only uses it when it can *prove* your query's
WHERE implies the index predicate. `WHERE payment_kind = 'credit'` matches;
`WHERE payment_kind = $1` with a parameter may not, unless the planner specializes the
plan (it often does with a generic plan after enough executions).

**Unique partial indexes** are how you express "at most one X under condition Y" — a real
invariant from [`../domain-decomposition.md`](../domain-decomposition.md), enforced once
in the schema.

---

## Index-only scans and the visibility map

An **index-only scan** answers a query from the index alone, no heap visits — *if* every
column needed is in the index (via key columns or `INCLUDE`) **and** the visibility map
says the page is all-visible.

```
   query: SELECT amount_cents FROM expenses WHERE user_id = 7 AND occurred_at > '...'

   ┌──────────────────────────────────────────────────────────────┐
   │ 1. descend index on (user_id, occurred_at) INCLUDE (amount)  │
   │ 2. for each matching leaf entry: is the page all-visible?    │
   │      YES ──► return amount straight from the index           │
   │      NO  ──► heap fetch to check visibility (MVCC xmin/xmax) │
   └──────────────────────────────────────────────────────────────┘

   heap_fetches in EXPLAIN ANALYZE ≈ 0  ⇒  the VM is doing its job
   heap_fetches climbing                 ⇒  run VACUUM, or accept the fetches
```

This is the payoff for keeping vacuum current: an under-vacuumed table silently degrades
from index-only scans to index scans + heap fetches
([`vacuum-bloat.md`](vacuum-bloat.md)).

---

## Reading `EXPLAIN (ANALYZE, BUFFERS)`

Always use `ANALYZSE` (actually runs the query) and `BUFFERS` (shows cache vs disk).
Add `VERBOSE` when confused.

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT amount_cents, category_id
FROM expenses
WHERE user_id = 7
  AND occurred_at >= now() - interval '30 days'
ORDER BY occurred_at DESC
LIMIT 50;
```

```
Limit  (cost=0.42..8.75 rows=50 width=16) (actual time=0.031..0.089 rows=50 loops=1)
  Buffers: shared hit=7                                   ◄── 7 pages, all from cache
  ->  Index Scan Backward using expenses_user_date_idx on expenses
        (cost=0.42..312.4 rows=1780 width=16)
        (actual time=0.029..0.081 rows=50 loops=1)
        Index Cond: ((user_id = 7) AND
                     (occurred_at >= (now() - '30 days'::interval)))   ◄── seek range
        Buffers: shared hit=7
Planning Time: 0.112 ms
Execution Time: 0.104 ms
```

**How to read it:**
- Read **inside-out, bottom-up**: the deepest node runs first, its output feeds the parent.
- **`Index Scan Backward`** — walking the index in reverse to satisfy `DESC` without a sort.
- **`Index Cond`** — the part done *by the index* (a seek). **`Filter`** — the part done by
  re-checking the row after fetching (a missed opportunity; often means a better index).
- **`rows` estimate vs actual** — a big gap means stale stats; run `ANALYZE`.
- **`Buffers: shared hit=N read=M`** — `hit` = served from cache, `read` = from disk. High
  `read` on a hot query = memory problem or a cold cache.
- **`cost=..`** — the planner's *arbitrary units* estimate (1.0 ≈ one sequential page
  fetch by convention). Not milliseconds. Compare costs, don't read them as time.
- **`loops`** — under a nested loop, multiply the node's actual time by loops.

**The two node names you must recognize:**
- `Seq Scan on <table>` — full table scan. **Sometimes correct**: a query returning 30% of
  a small table is cheaper as a seq scan than thousands of random heap fetches.
- `Index Scan` vs `Index Only Scan` vs `Bitmap Heap Scan` — the last builds a bitmap of
  TIDs then fetches in physical order, winning when many scattered rows match.

---

## When NOT to index

- **Low-cardinality columns** queried alone (`boolean is_active`): the planner will seq
  scan anyway unless the matching slice is tiny (then use a *partial* index).
- **Columns you never filter/sort/join on.** Dead weight on every write.
- **Small tables** (< a few hundred rows): seq scan is already microseconds.
- **Write-heavy tables where you haven't measured.** Every index is a write tax; the
  balance_changes/outbox tables deserve the fewest indexes.

**Find the dead ones** (see [`tuning-and-observability.md`](tuning-and-observability.md)):

```sql
SELECT relname, indexrelname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY relname;
-- indexes with 0 scans since the last stats reset are candidates to drop
```

---

## The write cost, concretely

```
   INSERT one row into a table with 4 indexes:

     1 heap tuple          → 1 page write (maybe)
     4 index entries       → up to 4 page writes + possible page splits
     WAL for all of the above

   UPDATE a row that changes an indexed column, with 4 indexes:

     new heap tuple       → 1 page write
     old tuple xmax set   → 1 page write
     4 new index entries  → up to 4 page writes
     WAL for all
     + a future VACUUM to reclaim the old versions
```

This is why `fillfactor`, HOT, and "do I need this index?" are the three levers on a
write-heavy table.

---

## Interview angle

- **"How would you index `WHERE user_id = ? ORDER BY created_at DESC LIMIT 20`?"** —
  `(user_id, created_at DESC)`; equality column first, then the sort column, so the index
  walk stops after 20 rows with no sort step.
- **"Why is my index not being used?"** — leading column not constrained, type mismatch
  (comparing `text` to `int`), function wrapping the column (`WHERE lower(x)=..` needs an
  expression index), stale stats, or the planner correctly choosing a seq scan.
- **"What's an index-only scan and what breaks it?"** — all columns in the index + VM
  all-visible; broken by stale vacuum or a column missing from the index.
- **"Cost of too many indexes?"** — write amplification, more WAL, more vacuum, more
  bloat, larger cache footprint.
- **"When is a seq scan the right plan?"** — large fraction of a small/medium table, or a
  query the planner estimates returns many rows.

## How this shows up here

- Main API query gets `(user_id, occurred_at DESC)`; consider
  `INCLUDE (amount_cents, category_id)` to make it index-only.
- `expenses(loan_id)` for "all expenses on this loan" — also an FK, so it's needed anyway
  to keep joins and cascade deletes fast.
- "One open loan per card" is a **unique partial index** — a domain invariant enforced in
  the schema (see [`../domain-decomposition.md`](../domain-decomposition.md) §3).
- `processed_events(event_id)` is unique — the idempotency gate
  ([`locking-concurrency.md`](locking-concurrency.md)).
- `outbox` gets exactly one index that serves the relay's `WHERE published_at IS NULL
  ORDER BY produced_at` — measure before adding more.
