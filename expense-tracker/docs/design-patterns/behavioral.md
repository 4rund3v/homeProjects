# Behavioral Patterns — and which ones Kafka or DRF already implement

> Behavioral patterns are about *how objects interact and control flow*. The key L5/L6
> move here is recognizing that the two most "behavioral" patterns in this system —
> Observer and Command — are *structurally* already implemented by Kafka. You're not
> adding them; you're recognizing them.

---

## 1. Strategy

**Problem:** several interchangeable algorithms for one job; choose at runtime.

**In this project (and in DRF):**
- **Auth:** `JWTAuth` vs `OAuth2Auth` vs `SessionAuth` — same call site, different
  strategy.
- **Throttling:** per-user vs per-IP vs per-endpoint rate limiters.
- **Payment kind:** `CardStrategy`, `BankStrategy` for how a `Money` flows into a
  `Loan` balance.

```
  class BalanceStrategy(Protocol):
      def apply(self, loan: Loan, money: Money) -> MoneyDelta: ...

  def compute_delta(kind: str, loan, money) -> MoneyDelta:
      return REGISTRY[kind].apply(loan, money)     # dict dispatch, no if/elif
```

**The point:** a `dict`-dispatch on a strategy beats a long `if kind == ...` chain the
moment you have 3+ cases. Two cases? An `if` is honest.

---

## 2. Observer / Publish–Subscribe

**Problem:** one thing happens; N unrelated things should react, and the source
shouldn't know who's listening.

**This is the heart of the whole system, and it's already Kafka:**

```
  producer (outbox) ──publish──► topic  ◄──subscribe── consumer 1 (loan updater)
                                             ◄──subscribe── consumer 2 (budget alerts)
                                             ◄──subscribe── consumer 3 (analytics)
```

- The API **doesn't know** a loan-updater exists. It just publishes `ExpenseRecorded`.
- Adding "budget alert" later means *adding a consumer*, not editing the API. That's
  Open/Closed in action.
- Kafka is a **distributed, durable** Observer. A plain in-process observer is a
  Python callback list; Kafka's is the durable, cross-process version.

**When you'd use the in-process version:** a UI event bus, or a domain that emits
events within one process. Once events cross a process boundary, you want Kafka (or a
message broker), not a local callback list.

---

## 3. Command

**Problem:** turn a request into a first-class object so it can be *queued, logged,
retried, or undone*.

**You're already doing it — you just call it "an event":**

```
  outbox row  ≈  a Command/Event serialized:  {event_id, payload, topic, key, sent_at}
  relay        ≈  the queue processor: pulls rows, executes them, marks sent
  consumer     ≈  idempotent executor of the command
```

**The insight:** the outbox row + the Avro event *are* the Command pattern, with Kafka
as the queue. Don't wrap it in a separate `Command` base class hierarchy — that's
ceremony on top of ceremony.

**Undo/saga angle:** a Command that can't be undone is where Sagas and compensating
transactions come in (see [`reliability-patterns.md`](reliability-patterns.md)).

---

## 4. Template Method

**Problem:** the algorithm's *skeleton* is fixed; a few steps vary.

**In DRF:** a `ViewSet` gives you the skeleton (`validate → perform_create →
serialize`); you override `perform_create` for the variation.

**In the consumer:**

```
  def consume(self, message):
      event   = self._deserialize(message)   # fixed
      if self._already_applied(event):        # fixed (idempotency gate)
          self._commit(); return
      self._apply(event)                     # ← THE varying step, per event type
      self._commit()
```

The skeleton (deserialize → idempotency-check → apply → commit) is fixed; `apply`
varies by event. That's a Template Method, and it's exactly right — the ordering and
the commit discipline are non-negotiable, only the per-event action changes.

---

## 5. Chain of Responsibility

**Problem:** a request can be handled by one of several handlers; pass it down the
line until one handles it.

**In this project:** the **auth + permission + throttle** pipeline in DRF is a chain —
`IsAuthenticated → IsOwner → UserRateThrottle`, each either handles the decision or
passes it along. You use it via the framework rather than hand-rolling the chain.

**When to hand-roll one:** a request-middleware system, or a "try these resolvers in
order" for a payment method. Rare here.

---

## 6. Mediator / Memento

**Mediator:** one object coordinates N objects that otherwise don't talk to each
other. Your **relay** is a mediator between the outbox and the broker; your **domain
services** mediate between repositories. You use the role, you don't need a formal
`Mediator` class.

**Memento:** save/restore an object's state. Useful in **reconciliation/replay** —
"snapshot the loan's derived state, then replay and compare" is a Memento-lite. Not
worth formalizing here.

---

## The behavioral decision table

| Pattern | You... |
|---------|--------|
| Strategy | use a dict-dispatch for payment kinds / auth; not 3+ if/elif |
| Observer/Pub-Sub | *have* it via Kafka — recognize it, don't add a second one |
| Command | *have* it via the outbox row — recognize it, don't wrap it |
| Template Method | the consumer's consume loop; DRF's viewset hooks |
| Chain of Responsibility | the DRF auth/permission/throttle pipeline |
| Mediator | the relay and services, informally |

**The L5/L6 framing:** "Most of my 'behavioral' patterns are the durable, cross-process
versions — Kafka *is* Observer, the outbox *is* Command. The remaining ones I get from
DRF (viewset hooks are Template Method, the permission stack is Chain of
Responsibility). My rule is: recognize what's already implemented, and only hand-roll
a pattern when the in-process version is what I actually need."
