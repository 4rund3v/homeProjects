# The Design Worksheet — "Design a System" in 30 Minutes

> The reusable structure for any "design X" interview, applied to this project as the
> worked example. The L5/L6 skill is *the process*, not the specific system — use this
> on a URL shortener or a notification service the same way.

---

## 0. The meta-rule: 80% of the answer is the *framing*

An interviewer grades: (1) do you clarify scope and constraints, (2) do you name the
*trade-offs* rather than just pick components, (3) can you state where the system sits
on each dial. Most candidates fail by jumping straight to "use Kafka + Postgres +
K8s." **Resist that.** Walk the worksheet in order.

---

## 1. Requirements (5 min) — separate functional from non-functional

```
   FUNCTIONAL (what it does):
     • record an expense: amount, currency, category, source, when
     • a credit-paid expense updates the related loan's outstanding balance
     • list/summarize expenses by category/source/period
     • see loan balances

   NON-FUNCTIONAL (the dials — THIS is where the points are):
     • Consistency: how fresh must the balance be? → eventual, bounded window
     • Availability: what's up when a dependency is down? → write path stays up
     • Latency: budget the API response vs balance freshness
     • Durability: how much can we lose? → RPO ≈ backup interval
     • Scale: one user → single node; state the ceiling
     • Security: who can see whose data? → per-user ownership (JWT)
```

**The move:** state the *requirement* as a number where you can ("balance staleness
< 5s," "API p99 < 200ms"). Numbers make the trade-offs concrete.

---

## 2. Back-of-envelope (2 min) — the numbers that drive the design

```
   user:        1 (personal tracker)  → single node is fine; state that
   expense rate: ~50/day → trivial write load
   outbox rows:  ~50/day → no back-pressure concern in practice
   balance lag:  outbox relay + consumer ≈ seconds → "eventual, < 5s"

   → The numbers say: the *correctness* problem (atomic expense+event, ordered
     balances, idempotency) matters far more than the *scale* problem.
     Design for correctness; the scale story is a documented deferral.
```

**The move:** let the numbers justify the deferrals. "This is one user, so I'll run
a single node and defer HA — I'll document RPO/RTO rather than build replicas."

---

## 3. High-level design (7 min) — draw the boxes and the seams

```
   ┌──────┐   HTTPS (Tailscale)   ┌───────┐   HTTPS/HTTP   ┌────────┐
   │ SPA  │ ─────────────────────► │ NGINX │ ─────────────► │ API    │
   │(React)│                        │ ingress│               │ (DRF)  │
   └──────┘                        └───────┘               └───┬────┘
                                                                │ write
                                                                ▼
        ┌─────────── durable ───────────  ┌────────────────────────────────┐
        │                                  │  POSTGRES                      │
        │  ┌──────────┐  outbox  ┌──────┐ │   expenses · loans ·          │
        │  │  Kafka   │◄────────│relay │ │   balance_changes · outbox      │
        │  │ topic    │         │(SKIP  │ │   processed_events            │
        │  │ loan_id  │         │LOCKED)│ └─────────────────────────────────┘
        │  │ key      │         └──────┘            ▲
        │  └────┬─────┘                             │
        │       │ consume                            │ idempotent
        │       ▼                                    │ update
        │  ┌───────────┐  balance_change            │
        └─►│ consumer  │────────────────────────────┘
           │(loan-updater)
           └───────────┘

   THE SEAMS (draw these explicitly — they're the load-bearing boundaries):
     UI↔API = OpenAPI contract        API↔domain = thin views + services
     API↔Kafka = transactional outbox  producer↔consumer = Avro + registry
     consumer↔Postgres = event_id idempotency
```

**The move:** name the *seams*, not just the boxes. Each seam is a place you can
change one side without the other — that's the design.

---

## 4. Data & events (5 min) — the domain, concretely

```
   Entities:  Expense, Loan (aggregate), Category, Source, BalanceChange
   VO:        Money(amount, currency)  ← the invariant lives here
   Aggregate: Loan + its balance_changes; invariant sum(changes)==outstanding
   Kafka key: loan_id  → per-aggregate ordering  (the critical decision)
   Idempotency: event_id unique constraint  → replay is safe
   Archival:  events partitioned by month; archive → verify → detach → drop
```

**The move:** the aggregate boundary and the Kafka key are the *same* decision.
Getting "the Loan is the unit of consistency" right makes ordering, idempotency, and
archival all fall out.

---

## 5. Reliability & consistency (3 min) — the fail-safes

```
   atomicity:  expense + outbox in one txn (no dual-write)
   delivery:   outbox → at-least-once → idempotent consumer
   ordering:   per-loan causal (partition key)
   integrity:  reconciliation: sum(changes)==outstanding; drift → replay
   durability: off-box backup + WAL archive → PITR; RPO/RTO stated
   availability: outbox absorbs a Kafka outage; write path stays up
```

---

## 6. Close with the trade-off map (the money answer)

```
   ┌─────────────────────────┬─────────────────────────────────────────────┐
   │  DIAL                    │  WHERE I SET IT (and why)                   │
   ├─────────────────────────┼─────────────────────────────────────────────┤
   │  Consistency            │  strong in-txn, eventual across async,       │
   │                         │  ordered per loan — window documented        │
   │  Latency ↔ Throughput   │  fast API (queued publish); freshness traded│
   │  Durability ↔ Speed     │  acks=all, sync commit (money events)        │
   │  Cost ↔ Retention       │  Kafka retention > reprocessing window       │
   │  HA (single node)       │  deferred + documented; RPO/RTO stated       │
   └─────────────────────────┴─────────────────────────────────────────────┘

   The closing line: "Every one of these is a dial I set deliberately, and the one
   I'd revisit first is HA — I'm on a single node, so my RPO/RTO are backup-bound,
   and the next step is a standby + quorum."
```

---

## 7. The reusable checklist (any system)

When you get "design X," run this exact order:

```
   1. Clarify + scope.  Functional + non-functional, with numbers.
   2. Back-of-envelope.  One user or one million? What's the real load?
   3. Boxes + SEAMS.     Name the load-bearing boundaries, not just components.
   4. The domain.        Entities/aggregates/VOs; the boundary that drives ordering.
   5. Fail-safes.        atomicity, idempotency, ordering, durability, availability.
   6. Trade-off map.     One row per dial, with the number and the reason.
   7. Close by naming the #1 thing you'd revisit first.
```

**The thing that gets you from L4 to L5:** step 6. Most people stop at step 3
("use Kafka + Postgres + K8s"). The L5/L6 move is *stating every dial and why* —
consistency window, latency budget, durability settings, retention, and the honest
"here's the deferred one and here's the next step."

---

## 8. How to practice this project

Redo steps 1–6 out loud, then:
- change one input (100k users) and re-derive the trade-off map — watch HA and
  partitioning move from "deferred" to "first."
- remove one seam (drop the outbox) and explain what breaks — that's the
  dual-write bug.
- name the single most expensive decision (the Kafka key) and defend it in 30 seconds.
