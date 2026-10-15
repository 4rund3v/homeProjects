# Storage — Pages, Heaps, HOT Chains, TOAST

> How Postgres physically stores a row, why updates rewrite pages, and why a "simple"
> UPDATE touches disk. Mechanism first, then this project's `expenses`/`loans` tables.

## The hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CLUSTER (a single Postgres instance on one machine)                        │
│                                                                             │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│   │   database: app  │  │  database: postgres│  │  database: ...   │        │
│   └────────┬─────────┘  └──────────────────┘  └──────────────────┘          │
│            │                                                                │
│            │  each database is a directory of relation files                  │
│            ▼                                                                │
│   ┌──────────────────────────────────────────────────┐                       │
│   │  relations (each table + index = one or more      │                       │
│   │  8KB files, called "segments" after 1GB)          │                       │
│   │                                                   │                       │
│   │   expenses   →  base/16384/24576                  │                       │
│   │   expenses_pkey → base/16384/24581  (index)       │                       │
│   └──────────────────────────────────────────────────┘                       │
│                                                                             │
│   shared:  pg_wal/  ·  pg_xact/ (clog)  ·  pg_stat/  ·  ...                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

Tablespaces sit above databases and let you move a table's files to another disk
(`CREATE TABLESPACE fast ON '/mnt/nvme'`). On a single k3s node you'll likely use only
the default tablespace; the concept matters for "put cold archives on cheap disk" and for
interviews.

**Everything below the relation is fixed 8KB blocks.** Postgres calls a block a *page*.
`block_size` is set at cluster init (usually 8192) and can never change without a
dump/reload. This one constant explains a lot of later behavior.

---

## A heap page, laid out

```
  page header (24 bytes)
  ┌──────────────────────────────────────────────────────────────────┐
  │ pd_lsn │ pd_checksum │ pd_lower │ pd_upper │ pd_special │ flags  │
  └──────────────────────────────────────────────────────────────────┘

  item identifier array ("line pointers") — grows DOWNWARD from the header
  ┌────────┬────────┬────────┬────────┬────────┬────────┐
  │  lp 1  │  lp 2  │  lp 3  │  lp 4  │ (free) │ (free) │
  └────────┴────────┴────────┴────────┴────────┴────────┘
       │        │        │        │
       │        │        │        └──────────────┐
       ▼        ▼        ▼                       ▼
  ┌────────┐┌────────┐┌────────┐          ┌─────────────────┐
  │ tuple  ││ tuple  ││ tuple  │          │                 │
  │ (row)  ││ (row)  ││ (row)  │   ...    │   free space    │
  └────────┘└────────┘└────────┘          │                 │
                                          └─────────────────┘
  special space (index pages only) — grows UPWARD from the end
```

**The trick to remember:** line pointers grow down, tuples grow up, free space is in the
middle. A row's physical address is its **TID** `(page_number, line_pointer_index)` —
you see it as the hidden `ctid` column.

**Why this layout matters:** when you `UPDATE` a row and the new version doesn't fit in
the old space, Postgres appends a new tuple to the page (or a new page), writes a new
line pointer, and marks the old one dead. The line pointer indirection is what makes HOT
updates possible (below) without touching indexes.

---

## Tuple layout

```
  tuple header (23 bytes, fixed)
  ┌──────────────────────────────────────────────────────────────┐
  │ xmin (4) │ xmax (4) │ cmin/cmax (4) │ ctid (6) │ infomask (2)│
  │  ... hint bits live here ... │ null bitmap (if nullable cols) │
  └──────────────────────────────────────────────────────────────┘
  user data: the column values, in declared order, with alignment padding
```

`xmin`/`xmax` are the MVCC machinery (see [`mvcc.md`](mvcc.md)). The `ctid` field is the
tuple's *own* address — which lets a HOT chain point from the new version back to the old
one. Alignment padding is why `ORDER BY` of column types can change storage size; it's
rarely worth optimizing on.

---

## HOT updates — the performance-relevant one

A **HOT (Heap-Only Tuple) update** is an update that only changes non-indexed columns.
Because the new version can be reached from the old version's line pointer, **no index
entry needs to change**.

```
  BEFORE:  index entry ──► line pointer 3 ──► tuple v1 (xmax = 0)

  UPDATE expenses SET note = 'checked' WHERE id = 101;   -- note is not indexed

  WITHOUT HOT (a non-HOT update, e.g. updating amount_cents which IS indexed):
    index entry ──► new line pointer ──► tuple v2      (index entry REWRITTEN)
    old line pointer marked dead, tuple v1 xmax = T_B

  WITH HOT (note not in any index):
    index entry ──► line pointer 3 ──► tuple v1 (xmax = T_B, ctid → v2)
                                        tuple v2 (xmin = T_B, ctid → v1 or 0)
    ► INDEX UNTOUCHED
    ► vacuumer later stitches v1's line pointer to point directly at v2
      and reclaims v1's space
```

**Consequences you should be able to state in an interview:**
- HOT is *why* updating non-indexed columns is cheap even with many indexes.
- HOT is *lost* when the page has no free space (the new version must go to a different
  page, breaking the chain), which is why `fillfactor` matters on update-heavy tables.
- HOT requires the *old* tuple's `xmax` to have been set by the *same* transaction and no
  index columns changed — check `n_tup_hot_upd` vs `n_tup_upd` in `pg_stat_user_tables`.
- Our `expenses` table is mostly INSERT + occasional note edit → high HOT ratio if we
  keep the indexed column set small.

---

## Fillfactor

`fillfactor` is the percentage of each page Postgres fills on INSERT before leaving free
space for future updates on the same page.

```sql
CREATE TABLE expenses ( ... ) WITH (fillfactor = 90);   -- default 100
-- or, after the fact:
ALTER TABLE expenses SET (fillfactor = 80);
```

- Default 100 = pack pages tight = great for INSERT-only tables (`balance_changes`,
  `outbox` events) = bad for frequently-updated tables (`loans.outstanding` changes often).
- Lower fillfactor → more pages touched → larger table, but more HOT updates and less
  page splitting. For `loans`, a fillfactor around 80–90 is a reasonable first guess.
- Change is per-table and only affects *new* pages until a rewrite (`VACUUM FULL`,
  `CLUSTER`) repacks existing ones.

---

## TOAST — when a row doesn't fit

Postgres will not store a value larger than ~2KB inline. Longer values go to the **TOAST
table** (The Oversized-Attribute Storage Technique), and the main tuple keeps a pointer.

```
  user row with a 100KB `note`
  ┌───────────────────────────────┐        ┌──────────────────────────────┐
  │  expenses tuple               │        │  TOAST table (pg_toast_*)    │
  │  ┌─────────────────────────┐  │        │  ┌────────┐ ┌────────┐       │
  │  │ id, user_id, amount, ...│  │        │  │ chunk 1│ │ chunk 2│ ...    │
  │  │ note = <TOAST pointer> ─┼──┼───────►│  │ ~2KB   │ │ ~2KB   │       │
  │  └─────────────────────────┘  │        │  └────────┘ └────────┘       │
  └───────────────────────────────┘        └──────────────────────────────┘

  strategies per column (SET STORAGE):
    EXTENDED (default) — compress, then toast if still too big
    EXTERNAL           — toast, never compress  (for already-compressed data)
    PLAIN              — never toast (fails if > ~1GB limit)
    MAIN               — compress inline, try hard to avoid toast
```

- Values ≤ ~2KB (roughly `toast_tuple_threshold`, a quarter of a page) stay inline.
- Compression (pglz) runs first; if the result still exceeds the threshold, it's chunked
  into the TOAST table.
- Detoasting happens on read — so a wide row can be cheap to store but expensive to
  select. `SELECT note` on 100KB values is I/O you don't want in a hot path.
- **For this project:** `expenses.note` is short; nothing needs TOAST. But if you later
  attach receipts/images, set `SET STORAGE EXTERNAL` on already-compressed bytes and keep
  the main row narrow.

---

## The buffer cache vs the OS cache

```
   client query
       │
       ▼
   ┌─────────────────────────────────────────────┐
   │ shared_buffers  (Postgres's own cache)      │  e.g. 1GB
   │  8KB pages, LRU-ish with clock sweep        │
   └───────────────┬─────────────────────────────┘
       hit         │ miss
       ◄───────────┘
                   ▼
   ┌─────────────────────────────────────────────┐
   │ OS page cache  (the kernel's file cache)    │  "the rest of RAM"
   └───────────────┬─────────────────────────────┘
       hit         │ miss
       ◄───────────┘
                   ▼
                disk
```

- A page is read from disk **once** and lands in the OS cache; Postgres then copies it
  into `shared_buffers`. So a "miss" on `shared_buffers` is often still an OS-cache hit —
  fast, but not free (a memcpy).
- This is why `effective_cache_size` should reflect *both* caches: it's the planner's
  estimate of "what's effectively in memory," which nudges it toward index scans over seq
  scans.
- Writes go to `shared_buffers` first (dirty pages), get a WAL record (see
  [`wal.md`](wal.md)), and flush to disk at checkpoints or when the cache is under
  pressure.

---

## Writes: from statement to durable

A single `UPDATE loans SET outstanding = outstanding + 4250 WHERE id = 42`:

```
 1. Parse/plan (cached if prepared)
 2. Find the row: index scan on loans_pkey → TID (page 3, lp 2)
 3. Page 3 into shared_buffers (from disk or OS cache if needed)
 4. Build new tuple v2 in memory; set v1.xmax = this xid, v2.xmin = this xid
 5. Write WAL record(s): the page image change (or full-page if first touch since
    checkpoint), recorded with an LSN
 6. At COMMIT: write a COMMIT WAL record; fsync WAL if synchronous_commit = on
 7. Return success to client  ── the page may STILL be dirty in shared_buffers
 8. Later: checkpoint or bgwriter flushes the dirty page to disk; only then does the
    data file match WAL
```

**The one-liner for interviews:** *WAL is written and fsynced before the commit is
acknowledged; the data page is flushed lazily. That's write-ahead logging.* If the
machine crashes between step 7 and 8, recovery replays WAL to redo the page change.

---

## Interview angle

- **"What's a page, and why does it matter?"** — 8KB block; every I/O, index, and vacuum
  decision is at page granularity. Row size relative to page size drives everything.
- **"What is a TID?"** — `(block, offset)`, the physical row address. It changes after
  `VACUUM FULL`/`CLUSTER`, which is why you never store a TID as a foreign key.
- **"What's a HOT update and why do we want it?"** — update that touches no indexed
  column, so indexes don't need new entries; keeps write amplification low.
- **"When does TOAST kick in?"** — value > ~2KB (a quarter page) after compression.
  Detoasting is read cost.
- **"Why does an UPDATE cost more than an INSERT?"** — new tuple version + WAL + index
  entries (unless HOT) + eventually vacuum.
- **"shared_buffers vs OS cache?"** — two levels; the planner needs `effective_cache_size`
  to cover both; a miss isn't necessarily a disk read.

## How this shows up here

- `loans` is updated on every card expense → set a lower `fillfactor` there so HOT chains
  form and pages don't split.
- `balance_changes` and `outbox` are append-mostly → default `fillfactor=100` is right.
- `expenses.note` stays short; if receipts arrive later, `SET STORAGE EXTERNAL`.
- The consumer's row lock doesn't change *where* the row lives, but the UPDATE it performs
  does — see [`locking-concurrency.md`](locking-concurrency.md).
- WAL settings that determine when step 6 actually hits disk are in [`wal.md`](wal.md).
