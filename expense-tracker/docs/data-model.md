# Data Model

> The schema you'll **converge on** through the phases — presented as reasoning, not a
> final DDL. Your entities come from [`domain-decomposition.md`](domain-decomposition.md);
> the modeling rules are in [`postgres-guide.md`](postgres-guide.md) §2. Build the
> tables in Phase 2, split into apps in Phase 4, partition the event tables in Phase 8.

This doc is the *target shape* to reason about, not a file to copy. If your
decomposition exercise produced something different and you can defend it, yours wins.

---

## 1. Entity map

```
User ──1:N── Expense ──N:1── Category
                │
                ├──N:1── Source
                │
                └──N:1(optional)── Loan ──1:N── BalanceChange
                                        │
User ──1:N──────────────────────────────┘

Outbox (1:1 with an event, written in the expense transaction)
```

**The relationship to think hardest about:** `Expense → Loan` is **optional** and only
set when the expense is credit-paid. That optionality is a real domain rule and
becomes a `CHECK` constraint, not a nullable column you forget about.

---

## 2. Core tables (conceptual)

Presented as *fields + the rules they encode*, not DDL. Types follow
[`postgres-guide.md`](postgres-guide.md) §2.

### users
Provided largely by Django's auth, extended as needed. Owns identity; everything else
references `user_id`.

### categories
| Field | Notes |
|-------|-------|
| id | PK |
| user_id | FK → users; categories are per-user |
| name | `UNIQUE (user_id, name)` — a user can't have two "Groceries" |
| kind | lookup table or enum; decide per [`postgres-guide.md`](postgres-guide.md) §2 |

**Rule:** categories are user-scoped, not global. Don't share one user's categories
with another.

### sources
Where money comes from: bank account, cash, a card.
| Field | Notes |
|-------|-------|
| id | PK |
| user_id | FK |
| name | e.g. "HDFC Credit Card", "Cash" |
| kind | cash / bank / card / other |
| linked_loan_id | FK → loans, **nullable**; set when this source is a credit instrument |

**The Card decision lives here** (from [`domain-decomposition.md`](domain-decomposition.md)
§5): is a card a `kind` of source that *links to* a loan, or a separate entity? The
model above treats a card as a source whose `linked_loan_id` points at the credit
account it draws on. That's a defensible default: it keeps "where money came from"
(source) separate from "what I owe" (loan), while linking them. Defend or change this
deliberately.

### expenses
| Field | Notes |
|-------|-------|
| id | PK (bigint or uuid — decide) |
| user_id | FK → users; **ownership anchor** |
| amount | `numeric`, `CHECK (amount > 0)` |
| currency | ISO code; part of the Money value object |
| category_id | FK → categories |
| source_id | FK → sources |
| loan_id | FK → loans, **nullable** — set only when credit-paid |
| payment_kind | cash / credit / etc. |
| occurred_at | `timestamptz` — when the expense happened |
| created_at | `timestamptz` — when it was recorded |
| note | optional |

**Invariants as constraints:**
- `CHECK (amount > 0)`
- `CHECK ((payment_kind = 'credit') = (loan_id IS NOT NULL))` — credit-paid ⟺ has a
  loan. This single CHECK encodes the optional-loan rule.
- `FOREIGN KEY (user_id)` and ownership enforced in the API
  ([`drf-jwt-guide.md`](drf-jwt-guide.md) §5).

**Indexes** (from [`postgres-guide.md`](postgres-guide.md) §3):
- `(user_id, occurred_at DESC)` — "my recent expenses"
- `(user_id, category_id)` — spend by category
- `(loan_id)` — "expenses on this loan" (also a FK)

### loans (credit accounts)
| Field | Notes |
|-------|-------|
| id | PK |
| user_id | FK |
| name | e.g. "HDFC Millennia" |
| kind | card / personal loan / line of credit |
| credit_limit | `numeric`, optional |
| outstanding | `numeric`, `CHECK (outstanding >= 0)` — **the projection** |
| currency | ISO |
| opened_at / closed_at | `timestamptz`; `closed_at` nullable |
| status | open / closed |

**Key idea:** `outstanding` is a **projection** — the sum of the loan's balance changes
([`data-lifecycle.md`](data-lifecycle.md) §5). It's the fast-read value; the
`balance_changes` table is the source of truth.

### balance_changes (the event log)
| Field | Notes |
|-------|-------|
| id | PK |
| loan_id | FK → loans |
| event_id | **UNIQUE** — the idempotency key from [`kafka-guide.md`](kafka-guide.md) §3 |
| amount | `numeric`, signed (a charge increases outstanding; a payment decreases it) |
| expense_id | FK → expenses, nullable (a change may come from a payment, not an expense) |
| occurred_at | `timestamptz` |
| created_at | `timestamptz` |

**The load-bearing constraint:** `UNIQUE (event_id)`. This is what makes the consumer
idempotent at the database level — applying the same event twice is a constraint
violation the app treats as "already applied, skip."

**The reconciliation invariant** (not a single-row constraint): for each loan,
`sum(balance_changes.amount) = loans.outstanding`. Enforced in the consumer's
transaction; *verified* by the scheduled reconciliation check
([`data-lifecycle.md`](data-lifecycle.md) §5).

### outbox
| Field | Notes |
|-------|-------|
| id | PK |
| event_id | UNIQUE — same id as the event and the consumer's idempotency key |
| topic | target topic |
| key | the message key (`loan_id`) |
| payload | the serialized event (or the data to serialize) |
| created_at | `timestamptz` |
| sent_at | `timestamptz`, nullable — null = unsent |
| attempts | int — for poison-message routing to a DLQ |

**Written in the same transaction as the expense insert** ([`event-flows.md`](event-flows.md)
§1). The relay reads `WHERE sent_at IS NULL ... FOR UPDATE SKIP LOCKED`.

---

## 3. Partitioning plan (Phase 8)

Per [`data-lifecycle.md`](data-lifecycle.md) §3, partition the time-series tables by
range:

- **expenses** — partition by `occurred_at` (monthly ranges).
- **balance_changes** — partition by `occurred_at` (monthly ranges).

Small, slow-growing tables (users, categories, sources, loans, outbox) don't need
partitioning — partition only what you archive. Design the partition key in from the
start; retrofitting partitioning onto a live table is painful
([`postgres-guide.md`](postgres-guide.md) §7).

---

## 4. What this model gives you

- **Ownership is unambiguous** — `user_id` on every user-scoped table; enforced in the
  API and constrained in the DB.
- **The optional-loan rule is a constraint**, not a comment — the CHECK encodes it.
- **Idempotency is a DB constraint**, not hopeful app code — `UNIQUE (event_id)`.
- **Balances are rebuildable** — `balance_changes` is the source of truth;
  `outstanding` is a projection you can recompute.
- **Archival is cheap** — partitioning the two event tables makes tier transitions
  metadata operations.
- **The event boundary is clean** — the outbox + Avro contract
  ([`avro-guide.md`](avro-guide.md)) is the only coupling between the API and the
  consumer.

---

## 5. Decisions to lock in before Phase 2

Record each in [`design.md`](design.md):

- [ ] ID strategy: `bigint` identity vs `uuid` (and why).
- [ ] Money: precision/scale and how currency is stored.
- [ ] `category.kind` and `expense.payment_kind`: native enum vs lookup table.
- [ ] The Card decision: source-with-linked-loan vs separate entity.
- [ ] Partition key and range for expenses and balance_changes.
- [ ] The `event_id` type and where it's generated (app vs DB).
- [ ] `ON DELETE` behavior for each FK (RESTRICT / CASCADE / SET NULL).
- [ ] Whether `linked_loan_id` on sources is enforced with a constraint or by
      convention.
