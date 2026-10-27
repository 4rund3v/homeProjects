# DDD Tactical Patterns — Mapped to This Domain

> The DDD tactical patterns, each with a concrete example on this codebase and the
> interview framing. The single highest-leverage set of patterns for "how do I
> decompose a problem into classes and entities?" — which is the stated goal of this
> whole project.

---

## 1. Entity

**Definition:** an object with a **persistent identity** (an `id`) that stays the same
even as its attributes change. Two objects with the same attribute values are *different*
entities if their ids differ.

**In this project:** `Expense`, `Loan`, `Category`, `Source`.

```
  Two expenses:
    Expense(id=101, amount=4250, currency="USD", category="Groceries", when="...")
    Expense(id=102, amount=4250, currency="USD", category="Groceries", when="...")

  Same attribute values, different ids → two distinct entities.
  If you "copy" Expense #101, the copy still references the original's id (that's the
  test for entity-ness: can it be mistaken for another object?).
```

**The identity rule (critical for the Kafka decision):** an Entity's id is what you key
by. Because `Loan` is an Entity, its `loan_id` is stable and is the natural Kafka key
([`../kafka-guide.md`](../kafka-guide.md) §2).

**Interview angle:** *"Entity vs value object?"* — "An Entity is compared by reference
(id); a Value Object is compared by value. `Loan` is an Entity — two loans with the same
balance are still two loans. `Money(42.50, USD)` is a Value Object — every
`Money(42.50, USD)` is the same thing."

---

## 2. Value Object

**Definition:** an **immutable object with no identity, defined entirely by its
values.** Two VOs with the same field values are *equal*. They're a bundle of related
data + invariants that should always be treated as a unit.

**In this project:** `Money(amount, currency)`, `DateRange(start, end)`, `MoneyDelta`.

```
  class Money:
      amount: Decimal       # positive
      currency: str        # ISO code

  Money("42.50", "USD") == Money("42.50", "USD")   →  True
  Money("42.50", "USD").add(Money("1.00", "EUR"))   →  raises CurrencyMismatch

  The INVARIANTS (positive amount, single-currency arithmetic) live in ONE place,
  not scattered across serializers/views.
```

**Why VOs matter more than most people think:** they make the *type system* express the
domain rules. `Money` won't let you add currencies or go negative — that rule is
enforced by the type, not by a comment or a `if` somewhere.

**The interview follow-up:** *"Why not just store two `DECIMAL` columns?"* — You can,
but then "amount must be positive" is enforced by a DB `CHECK`, "currencies must
match" is enforced by scattered app `if`s, and every new place you do arithmetic has to
remember to re-check. A VO centralizes all of it, and the DB still gets a
`CHECK (amount > 0)` as a second line of defense ([`../data-model.md`](../data-model.md)
§2).

**Practical VO design rules:**
- **Immutable** — a `Money` doesn't have `.add_in_place()`, it returns a new `Money`.
  This keeps the VO safe to share across threads and safe to use as a dict key.
- **No identity** — no `id` field, no `__eq__` based on id.
- **Factory or constructor validates** — `Money.from_raw(user_input)` raises on bad
  currency, not the VO's `__init__` silently accepting it.

---

## 3. Aggregate (and Aggregate Root)

**Definition:** a **cluster of Entities and Value Objects that must be kept
consistent as a unit.** There's exactly one **Aggregate Root** — the only entity
outside the aggregate may hold a reference to, and the only entry point for changes.

This is the pattern that most determines the shape of a correctly-designed domain, and
the one you're most likely to be asked about in a systems interview because it drives
the Kafka partitioning decision.

**In this project:**

```
  ┌─────────────────────────────────────────────────┐
  │  AGGREGATE: Loan                                │
  │                                                 │
  │  Loan  (aggregate root — has id, has invariants)│
  │    ├── outstanding: Money          (derived)    │
  │    ├── credit_limit: Money                        │
  │    └── [balance_changes: list of MoneyDelta]     │  ← the source of truth
  │                                                 │
  │  INVARIANT: sum(balance_changes) == outstanding │
  └─────────────────────────────────────────────────┘

  Outside the aggregate: Expense (references Loan by id, NOT by object).
  The ONLY way to change Loan is through Loan.apply_change(delta).
```

**The two rules that make the aggregate *correct*, not just a naming convention:**

1. **The invariant spans the whole cluster.** "Sum of changes = outstanding" involves
   the `Loan` root AND its `balance_changes`. So the cluster is the unit of
   consistency — you can't enforce that invariant from inside a single entity.
2. **Outside code talks to the root only.** `Expense` holds `loan_id` (a reference
   key), never a `Loan` object. When you change the balance you call
   `loan.apply_change(delta)`, which internally keeps `balance_changes` and
   `outstanding` in lockstep. No code outside the aggregate touches `outstanding`
   directly.

**The interview question that reveals understanding:**
*"Why key the Kafka topic by `loan_id` and not `expense_id`?"*

```
  Because Loan is the aggregate, and the invariant spans the whole aggregate.
  Ordering matters per-AGGREGATE, not per-trigger:

    events for loan 42 MUST be applied in order (balance changes are cumulative)
    events for loan 43 MUST be applied in order
    ordering between loan 42 and loan 43 doesn't matter

  Key by loan_id → same loan = same partition = in-order delivery.
  Key by expense_id → two expenses on the same loan could land on different
  partitions and be applied out of order → corrupt balance.
```

This is the "the aggregate is the unit of consistency AND of ordering" insight — it's
the single best answer to a Kafka+domain question.

**The rule for finding your aggregates:** start from the invariants. Anything two
entities touch together to maintain an invariant is one aggregate. If you can't name
the invariant, you don't have an aggregate yet — you have two loosely-coupled
entities and a `loan_id` reference, and that's fine too.

---

## 4. Domain Service

**Definition:** a **stateless object that coordinates behavior that doesn't belong to
any single entity.** It's the "orchestrator" when an operation needs 2+ entities or
an external resource.

**The discipline (most-important part):** a domain service **orchestrates**; it does
not *contain* rules that should live on an entity. If your service is doing
`loan.outstanding += delta` directly, that rule belongs on `Loan` instead
([`../oop-principles.md`](../oop-principles.md) "Tell, Don't Ask").

**In this project:**

```
  class LoanService:                       # stateless — no instance data
      def apply_expense(loan: Loan, expense: Expense):
          # orchestration only:
          loan.apply_change(expense.delta)   # the RULE lives on Loan
          self.repo.save(loan)               # persistence

  class ExpenseService:
      def record(user, dto):
          # orchestration: validate → build VO → persist → publish event
          money = Money.from_raw(dto.amount, dto.currency)
          expense = Expense(user, money, ...)
          self.expense_repo.save(expense)
          self.outbox.enqueue(ExpenseRecorded(...))    # same transaction
```

**The test for "is this a domain service or just a view doing too much?":** if the
behavior is **purely about the domain** (balance rules, invariants, cross-entity
consistency), it's a domain service. If it's about **HTTP or the UI** (status codes,
pagination, serialization), it's a view/serializer. A service that formats JSON is in
the wrong place.

**Interview angle:** *"Why not just put it all in the model?"* — because the model
can't reach out to the outbox or two repos at once. The service is the *coordination*
layer; the model is the *rule* layer. Keep them separate and both stay testable.

---

## 5. Domain Event

**Definition:** a **record of something that already happened, in the domain, that
other parts of the system care about.** Immutable, past-tense, no behavior.

**In this project:** `ExpenseRecorded`, `LoanBalanceUpdated`.

```
  @dataclass(frozen=True)
  class ExpenseRecorded:
      event_id: str        # idempotency key
      expense_id: int
      loan_id: int | None
      amount: Money
      occurred_at: datetime
```

**The fact-not-command rule:** `ExpenseRecorded` (past tense) is an event. `Please
UpdateLoan` (present/infinitive) is a command. Conflating them is the most common
event-domain design error — it leaks *intent* into *recorded history*.

**The envelope fields you need on every event** (and the reasoning) are in
[`../avro-guide.md`](../avro-guide.md) §3. The key design question: is the event a
**fact** (what happened) or an **intent** (what to do)? Facts compose; intents
don't. Prefer facts.

---

## 6. Repository

**Definition:** an **abstraction over the persistence of an aggregate.** The client
codes against the Repository, not the ORM — so the aggregate can be persisted by
anything (Postgres, SQLite, in-memory) and tested without a database.

**The practical Django/DRF guidance (where most teams get this wrong):**

```
  ┌──────────────────────────────────────────────────────────────┐
  │  DON'T build a Hibernate-style repository layer on top of   │
  │  Django's ORM. The ORM already gives you:                    │
  │    • queries (QuerySet)                                     │
  │    • the Unit of Work (transaction.atomic)                  │
  │    • lazy loading, N+1 detection                             │
  │  A full Repository wrapper mostly just adds ceremony.        │
  │                                                              │
  │  DO keep query logic in a thin per-app "query service" or   │
  │  named QuerySet, so a service doesn't scatter ORM calls:    │
  │                                                              │
  │    class LoanQueryService:                                  │
  │        def __init__(self, db: QuerySet): ...                │
  │        def for_user(self, user_id): ...                     │
  │        def recent_balance_changes(self, loan_id): ...       │
  │                                                              │
  │  And inject that QueryService into your domain service:     │
  │    class LoanService:                                        │
  │        def __init__(self, loans: LoanQueryService): ...     │
  │                                                              │
  │  Now you can fake `LoanQueryService` in a test and exercise  │
  │  the domain rules with no database.                          │
  └────────────────────────────────────────────────────────────────┘
```

**Interview angle:** *"How do you test a domain rule without a DB?"* — Inject a fake
repository (a dict, a `list`-backed one), run the rule, assert. The Repository
abstraction is what makes that testable; Django's ORM makes the abstraction mostly
optional in production but still useful at the test boundary.

**When a full Repository is worth it:** when you genuinely have *multiple*
implementations (Postgres + read replica + cache), or you want the aggregate's
persistence to be swappable across the system. That's not this project's situation —
you have one Postgres and it stays one Postgres.

---

## 7. Unit of Work

**Definition:** coordinate **multiple object changes into one atomic commit.** The
"did all the writes succeed, or did any of them fail and we need to roll back all of
them?" question.

**In Django, this is `transaction.atomic()`.** You almost never need a hand-rolled UoW
class — Django's ORM manages the pending change set and `atomic()` commits or rolls
back atomically.

**The two places this project actually needs it:**

```
  1. Expense + outbox (in the API):
     with transaction.atomic():
         self.expense_repo.save(expense)     # the domain change
         self.outbox.enqueue(event)          # the event, SAME transaction
     → Both commit together or neither. No distributed transaction needed.
       This is the outbox pattern ([`reliability-patterns.md`](reliability-patterns.md)).

  2. Balance change + outstanding (in the consumer):
     with transaction.atomic():
         loan.apply_change(delta)            # the derived state
         self.balance_change_repo.save(...)  # the source of truth
     → Same. One transaction, one commit.
```

**The discipline:** you don't write `class UnitOfWork` — you write *the rule that
these N things are one atomic unit*, and use `atomic()`.

---

## 8. Specification

**Definition:** a **reusable, composable predicate** that expresses a query condition as
an object. `Specification.is_satisfied_by(object) -> bool`.

**In this project:** rarely needed. You use QuerySets for most queries, and the
Specification pattern is most useful when you have **many reusable, composable
domain-rule filters** and you find yourself writing the same `WHERE` clauses over and
over. The `Money.amount > 0` rule is really a Specification if you use it in more
than two places.

**When to adopt it:** when you start seeing 3+ places that say
`if expense.amount.cents > 0 and expense.currency == user.currency:` — extract that
into a `ValidExpense` spec, and the code that *builds* the rule becomes the code that
*checks* it.

**The L5/L6 discriminator:** knowing to say "a Specification is mostly useful when
you have a lot of *reusable, composable domain-rule predicates*, not just
DB-query-filters. Here, I don't have that volume, so I use QuerySets and keep the
invariant rules on the VO." is a more useful answer than "yes I use Specifications."

---

## How the patterns fit together — the one-diagram summary

```
   ┌──────────────────────────────────────────────────────────────┐
   │  BOUNDED CONTEXT: expenses                                   │
   │                                                               │
   │  ┌─────────────┐        ┌─────────────────────────────────┐ │
   │  │  Expense     │  ──id─►  Loan  (AGGREGATE, root)       │ │
   │  │  (Entity)   │       │  ─────────────────────────────── │ │
   │  └─────────────┘        │  Loan (root)                     │ │
   │                         │    ├─ outstanding: Money (VO)    │ │
   │                         │    ├─ credit_limit: Money (VO)   │ │
   │                         │    └─ [balance_changes: VO]      │ │
   │                         │  INVARIANT: sum(changes)==outstanding│
   │                         └─────────────────────────────────┘ │
   │                                                               │
   │  Domain services: ExpenseService, LoanService                │
   │  Events: ExpenseRecorded (published via outbox)              │
   │  Repository: thin QueryService per app                       │
   └─────────────────────────────────────────────────────────────────────────┘
```

**The reading:** the aggregate is the unit of consistency AND of Kafka keying.
The VO is the unit of invariant enforcement. The domain service orchestrates.
The event crosses the boundary. The repository is the (thin) persistence seam.

---

## When to skip DDD tactics here

- **Don't** split into microservices because you have "bounded contexts" — this is a
  single-user personal tracker; soft DDD (apps in one Django project) is the right
  level.
- **Don't** introduce Specifications, full Repository layers, or the Command pattern
  until you have the *repetition* that justifies them. The rule of three applies.
- **Do** keep the VO (Money) and the aggregate boundary (Loan) — those are the two
  DDD moves that pay for themselves in this project specifically, and they're the ones
  an interviewer will probe.

---

## Interview angle (the one to memorize)

*"How would you design a domain where loan balances are updated by events from a
Kafka stream?"*

```
  1. Loan is the aggregate; loan_id is the Kafka key — ordering per-aggregate.
  2. outstanding is a PROJECTION of balance_changes, not the source of truth.
  3. The consumer is idempotent (event_id unique constraint) → replay is safe.
  4. A reconciliation job checks sum(changes)==outstanding; drift triggers a replay.
  5. The API returns the expense immediately; the balance updates asynchronously —
     that's documented as eventual consistency.
```

That answer is the L5/L6 system-design interview in miniature, and it's the same
answer you'd give at a company.
