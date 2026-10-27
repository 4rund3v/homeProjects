# Consistency — in Depth (CAP, PACELC, and where this system actually sits)

> The consistency model, done right. Most people get the "CAP = pick two" slogan; the
> skill is stating the *real* trade-off and naming *where your* system sits on the
> spectrum.

---

## 1. The consistency spectrum (strongest → weakest)

```
   LINEARIZABLE        a read returns the latest committed write, as if there were
                       one sequential machine. Strongest, most expensive.

   SEQUENTIAL          ops appear in some order consistent with real time.

   CAUSAL              a cause is always visible before its effects.
                       (if I see "balance updated," I also saw "expense recorded")

   EVENTUAL            given enough time AND no new writes, all replicas converge.
                       The model of most async/distributed systems.

   WEAK/RELAXED        replicas can diverge indefinitely; no convergence promise.
```

**The one question that locates a system:** "When a reader looks at X *right now*,
are they guaranteed to see the latest write to X?" Strongest: yes, immediately.
Eventual: no, they might see a slightly-stale value that converges later.

---

## 2. Where THIS system sits (the exact answer)

```
   ┌────────────────────────────────────────────────────────────────────┐
   │  WITHIN a Postgres transaction:  LINEARIZABLE                    │
   │    expense insert + outbox write = one atomic unit                │
   │    balance change + outstanding update = one atomic unit          │
   ├────────────────────────────────────────────────────────────────────┤
   │  ACROSS the async boundary (expense → loan):  EVENTUAL            │
   │    after POST /expenses/ → 201, the balance updates a moment      │
   │    later (outbox relay + consumer lag)                            │
   │    window = relay lag + consumer processing                       │
   ├────────────────────────────────────────────────────────────────────┤
   │  PER-LOAN ORDERING:  CAUSAL                                      │
   │    keying by loan_id guarantees changes apply in order,           │
   │    so "balance updated" is never visible before "expense recorded"│
   └────────────────────────────────────────────────────────────────────┘

   The full, honest statement:
     "Strong within each database transaction; eventual across the async
      event boundary; causally-ordered per loan; idempotent per event."
   That's the consistency model, in one breath.
```

**The discipline:** *never promise stronger consistency than you deliver.* "Expense
recorded, balance updating" is honest. "Done" would be a lie — the balance lags.
The API contract must say the honest version
([`api-contracts-guide.md`](../api-contracts-guide.md) §5).

---

## 3. CAP — the theorem, stated correctly

**The real statement (not "pick two"):**

> When a **network partition (P)** occurs, a distributed system must choose between
> **Consistency** and **Availability** *for the duration of that partition*.

**Why "pick two" is wrong:**
- **P is not optional.** In a distributed system, partitions *happen*. You don't
  "choose" P — you handle it. So the real choice is only "given P, do I keep
  serving (A) or refuse to serve inconsistent/stale data (C)?"
- Outside a partition, you can have both C and A — that's the PACELC "else" clause.

**How CAP shows up here:**
- **Kafka under a partition:** with `min.insync.replicas` set high, a partition loses
  enough brokers and produce *stops* — you chose **C** over **A**. Lower it, and it
  keeps accepting (A) but risks losing data. On one node this is moot; in prod it's
  the real dial.
- **Your async boundary:** you chose **A** — the API keeps accepting expenses even if
  Kafka is down (the outbox absorbs it) — and accepted **eventual consistency** for the
  balance. That's a CAP-flavored decision, made explicit.

**The L5/L6 reframe:** stop saying "CAP means pick two." Say: *"During a partition, I
favor ___ over ___, and here's the consequence — and here's the config knob."*

---

## 4. PACELC — the more complete lens

**The statement:**

> **P**artition **A**vailability or **C**onsistency, **E**lse **L**atency or
> **C**onsistency.

CAP only describes behavior *during a partition.* PACELC adds the normal-operations
trade: even with no partition, you trade **latency** for **consistency**.

**Applied to this system — the "else" trade is the whole design:**

```
   "ELSE" (no partition, normal operation):
     I trade a little LATENCY (the async hop through Kafka — the balance lags
     the expense by a moment) for DECOUPLED, RECOVERABLE consistency.

   → The balance is briefly stale. That's the everyday cost of the design.
     PACELC names exactly that trade that CAP ignores.
```

**The ordering guarantee that makes "eventual" safe:** keying by `loan_id` means
per-loan changes apply *in order* (`kafka-guide.md` §2). So eventual + ordered +
idempotent = correct, just not instant. Without the ordering guarantee, "eventually"
could mean "in a wrong order" — and the balance would be wrong, not just late.

---

## 5. The 3 questions that pin down a consistency answer

When asked "what's the consistency model of X?":

```
   1. At the unit of work, is it atomic?          (DB transaction = linearizable)
   2. Across async boundaries, is it eventual?     (event boundary = eventual, bounded window)
   3. What ORDERING guarantees protect it?        (per-loan causal ordering + idempotency)

   Answer all three and you've fully specified the model. Missing any one and you've
   only stated part of it.
```

---

## 6. How this shows up here (the statements to use)

- **Strong** within each Postgres transaction (expense+outbox; change+outstanding).
- **Eventual** across the event boundary; the window is documented in the API contract.
- **Causally ordered** per `loan_id` (partition key), **idempotent** per `event_id` —
  which is what makes eventual consistency *correct* rather than just *late*.
- **The CAP trade:** favoring availability of the write path when Kafka is down
  (outbox absorbs it), accepting eventual consistency for the balance.

---

## 7. The trap to avoid in the answer

The naive answer is "it's eventual consistency." The L5/L6 answer is:
*"Strong within transactions, eventual across the async boundary with a bounded window,
causally ordered per loan, and idempotent per event — and I've documented that window
in the API contract rather than pretending the balance is current when I return 201."*

The last clause — *documenting the trade instead of hiding it* — is what separates
"knows the concept" from "can operate the system."
