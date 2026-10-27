# DDD Strategic — Bounded Contexts & Context Mapping

> The *strategic* side of DDD: what the boundaries are, how they relate, and how the
> language works. The *tactical* patterns (entities, aggregates, VOs) live in
> [`../design-patterns/ddd-tactical.md`](../design-patterns/ddd-tactical.md).
> The L5/L6 move here is knowing which of the formal DDD machinery is worth using on
> a project of this size — and saying so.

---

## 1. Bounded Context — the unit that matters most

A **Bounded Context** is the area of *consistency*: a subdomain where a term like
"source" or "loan" has *one* unambiguous meaning. The rule:

> **Inside a bounded context, "a loan" means one thing.** Cross the boundary and the
> same word can mean something different.

For this project, the natural contexts (which map to Django apps):

```
   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
   │  EXPENSES        │   │  LOANS / CREDIT  │   │  CATEGORIES      │
   │  ─────────────   │   │  ──────────────   │   │  ──────────────   │
   │  Expense         │   │  Loan (aggregate) │   │  Category        │
   │  "source" = where│   │  "balance" = the  │   │  "category" = the│
   │   money came     │   │   outstanding on │   │   grouping label │
   │  "outstanding" N/A│   │   a loan         │   │                  │
   └──────────────────┘   └──────────────────┘   └──────────────────┘
          same word, different meaning across contexts:
          "source" in EXPENSES = the funding account; "source" in an
          analytics context could mean "the Kafka topic"
```

**The payoff:** when two pieces of code say "loan balance" they *can't* be talking
about the same thing, because they're in different contexts with different definitions.
The boundary is the defense against the most common domain bug: *words drifting apart
from their meaning.*

---

## 2. Context Mapping — how the contexts relate

The relationships between contexts, and what each costs:

```
   ┌──────────────┬────────────────────────────────────────────────────────┐
   │ RELATIONSHIP │ MEANING  ·  USE WHEN                                   │
   ├──────────────┼────────────────────────────────────────────────────────┤
   │ Shared Kernel│ EXPENSES + LOANS share the "Money" + "Loan" concepts.  │
   │              │ One team owns the shared model; both agree.           │
   │              │ ✓ THIS PROJECT — a shared kernel, not two services.    │
   ├──────────────┼────────────────────────────────────────────────────────┤
   │ Conformist   │ CATEGORIES simply accepts EXPENSES's definition of      │
   │              │ "category." No translation needed.                    │
   ├──────────────┼──────────────────────────────────────────────────────────┤
   │ Customer /   │ LOANS (upstream) defines the rules; EXPENSES           │
   │ Supplier     │ (downstream) consumes "a loan balance can be         │
   │              │ updated." Upstream has priority.                     │
   ├──────────────┼────────────────────────────────────────────────────────┤
   │ Open Host    │ a future analytics context can subscribe to EXPENSES's │
   │ Service      │ events without EXPENSES knowing. (event-driven)       │
   ├──────────────┼────────────────────────────────────────────────────────┤
   │ Anti-Corr.   │ if you ever import a foreign system's messy "loan"    │
   │ Layer        │ concept, isolate it behind a translator. Rare here.   │
   └──────────────┴────────────────────────────────────────────────────────┘
```

**The L5/L6 framing:** "At this scale I use a **shared kernel** — one codebase, a few
Jinja… one codebase, a few Django apps, agreeing on the shared domain model. I'd
revisit anti-corruption layers or Open Host only if I integrated a foreign system or
exposed events to downstream consumers I don't control."

---

## 3. Ubiquitous Language — the discipline, not the glossary

The point isn't to *have* a glossary; it's that the **code names come from the
language, and the language comes from the domain experts.**

```
   "Outstanding balance"  →  loans.outstanding          (not `balance`, not `amt`)
   "A charge to a card"  →  a balance_change, not `txn`
   "The event that an    →  ExpenseRecorded (past tense, it's a fact)
    expense was recorded"

   The code reads the domain. A junior who only knows SQL can look at
   `loan.apply_expense(...)` and understand *the business rule*, not just a query.
```

**The test:** if you have to translate a code name back into business language to
understand it, the language isn't ubiquitous yet. The names *are* the knowledge.

**Practical:** keep a short glossary (this project has one in
[`glossary.md`](../glossary.md)). The discipline is that the glossary and the code
*move together* — a new term gets a name, the name goes in the code, the code goes in
the glossary.

---

## 4. What NOT to do with DDD at this scale

The expensive DDD moves, and why to hold off:

| Formal move | What it is | Why not yet |
|-------------|-----------|-------------|
| **Context Mapping diagram** | a full map of every relationship | 3 contexts, drawn by hand is enough; the formal technique is overkill |
| **Anti-Corruption Layer** | a translator to a foreign model | no foreign system in this project |
| **Seamless Bounded Contexts** | merging two contexts into one shared model | do it *deliberately* once, not as drift |
| **Domain-centric deployment** | one deployable per context | that's microservices — not this scale |
| **Event Storming workshops** | the team mapping events on sticky notes | fine *once*, to find the events; not a recurring ritual here |

**The honest L5/L6 answer:** "I use DDD's *tactical* patterns (aggregates, value
objects, domain events) and a *light* strategic layer — bounded contexts that mirror
my Django apps and a shared kernel. I don't do formal context-mapping diagrams or
anti-corruption layers, because there's no foreign system and one team. The value of
DDD here is the *discipline* — naming things after the domain and keeping the
aggregate boundary honest — not the heavyweight organizational machinery."

---

## 5. The one diagram to keep (the shared kernel)

```
                       ┌────────────────────────────┐
                       │   SHARED KERNEL            │
                       │   Money · Loan · Expense   │
                       │   (the agreed-upon model)   │
                       └────────────────────────────┘
                         │          │           │
             ┌───────────┘          │           └───────────┐
             ▼                       ▼                     ▼
        ┌──────────┐          ┌───────────┐          ┌─────────────┐
        │ EXPENSES │  sup. →  │  LOANS    │  uses →  │ CATEGORIES  │
        │ context  │          │  context  │          │  context   │
        └──────────┘          └───────────┘          └─────────────┘

   sup. = supplier relationship (loans defines the balance rules;
   expenses consumes them). One codebase, agreed-upon shared model.
```

---

## 6. How this shows up here

- **Bounded contexts ≈ Django apps** — expenses, loans/credit, categories. Each has
  its own language; the shared kernel is `Money` + the `Loan` aggregate.
- **Supplier relationship:** LOANS defines "how a balance changes"; EXPENSES triggers
  those changes via events. Upstream (loans) wins argument
  [kafka-guide.md](../kafka-guide.md).
- **Ubiquitous language:** the terms in [`glossary.md`](../glossary.md) *are* the code
  names. `apply_change`, `outstanding`, `ExpenseRecorded` — all domain words.
- **What's deferred:** formal context maps, anti-corruption layers, and
  per-context deployment. Revisit only if a foreign system is integrated.
