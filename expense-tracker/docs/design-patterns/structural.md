# Structural Patterns — and where Django/DRF already does them

> Structural patterns are about *how objects compose* to build larger interfaces. In
> Django/DRF, most of these are built in — the L5/L6 skill is recognizing them so you
> don't reinvent the framework, and so you can name what's happening when you're
> debugging.

---

## 1. Adapter

**Problem:** two existing interfaces that don't match — A expects shape X, B provides
shape Y. The Adapter translates B's shape into A's.

**In this project:**
- A third-party OAuth provider returns a token blob; your `Identity` type wants
  `user_id + email`. A small adapter parses the provider response into `Identity`.
- The **schema-registry client** has an `encode(obj) -> bytes` API, but your relay
  wants a cleaner `publish(event)`. Wrap it in a `Publisher` adapter so the relay
  depends on *your* interface, not the library's.

**The DIP connection:** the Adapter is *how* Dependency Inversion is implemented — you
code against the abstraction (your `Publisher`), and the adapter connects the
concrete (the Kafka library) to it. See [`../oop-principles.md`](../oop-principles.md).

---

## 2. Decorator

**Problem:** add behavior to an object *at runtime, per instance*, without subclassing
or modifying the object.

**In Django/DRF — heavily used, mostly without you noticing:**

```
  @permission_classes([IsAuthenticated])
  @throttle_classes([UserRateThrottle])
  class ExpenseViewSet(...): ...

  → each @... wraps the viewset with a behavior. That's a decorator *pattern*,
    applied through class-based "mix-in" composition.

  Middleware is the same idea at the HTTP level:
    request ─► CORS ─► Auth ─► RateLimit ─► your view ─► response (back)
```

**When you'd hand-roll one:** wrapping a repository to add caching or tracing:

```python
class TracingRepo:
    def __init__(self, inner: LoanQueryService): self.inner = inner
    def for_user(self, user_id):
        t0 = now(); out = self.inner.for_user(user_id); log(...)
        return out
```

**The L5/L6 framing:** "DRF's permission/throttle classes and Django middleware are the
Decorator pattern; I use the framework's version rather than subclassing the view."

---

## 3. Facade

**Problem:** a subsystem has many moving parts; callers need one simple door.

**In this project:** a `LedgerFacade` / `ExpenseService.record(user, dto)` that hides
the expense insert + outbox write + validation + event building:

```
  caller:  service.record_expense(user, dto)          ← one call
           └► validate → build Money → persist → enqueue outbox
```

**The rule:** the facade *coordinates*; it does not *contain* the business rules
(those stay on the entities/services). A facade that has all the logic is a God object
in disguise — see [`creational.md`](creational.md) and the overview's "Facade" note.

---

## 4. Proxy

**Problem:** control access to an object — *after* work (caching), *before* work
(validation, auth), or *in place of* a remote object.

**In this project:**
- **Caching proxy** in front of a reporting query — answer from cache when fresh, else
  compute and store.
- **The API itself is a proxy to the domain** — it validates, authenticates, then
  hands the request to the service.
- In a scale-up future: a **replica-reading proxy** that routes reads to a standby.

**Note:** proxies are where you get value *at the boundary* (cache, latency, access
control), and where you must be careful not to leak the "real" object's identity to
callers.

---

## 5. Composite

**Problem:** treat a tree of objects (one item or many) the same way — "a category can
contain subcategories; a report can be one number or a hierarchy of numbers."

**In this project:** if you ever model **categories as a hierarchy** (Groceries →
Dairy → Milk), the Composite lets a query "spend in this category tree" work whether
the category is a leaf or a branch. You probably don't need it yet; it's the pattern to
reach for *if* you add category nesting.

---

## The structural decision table

| Pattern | Where it shows up here |
|---------|------------------------|
| Adapter | OAuth provider → Identity; schema registry → `Publisher` |
| Decorator | `@permission_classes`, `@throttle_classes`, middleware |
| Facade | `ExpenseService.record` — one door over insert+outbox+event |
| Proxy | caching in front of reports; replica-read proxy (future) |
| Composite | category hierarchy (only if you add nesting) |

**The L5/L6 framing:** "I mostly lean on the framework's structural patterns —
permissions and middleware are decorators; DRF's viewset hierarchy is a Composite-ish
structure. I hand-roll a Facade for the outbox write path and an Adapter to wrap the
Kafka/registry clients so my relay depends on my own interfaces."
