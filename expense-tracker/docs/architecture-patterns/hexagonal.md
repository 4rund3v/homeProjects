# Hexagonal (Ports & Adapters) — in Depth

> Layered with a stricter rule: **the domain defines the interfaces; everything else
> is an adapter.** This is the shape that makes the "the domain knows no framework"
> promise in [`layered.md`](layered.md) mechanical, not aspirational.

---

## 1. The core idea

```
              ┌───────────────────────────────────────────┐
              │            APPLICATION + DOMAIN            │
              │                                           │
              │   ┌─────────┐   ┌─────────┐   ┌────────┐  │
        IN  ──► │ [ PORT ] │   │  CORE  │   │ [ PORT ]│  │   ◄── OUT
   (driven)     └─────────┘   │ (pure)  │   └────────┘     (driving)
              │     ▲                  │        ▲          │
              │     │   adapters       │        │   adapters │
              │     │                  │        │          │
              │   ┌─┴───────────┐  ┌───┴─────┐  │          │
              │   │ HTTP/DRF    │  │  Kafka   │  │          │
              │   │ adapter     │  │ producer │  │          │
              │   └─────────────┘  └─────────┘  │          │
              │   ┌─────────────┐  ┌───────────┐  │          │
              │   │ Postgres    │  │ Schema    │  │          │
              │   │ adapter     │  │ registry  │  │          │
              │   └─────────────┘  └───────────┘  │          │
              └───────────────────────────────────────────┘

   "IN" adapters drive the app (a request comes in).
   "OUT" adapters the app drives (it publishes, it persists).
   The CORE never imports an adapter.
```

**The rule:** the dependency arrow always points *into* the core. Adapters call
inward; they are never called by the core. The core reaches for a port, and a
*port* is an abstract interface the core defines.

---

## 2. Ports vs adapters — the two that matter here

```
   PORT (defined by the core, in the application layer):
   ┌────────────────────────────────────┐
   │  class EventPublisher(Protocol):    │   ← the *abstraction* the core codes
   │      def publish(event) -> None    │      to. No Kafka import.
   │                                     │
   │  class BalanceRepo(Protocol):       │
   │      def save_change(delta) -> None │
   └────────────────────────────────────┘

   ADAPTERS (implement the port, live in the infrastructure layer):
   ┌──────────────────────────┐    ┌──────────────────────────┐
   │  KafkaPublisher          │    │  PostgresBalanceRepo     │
   │  (implements EventPub)   │    │  (implements BalanceRepo)│
   │  imports kafka           │    │  imports Django ORM      │
   └──────────────────────────┘    └──────────────────────────┘
```

**The whole point, in one sentence:** the core depends on `EventPublisher` (a
Python Protocol), not on `kafka` (a concrete library). Tests swap the adapter for a
fake; production wires in Kafka. The core doesn't know the difference.

---

## 3. Ports & adapters for this exact system

| Core defines | Adapter(s) that satisfy it |
|--------------|---------------------------|
| `ExpenseRepo` | Django ORM repository (in tests: in-memory dict-backed) |
| `EventPublisher` | Outbox writer (writes the outbox row); relay reads it into Kafka |
| `BalanceUpdateSink` | Kafka consumer → Postgres `balance_changes` + `outstanding` |
| `IdentityProvider` | JWT / social login (the auth adapter) |
| `Clock` | system time; fake in tests |

**The non-obvious one:** `EventPublisher` is *two* adapters — the API writes to the
**outbox** (transactional), the relay moves outbox rows to Kafka. The port hides that
split. The core just says "publish this event"; it doesn't know whether it's a row
insert or a broker produce.

---

## 4. When to actually build it vs skip it

```
   BUILD PORTS (worth it):
   • the dependency is AWKWARD in tests (Kafka, the schema registry,
     an HTTP auth provider) → fake it behind a port
   • you want to SWAP the implementation (Postgres now, a read replica later)
   • the core must stay framework-free for unit tests

   SKIP PORTS (YAGNI — just use the thing):
   • a plain Postgres read through Django's ORM — the ORM IS the abstraction
   • config/settings — just read them; a "ConfigPort" is ceremony
   • logging — import the logger; don't port it
```

**The L5/L6 discriminator:** "I port the *awkward-to-fake* dependencies — Kafka, the
registry, auth. I don't port Django's ORM or a logger, because the framework already
gives me the seam I need. A port earns its keep by enabling a test or a swap; if I
can't name the test or the swap, I'm adding ceremony."

---

## 5. The dependency-inversion payoff (concrete)

```
   Without ports:
     consumer.py  ──imports──►  kafka  ──►  hard to unit-test, hard to replay

   With a port:
     LoanService.update(balance_repo, publisher)
        where balance_repo: BalanceRepo (Protocol)
        in tests:  InMemoryBalanceRepo()   ← no DB, no Kafka
        in prod:   PostgresBalanceRepo()   ← real thing

   Now the *rule* "sum of changes = outstanding" is tested with zero infrastructure.
   The rule is in the core; the storage is an adapter.
```

---

## 6. How it shows up here

- The **outbox + relay** is the cleanest hexagonal example: the core says "publish
  event," the outbox is the in-transaction adapter, the relay is the delivery
  adapter. Three layers, one port.
- The **consumer's balance update** codes against a `BalanceRepo` port, not Django ORM
  directly.
- **Testing:** `InMemoryBalanceRepo` + `ListPublisher` replaces the DB and Kafka in
  every unit test. That's the payoff.
- **You skip** ports for settings, the ORM's simple reads, and logging — YAGNI.

---

## 7. The "where does the port live" rule (the subtle one)

The port is defined **where the port's user lives**, not where the implementation
lives:

```
   LoanService (application) uses BalanceRepo → BalanceRepo lives in application.
   PostgresBalanceRepo (infrastructure) implements it → adapter lives in infra.

   If BalanceRepo lived in infra, LoanService would import from infra → the arrow
   reversed → the hexagon is a lie.
```

This is the #1 reason hexagonal architectures rot: people put the interface next to
the implementation for convenience, and silently invert the dependency.
