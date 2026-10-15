# Domain Decomposition Guide

> **The goal of this guide:** teach you to take a fuzzy idea ("expense tracker with
> loans and Kafka") and break it into **entities, relationships, and classes** you
> can defend out loud. This is the single most transferable skill in the project.
>
> No code here. Just the method. You apply it in Phase 4–5 and revisit it whenever
> the domain grows.

---

## 1. Why decomposition first

Most backend pain comes from getting boundaries wrong early and paying for it later.
A well-decomposed domain gives you:

- **Clear ownership** — every piece of data has one home.
- **Predictable change** — a new requirement touches one area, not five.
- **Testable rules** — business logic sits in classes you can test without HTTP or Kafka.
- **A schema that makes sense** — tables fall out of entities; you stop guessing.

The trap is jumping to tables or endpoints. Resist it. Entities first, then schema,
then API, then events. Each layer is a consequence of the one above.

---

## 2. The method: five passes

Work through the domain in five passes. Do them in order. Don't skip to classes.

### Pass 1 — Nouns (find the entities)

Read the problem statement and underline every **noun**. From this project:

> "add expenses on a daily basis, each expense has a **category** and a **source**…
> when added it runs a background **consumer** to update the active **loans** if the
> expense is through a **card**… updating that in the **db**… historical **events**…"

Nouns: expense, category, source, loan, card, consumer, event, user, balance.

Now separate three kinds of nouns:

| Kind | What it is | Examples here |
|------|-----------|---------------|
| **Entity** | Has identity, lives over time | Expense, Loan, Category, Source, User |
| **Value** | Describes, no identity of its own | Money amount, Date, Currency, Category *name* |
| **Event** | Something that happened | ExpenseRecorded, LoanBalanceUpdated |
| **Process/actor** | A behavior, not data | Consumer, Archiver, Scheduler |

**Rule:** entities get their own class/table. Values become fields or small value
objects. Events become messages. Processes become services/workers — never tables
that pretend to be nouns.

### Pass 2 — Relationships (find how they connect)

For each pair of entities, ask: how do they relate? Use cardinality as the lens.

- A **User** *has many* **Expenses**. An **Expense** *belongs to* one User.
- An **Expense** *has* one **Category**; a **Category** *has many* Expenses.
- An **Expense** *has* one **Source** (where the money came from — bank, cash, card).
- A **User** *has many* **Loans/credit accounts**; a **Loan** *belongs to* one User.
- An **Expense** *may reference* one **Loan** (when paid by credit).
- A **Loan** *has many* **BalanceChange events**.

**The critical distinction:** "has-a" vs "is-a". A credit card *is a* kind of source,
but a card is also *linked to* a loan/credit account. Decide deliberately whether
Card is a subtype of Source or a separate entity linked to a Loan. Write down the
reason. This is the kind of decision decomposition is *for*.

### Pass 3 — Invariants (find the rules that must always hold)

Invariants are truths your system must never violate. They are the heart of the
domain and they dictate where logic lives.

Candidate invariants for this project:

- An expense amount must be **positive** and have a **currency**.
- A loan's **outstanding balance** must never go negative.
- Sum of a loan's balance changes must equal its current balance.
- An expense marked as credit-paid must reference an existing loan.
- Every expense belongs to exactly one user; users can't see others' expenses.
- A balance change is **immutable** once recorded — corrections are new changes, not edits.

**Rule:** every invariant becomes either a database constraint, a validation rule, or
a method on a domain class — and you should be able to point at exactly one place
that enforces each. If you can't, the boundary is wrong.

### Pass 4 — Behaviors (find what the system *does*)

Entities don't just hold data; they have behavior. List the actions, then decide
which class owns each:

| Behavior | Candidate owner |
|----------|----------------|
| Record an expense | Expense domain (service), not the view |
| Apply an expense to a loan balance | Loan (it owns the invariant) |
| Recompute a balance from events | Loan / projection service |
| Categorize/spend summaries | Reporting service over Expenses |
| Archive old events | Archiver (a process, not an entity) |
| Consume Kafka message | Consumer (a process) |

**Rule:** behavior lives with the entity that owns the data it touches. The HTTP view
is a thin adapter — it validates input, calls a service, serializes output. It does
not contain business rules.

### Pass 5 — Boundaries (group into modules)

Now cluster entities that change together into modules (later: Django apps, later
still: possibly services). Two heuristics:

- **Cohesion:** do these entities always change for the same reason?
- **Coupling:** can one module be understood without reading the other?

Likely clustering here:

- **Identity**: User, auth tokens
- **Categorization**: Category (maybe Source too)
- **Expenses**: Expense, ExpenseEntry rules
- **Credit/Loans**: Loan, BalanceChange, the credit-paid logic
- **Events/Streaming**: event schemas, producer/consumer contracts (not entities, but a boundary)
- **Reporting**: read-only aggregations

Don't over-split. Three or four modules is plenty for v1. Split when the coupling
signal fires, not before (see [`project-structure-guide.md`](project-structure-guide.md)).

---

## 3. From entities to classes

Now — and only now — think about classes. Two kinds matter:

### Entities (have identity)

```
class Expense:
    id
    user_id
    amount: Money
    category_id
    source_id
    loan_id | None        # set when paid by credit
    occurred_at
    created_at
```

### Value objects (no identity, defined by their values)

```
Money = (amount: Decimal, currency: str)   # not two loose fields
DateRange = (start, end)
```

**Why value objects matter:** money as `(Decimal, currency)` lets you enforce "no
negative amounts" and "currencies must match" in one place. Two loose columns
(`amount`, `currency`) scatter that logic everywhere. This is the cheapest,
highest-leverage class design move in the whole project.

### Services (behaviors that span entities)

A service coordinates but doesn't own data:

```
ExpenseService.record(user, dto) -> Expense
    - validates the DTO
    - builds Money value object
    - persists Expense
    - if credit-paid: publishes ExpenseRecorded event
LoanService.apply_expense(expense) -> BalanceChange
    - loads the loan
    - creates a BalanceChange (loan owns this rule)
    - updates outstanding balance
    - persists both in one transaction
```

**Rule:** the service orchestrates; the entity enforces its own invariants. If you
find a service reaching into an entity's fields to enforce a rule, move that rule
onto the entity.

---

## 4. The event boundary

This is where decomposition pays off most. The expense flow is async, so you need a
clean seam between "record the expense" (synchronous, transactional) and "update the
loan" (asynchronous, via Kafka).

The seam is an **event**, not a shared database write across services:

- The API records the expense and emits `ExpenseRecorded` — **in the same
  transaction boundary** as the expense insert, so you never have an expense without
  its event, or an event without its expense. (This is the transactional-outbox
  pattern — see [`event-flows.md`](event-flows.md).)
- The consumer reads `ExpenseRecorded` and calls `LoanService.apply_expense`.

**Decomposition rule:** the API does not know how loans are updated. The consumer
does not know how expenses are validated. They meet only at the event contract
([`avro-guide.md`](avro-guide.md)). This is what makes each side independently
testable and deployable.

---

## 5. A decomposition exercise for you

Before Phase 4, do this on paper (or in [`design.md`](design.md)):

1. **List every noun** in your own words for the problem. Mark each entity / value /
   event / process.
2. **Draw the relationships** — even as boxes and arrows. Label each with cardinality.
3. **Write 5–8 invariants** in plain sentences ("a loan balance never goes negative").
4. **For each invariant, name the single place** that enforces it: a constraint, a
   validation, or a method. If you can't, your boundaries are wrong — fix them now.
5. **List the behaviors** and assign an owner class to each.
6. **Decide the Card question**: is Card a Source subtype, or a separate entity linked
   to a Loan? Write one paragraph defending your choice.
7. **Decide the module split**: name your 3–4 modules and one sentence each on what
   they own.

Bring your answers to the Phase 4 checkpoint ([`checkpoints.md`](checkpoints.md)).
The point isn't a perfect model — it's that you can *defend* the model.

---

## 6. Common decomposition mistakes

- **Anemic entities:** classes that are just data bags with all logic in services.
  If an entity has a rule ("balance can't go negative"), that rule belongs on the
  entity, not only in a service.
- **God service:** one `ExpenseService` that does validation, persistence, Kafka,
  email, and reporting. Split by responsibility.
- **Leaky boundaries:** the expenses module importing loan internals. Depend on
  public interfaces only.
- **Modeling processes as entities:** a `KafkaConsumer` table, a `Scheduler` table.
  Processes aren't data.
- **Premature splitting:** six microservices for a personal tracker. Decompose into
  *modules* first; split into *services* only when deployment or scaling demands it.
- **Skipping invariants:** the fastest route to a buggy schema. Write them down.

---

## 7. How this connects forward

- Your entities → **tables** in [`data-model.md`](data-model.md) and
  [`postgres-guide.md`](postgres-guide.md).
- Your behaviors → **endpoints** in [`api-contracts-guide.md`](api-contracts-guide.md).
- Your event boundary → **topics and schemas** in [`kafka-guide.md`](kafka-guide.md)
  and [`avro-guide.md`](avro-guide.md).
- Your module split → **the repo layout** in
  [`project-structure-guide.md`](project-structure-guide.md).

Get this layer right and the rest is mechanical. Get it wrong and every later layer
inherits the mistake.
