# Layered (n-tier) Architecture — in Depth

> The baseline shape almost every backend uses, explained precisely: what each layer is
> allowed to know, where the dependency direction must point, and the exact leaks that
> turn a clean layering into a decorative one.

---

## 1. The layers, with their contracts

```
   ┌───────────────────────────────────────────────────────────────┐
   │  PRESENTATION (DRF)                                          │
   │   views, serializers, URL routing, auth, error shaping       │
   │   KNOWS: HTTP, the API contract, the domain's public API     │
   │   DOES NOT KNOW: how data is stored, how events are published│
   ├───────────────────────────────────────────────────────────────┤
   │  APPLICATION (services)                                      │
   │   use cases: "record an expense", "update a loan balance"    │
   │   KNOWS: the domain's public API, orchestration, the ports   │
   │   DOES NOT KNOW: HTTP, Postgres specifics, Kafka specifics   │
   ├───────────────────────────────────────────────────────────────┤
   │  DOMAIN                                                    │
   │   entities, value objects, invariants, domain services       │
   │   KNOWS: ONLY the domain rules. No framework imports.        │
   │   DOES NOT KNOW: HTTP, ORM, broker, anything external        │
   ├───────────────────────────────────────────────────────────────┤
   │  INFRASTRUCTURE                                              │
   │   ORM/repositories, Kafka producer/consumer, config, logging │
   │   KNOWS: the ports the domain/application defined            │
   │   Satisfies them with Postgres, Kafka, env vars              │
   └───────────────────────────────────────────────────────────────┘
```

**The single most important line in this whole doc:** dependencies point
*inward*. Infrastructure implements ports the domain defined. The domain never
implements a port.

```
   domain  ──(defines port: `Publisher`)──►  infrastructure  (implements `Publisher`)
   domain  ◄──never────────────────────────────  infrastructure
```

If a domain file ever `import` from the ORM or a broker client, the arrow reversed
and the layering is broken.

---

## 2. Why "the domain knows nothing about frameworks" is the whole point

The layering earns its keep only when the **domain layer is framework-free**.
Consequences, all testable:

- **Unit-test a balance rule with no Postgres, no Kafka, no Django.**
  ```python
  def test_balance_never_negative():
      loan = Loan(credit_limit=Money(1000, "USD"))
      for delta in [400, 600]:      # pushes past the limit
          with pytest.raises(OverLimit):
              loan.apply_change(MoneyDelta(delta, "USD"))
  # no database, no framework, no HTTP — just the rule
  ```
- **Swap the broker without touching the domain.** The outbox port can be satisfied
  by Kafka *or* an in-memory queue in tests, and the domain doesn't care.
- **The framework can't leak business rules.** A serializer can't accidentally let
  a negative amount through, because "amount must be positive" lives on the `Money`
  value object, not the serializer.

That last point is the one that separates "I organized files into folders" from "the
layering actually buys me testability and correctness."

---

## 3. Where layers leak — the exact failure modes

```
   LEAK 1 — presentation reaches the domain's internals:
     view does  loan.outstanding += amount
     FIX:       view calls  service.apply_expense(...)  → the rule is on Loan

   LEAK 2 — application reaches infrastructure directly:
     service does  cursor = db.execute("UPDATE loans ...")
     FIX:           service calls a port (repository/service abstraction)

   LEAK 3 — domain imports a framework:
     loan.py does  from myapp.models import Expense   (cross-app ORM import)
     FIX:          use a reference key (expense_id), not the ORM object

   LEAK 4 — infrastructure defines the port, not the domain:
     the Kafka port is *defined* in infra and imported upward
     FIX:           the port is defined where the *user* of the port lives
                    (the domain/application), and implemented downward
```

**The rule that catches all four:** a layer may only depend on layers *below* it in
the dependency graph, and "below" means "more abstract." The domain is the most
abstract; infrastructure is the least.

---

## 4. The Django/DRF reality (be honest about it)

Django's ORM is a **leaky abstraction** in one specific way: a model *is* the domain
object and *is* the persistence object (Active Record). You get the domain layer and
the infrastructure layer fused into one class.

**The pragmatic stance for this project:**
- Accept the fusion for simple entities (`Category`, `Source` — dumb records).
- **Resist it where rules live.** For `Loan`, the invariant "sum of changes =
  outstanding" is a *domain rule*; keep the rule on a plain Python object or a
  tightly-scoped service, and let the Django model be the thin persistence shell.
- Use `transaction.atomic()` as the Unit of Work so the multi-write operations
  (expense + outbox, change + outstanding) stay atomic.

**The L5/L6 framing:** "I use Django's ORM for the record-keeping entities, but I
keep the *rules* on value objects and aggregate methods so they're testable without a
database. The ORM is my Active Record; the domain layer is the part I keep clean."

---

## 5. Layers vs the alternatives (the interview comparison)

| Architecture | Key idea | When it beats layered |
|--------------|----------|----------------------|
| **Layered** | clear dependency direction, per concern | your default; easiest to understand |
| **Clean/Hexagonal** | domain at the center, adapters at the edge | you need *swappable* adapters (multiple brokers) |
| **CQRS + Event Sourcing** | separate write/read models; events are truth | high read/write asymmetry, auditability |
| **Microservices** | each bounded context is its own deployable | independent scaling/teams; *not* for a personal tracker |

Layered is the right *start* for this project. You graduate to event-driven for the
async path, and you *do not* graduate to microservices — that's a scale/teams problem,
not a correctness one.

---

## 6. The one-paragraph "what is a layer" answer

> "Layers enforce **who can depend on whom**: presentation → application → domain →
> infrastructure, with arrows pointing down. The domain is the most abstract and knows
> nothing about HTTP, ORM, or broker; infrastructure implements the ports the domain
> declares. The payoff: I can unit-test a business rule with no framework, swap a
> broker without touching the domain, and no serializer can bypass a domain invariant.
> The failure mode is leaking — a view reaching into the domain, or a domain importing
> the ORM. The fix is always 'push the rule down one layer and code against the
> port.'"

---

## 7. How this shows up here

- **Presentation:** DRF views + serializers (thin; no business rules).
- **Application:** `ExpenseService`, `LoanService` (orchestrate + the outbox write).
- **Domain:** `Money`, `Loan` (the invariants; framework-free).
- **Infrastructure:** the outbox relay, the Kafka consumer, `pgbouncer` config,
  settings.
- **The two load-bearing boundaries:** view→service (no rules in views) and
  domain→infra (domain imports nothing external).
