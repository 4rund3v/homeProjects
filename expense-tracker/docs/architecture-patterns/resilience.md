# Resilience Patterns — The Toolbox

> The patterns that keep a dependency's slowness or failure from taking down the whole
> service. Each with: what it is, where it's used in this project, and the one thing
> that goes wrong if you do it badly.

---

## 1. Timeouts

**The rule:** *every* external call has a timeout. A retry with no timeout is just a
slower failure.

```
   where they live here:
   • relay → Kafka produce            (a hung broker must not hold a relay thread)
   • API  → OAuth provider (login)    (a slow IdP must not hang the login endpoint)
   • API  → schema registry lookup    (a slow registry must not stall the consumer)
   • NGINX → upstream proxy_read_timeout   (see nginx/reverse-proxy.md §4)
```

**The common mistake:** a timeout that's too long. "The provider is slow, so 30s"
means 30s of held connections per request. Set the timeout to what the *caller* can
tolerate, not what the *provider* averages.

---

## 2. Retries with backoff

**Rule:** retry transient failures, with *exponential backoff + jitter*, a bounded
number of times, and **only on idempotent operations**.

```
   attempt:  0        1          2          3
   delay:   100ms    200ms      400ms      800ms      × jitter
   → "fast" failures get quick retries; the jitter prevents a herd
     of clients all retrying at the same instant (thundering herd)

   NEVER retry a non-idempotent call blindly —
   retrying a POST /expenses could create two expenses.
   (This is why the outbox + idempotent consumer exist.)
```

**What goes wrong:** retrying a non-idempotent request without an idempotency key →
duplicates. Retrying without a cap → you amplify a downstream failure into your own
outage.

---

## 3. Circuit Breaker

**Rule:** stop calling a dependency that keeps failing, for a cooldown period.

```
   CLOSED ──(failure rate > threshold)──► OPEN ──(cooldown elapses)──► HALF-OPEN
   │                                                        │
   │  normal: pass calls, count failures                    │  allow ONE probe
   │                                                        ▼
   └────────────(probe succeeds → CLOSED)──────────────(probe fails → back to OPEN)
```

**Where:** synchronous external calls — the OAuth provider, the schema registry.
**Not where:** the Kafka path — that's handled by the outbox (failures queue, they
don't cascade). Don't bolt a breaker onto a path that already has a better pattern.

**What goes wrong:** a breaker that opens too easily (jitter trips it and you lose
normal traffic) or that *never* closes (you forget the probe). The probe is the part
people skip.

---

## 4. Bulkhead

**Rule:** isolate the resource pool of a *flaky* dependency so its failure can't
exhaust the whole service.

```
   Without bulkhead:  all requests share one thread pool / connection pool
                      one slow external API → all requests queue behind it → whole
                      service down

   With bulkhead:     the flaky dependency gets its OWN small pool
                      it can saturate its pool and time out; the main pool is untouched
```

**When you need it:** when you add a *second* flaky external dependency (a payment
provider, a third-party FX rate API). Right now the outbox already acts as a
bulkhead for the async path.

**What goes wrong:** a bulkhead that's too big — it's just the old shared pool with a
line through it. The size should be *small enough* to contain the damage.

---

## 5. Load Shedding

**Rule:** under overload, deliberately drop the least-important work to protect the
critical path.

```
   in this system:
   • an analytics consumer can lag / drop, WITHOUT affecting the loan-updater —
     that's load shedding by separation (different consumer group).
   • the API can shed: return 503 on a known-overloaded endpoint rather than queue
     until the pool dies (NGINX's limit_req is the edge version).
```

**The principle:** not all work is equal. Shed the "nice to have" (analytics,
background recompute) before the "must have" (recording an expense, updating a
balance).

---

## 6. Rate Limiting / Throttling

**Rule:** cap how fast a client (or a dependency) is consumed, and say so honestly.

```
   two layers, different jobs (see rate-limiting.md):
   • EDGE (NGINX): per-IP, coarse — shed floods before they reach Python
   • APP (DRF):    per-user, semantic — stricter for logins, generous for reads
```

**What goes wrong:** putting per-user limits at the edge (the edge can't authenticate)
or per-IP limits in the app (spoofable). Each layer keys on what it *knows*.

---

## 7. The Resilience "stack" for one external call

The pattern composition that makes a single flaky dependency survivable:

```
   call ──► timeout ──► retry (backoff+jitter, capped, idempotent)
                          │
                          ├─► circuit breaker (stop when failing, probe to close)
                          │
                          └─► bulkhead (isolated pool, small, so it can't take you down)
```

**And the load-shedding / rate-limiting that surrounds it.** One dependency, defended
by *five* patterns — each catching a different failure. That's the whole resilience
story, and it's the answer to "how do I make this not fall over when X is down?"

---

## The L5/L6 synthesis (memorize this mapping)

| Failure of a dependency | Pattern that catches it |
|-------------------------|-------------------------|
| Slow | timeout (+ bulkhead so slowness is contained) |
| Transient error | retry with backoff + jitter (idempotent only) |
| Sustained failure | circuit breaker (stop + probe) |
| Resource exhaustion | bulkhead (isolated, small pool) |
| Overload | load shedding (drop non-critical) / rate limiting (cap input) |
| Poison input | DLQ (route, don't retry forever) |

**The framing that earns the points:** "I don't add resilience patterns speculatively.
I add *timeout + bounded backoff* to every external call by default. I add a *circuit
breaker* when I have a synchronous call that can hang. I add a *bulkhead* when I add a
second flaky dependency. And for the async path, I don't need any of those — the
**outbox** already does durable, retriable, back-pressured delivery. The pattern
choice is a function of where the failure can propagate."

---

## How this shows up here

- **Timeouts** on the relay's Kafka produce and on the API's OAuth call.
- **Retry + backoff** in the relay (republish an outbox row that failed to send) —
  capped, and the consumer's idempotency makes the retry safe.
- **Circuit breaker** around the synchronous OAuth/schema-registry calls (add when you
  wire them).
- **Bulkhead** for any second external dependency you add (e.g. an FX-rate API).
- **Load shedding** = the analytics consumer is separate from the loan-updater.
- **Rate limiting** = NGINX per-IP at the edge + DRF per-user in the app.
- **DLQ** for poison events the consumer can't process.
- The **outbox** is the single best-resilience tool in the whole system — it replaces
  three of the patterns for the async path.
