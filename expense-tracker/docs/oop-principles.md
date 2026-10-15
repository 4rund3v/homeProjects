# OOP Principles

> The object-oriented principles that matter, each mapped to a **concrete decision in
> this project** — plus the over-engineering trap each one sets. No code; the concepts
> and where they bite. Related: [`design-patterns.md`](design-patterns.md) (patterns
> that follow from these), [`architecture-patterns.md`](architecture-patterns.md)
> (system-level shapes).

---

## How to read this

Principles are **heuristics, not laws**. Each one exists to prevent a specific kind of
pain. Applied blindly, each becomes its own pain — a codebase contorted to satisfy an
acronym. So for every principle below you get: what it prevents, how it shows up here,
and **when ignoring it is the right call**.

The discipline you're building: name the principle, then ask *"what breaks if I
violate it, and is that break worth avoiding?"* That question is the whole skill.

---

## SOLID

### S — Single Responsibility Principle
**Prevents:** a class that changes for many reasons (and so breaks for many reasons).
**Rule of thumb:** a class should have **one reason to change** — equivalently, one
"actor" whose needs it serves.

**Here:**
- A DRF **serializer** validates and shapes the API contract. It should not also
  compute loan balances or publish to Kafka — those are different reasons to change.
- An **Expense** entity owns expense invariants (amount > 0, currency). It should not
  know how Kafka serializes it.
- The **outbox relay** publishes events; it should not validate expenses.

**Trap:** over-splitting into `ExpenseReader`, `ExpenseWriter`, `ExpenseValidator`,
`ExpenseFormatter` until "single responsibility" means "single method." SRP is about
*reasons to change*, not line counts. If two things always change together, they're one
responsibility.

### O — Open/Closed Principle
**Prevents:** editing working, tested code every time a requirement arrives.
**Rule:** open for **extension**, closed for **modification**.

**Here:**
- Adding a new **payment kind** (cash → card → UPI → …) should extend a set of kinds,
  not rewrite the expense logic with new `if` branches.
- Adding a new **event consumer** (e.g. a future "budget alert" consumer) should mean
  adding a consumer, not editing the loan-updater.
- A new **auth provider** should plug into the login flow, not fork it.

**Trap:** building an abstraction for extension you'll never use. You don't need a
plugin architecture for payment kinds that are fixed at three. **Extend on the second
or third case, not the first** (ties to YAGNI below).

### L — Liskov Substitution Principle
**Prevents:** a subclass that breaks the parent's contract, so code using the parent
silently misbehaves.

**Rule:** a subtype must be usable anywhere its base type is, without the caller
knowing or caring.

**Here:**
- If you model `CardPaymentSource` as a subtype of `Source`, any code handling a
  `Source` must work correctly with a `CardPaymentSource` — no special-casing
  "actually if it's a card, do this other thing." If you *do* need to special-case it,
  it's not a valid subtype — it's a different type (this is exactly the Card decision
  in [`domain-decomposition.md`](domain-decomposition.md) §5).
- Any `AuthenticationClass` in DRF must produce a valid `request.user` or `None`; you
  can't have one that throws when anonymous.

**Trap:** inheritance hierarchies grown "for reuse" that violate LSP constantly. This
is the strongest argument for **composition over inheritance** (below).

### I — Interface Segregation Principle
**Prevents:** a fat interface that forces implementers to stub out methods they don't
need.

**Rule:** many small, specific interfaces beat one general-purpose one.

**Here:**
- Don't build one `EventPublisher` interface with `publish`, `subscribe`, `replay`,
  `manage_schema`, `admin_cluster`. Split into what each consumer actually needs: a
  producer needs `publish`; a consumer needs `subscribe`/`commit`.
- A reporting interface shouldn't force every entity to implement `to_report_row()`.

**Trap:** ISP is often irrelevant in Python (no compile-time interface enforcement,
duck typing). Don't manufacture abstract base classes to satisfy ISP where a plain
function or protocol is honest. Reach for it when a *shared contract* genuinely spans
multiple implementers.

### D — Dependency Inversion Principle
**Prevents:** high-level business logic depending on low-level details (a specific DB,
a specific broker, a specific HTTP client).

**Rule:** depend on **abstractions**, not concretions; the concrete wiring is injected
from the edge.

**Here:** this is the most valuable SOLID principle for your project, because it's what
makes the domain testable without Postgres or Kafka.
- Your **domain service** (`LoanService.apply_expense`) should depend on a repository
  abstraction, not import SQLAlchemy directly — so you can test the balance rule
  without a database.
- The **outbox relay** depends on a "publisher" abstraction, so you can test it with a
  fake publisher and only use the real Kafka one in production.
- The **consumer** depends on a deserializer abstraction, so schema-registry issues
  don't entangle the balance logic.

**Trap:** an interface + two implementations where there will only ever be one. DIP
earns its keep when you have (or will have) multiple implementations, or when the
dependency is genuinely awkward in tests. A single Postgres repository doesn't need an
interface on day one — add it when the second implementation or the test pain appears.

---

## The other principles that matter more day-to-day

### DRY — Don't Repeat Yourself
**Prevents:** the same rule in five places, changed in four.
**Rule:** every piece of *knowledge* has one authoritative representation.

**Here:** the "money must be positive and have a currency" rule lives in the `Money`
value object — once — not re-checked in the serializer, the model, and the service. The
idempotency key semantics live in one place.

**The critical nuance people miss:** DRY is about **knowledge**, not text. Two pieces of
code that *look* identical but encode different rules should **not** be merged — merging
them couples two things that change independently. Duplicated *code* is fine;
duplicated *knowledge* is the bug.

### KISS — Keep It Simple, Stupid
**Prevents:** cleverness that future-you can't debug.
**Here:** a plain function beats a metaclass; an explicit `if` beats a clever
comprehension nobody can read; the simplest thing that passes the test wins. This
project is a learning vehicle — optimize for *legibility*, not elegance.

### YAGNI — You Aren't Gonna Need It
**Prevents:** building for hypothetical futures that never arrive (and change when they
do).
**Here:** you don't need a plugin system for three payment kinds, a sharding strategy
for one user, or a CQRS read model before you've measured a slow read. Build for the
requirement in front of you; refactor when the second case arrives.

**The tension with OCP:** OCP says "be open to extension"; YAGNI says "don't build the
extension yet." Resolve it like this: **make the code easy to refactor, don't
pre-build the abstraction.** Clean, well-bounded code can be extended later; a
speculative abstraction built for the wrong future cannot.

### Composition over Inheritance
**Prevents:** deep hierarchies, fragile base classes, LSP violations.
**Rule:** "has-a" beats "is-a"; assemble behavior from small objects rather than
inheriting it.

**Here:** rather than `CreditCardExpense(CashExpense)` with overridden behavior, model
an `Expense` that *has* a payment kind and optionally *has* a linked loan. Behavior
comes from composing the right pieces, not from a subtype tree. This is the practical
antidote to the LSP trap above.

**Trap:** composition taken to absurdity — a "has-a everything" object assembled from
forty injected strategies is worse than inheritance. Composition where it clarifies;
inheritance where there's a genuine, contract-preserving "is-a."

### Law of Demeter ("don't talk to strangers")
**Prevents:** `a.getB().getC().doThing()` — code coupled to the internal structure of
its collaborators, so a refactor deep in one object ripples everywhere.
**Rule:** talk to your immediate collaborators; don't reach through them.

**Here:** the view shouldn't do `expense.source.loan.outstanding -= amount`. It calls
`LoanService.apply_expense(expense)`, and the service coordinates. The view knows its
collaborators; it doesn't navigate the whole object graph.

**Trap:** dogmatic Demeter produces wrapper-method explosions. Use it to spot
inappropriate intimacy, not to ban every chained call.

### Encapsulation (information hiding)
**Prevents:** every part of the code reaching into every other part's fields.
**Rule:** an object exposes behavior and guards its own invariants; its internal state
is private.

**Here:** a `Loan` shouldn't expose a public `outstanding` field that any code can
`+=` to. It exposes `apply_change(amount)`, which enforces "never negative" and keeps
the invariant intact. This is the fix for the **anemic domain model** trap (below).

### Tell, Don't Ask
**Prevents:** code that interrogates an object's state and then decides for it — the
object's logic leaking into its callers.
**Rule:** tell the object what to do; don't ask its state and manipulate it yourself.

**Here:** don't `if loan.outstanding > loan.credit_limit: ...` in the service. Tell the
loan `loan.charge(amount)` and let it enforce its own rules.

---

## The two OOP failure modes to actively avoid

**The Anemic Domain Model** — entities that are pure data bags (getters/setters) with
*all* logic in service classes. It looks OOP but is procedural code with extra steps;
every rule about a Loan lives in `LoanService`, so the Loan can't protect itself and
any code touching a Loan can violate it. **Fix:** put the invariant-enforcing behavior
on the entity ([`domain-decomposition.md`](domain-decomposition.md) §3).

**The God Object / God Service** — one class that does everything (validation,
persistence, Kafka, email, reporting). It violates SRP and becomes the file everyone
edits and nobody understands. **Fix:** split by responsibility; if you can't describe
a class's job in one sentence, it's a God object.

---

## Mapped to this project (what to actually apply, and when)

| Principle | Apply it here | Phase |
|-----------|---------------|-------|
| SRP | thin views, one job per class | 1, 4 |
| OCP | payment kinds, event consumers, auth providers | 4–7 (extend on 2nd case) |
| LSP | the Card-as-Source-subtype decision | 4 |
| ISP | split publisher/consumer interfaces | 6 |
| DIP | repository + publisher abstractions; testable domain | 2, 6 |
| DRY (knowledge, not text) | `Money` value object | 4 |
| KISS | default to the readable option | always |
| YAGNI | no speculative abstraction | always |
| Composition > inheritance | Expense has-a kind/loan, not a subtype tree | 4 |
| Law of Demeter | view calls service, doesn't navigate the graph | 5 |
| Encapsulation | Loan guards its own invariant | 5 |
| Tell, Don't Ask | `loan.charge(x)`, not `loan.outstanding += x` | 5 |

---

## Checkpoint questions

- Name a class and its **one reason to change**.
- Which abstraction in your code exists for **extension**, and which is **speculative**
  (YAGNI violation)?
- Is `Card` a valid subtype of `Source` under LSP? Defend it.
- What depends on an abstraction so it's testable without Postgres/Kafka? (DIP)
- Is any rule duplicated as *knowledge* (not just text)? Where's the one home?
- Show one place you chose composition over inheritance, and why.
- Can an entity's invariant be violated from outside the entity? (Encapsulation)

These map to the Phase 4–5 gates in [`checkpoints.md`](checkpoints.md).

---

## Decisions to record in `design.md`

- The Card decision (subtype vs linked entity) and the LSP reasoning.
- Which abstractions you introduced for DIP, and the test they enable.
- Where you deliberately chose **not** to abstract (YAGNI), and why.
- Any inheritance you kept, and the LSP contract it preserves.
