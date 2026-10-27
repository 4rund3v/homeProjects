# Latency & Throughput — in Depth

> How to budget latency, why you measure percentiles not averages, the
> latency/throughput trade, and how back-pressure keeps the two from fighting. These
> are the numbers an interview wants you to reason about, not recite.

---

## 1. Budget the async path (the segments that add up)

```
   total user-perceived latency for "record an expense, see the balance":

   ┌─────────────────────────────────────────────────────────────┐
   │ 1. API response           fast (the expense is committed)   │
   │    └─ the API does NOT wait on Kafka — it queues the event │
   │                                                          │
   │ 2. Outbox → relay       outbox depth-dependent             │
   │ 3. relay → broker ack   produce latency (acks=all)         │
   │ 4. broker → consumer    consumer lag-dependent             │
   │ 5. consumer → DB        the balance update transaction       │
   └─────────────────────────────────────────────────────────────┘

   → Segment 1 is what the user waits for. Segments 2–5 are the "eventual" window
     that makes the balance stale-by-a-moment, not the user's blocking time.
     Keeping the API fast is why publishing is QUEUED, not inline.
```

**The key split:** *user-perceived* latency (segment 1) vs *pipeline* latency
(segments 2–5). You optimize segment 1 for the API; you optimize 2–5 for freshness,
and you measure the gap with the event envelope's `produced_at` timestamp.

---

## 2. Percentiles, not averages

```
   mean latency hides the tail. The 1 user who waits 10s drags the mean up a little;
   p99 shows it plainly.

   ┌────────────────────────────────────────────────────────────┐
   │  • Alert on p99, never the mean                             │
   │  • p50 = typical user; p95/p99 = the users you must not     │
   │    make wait                                                │
   │  • a p99/p50 ratio that's growing = a degrading tail        │
   └────────────────────────────────────────────────────────────┘
```

**The "latency budget" discipline:** give each path a p99 target
(API < 200ms, balance-freshness < 5s, report < 10s), measure the segments, and know
*which segment* is breaking budget. "The system is slow" is not a diagnosis;
"the consumer segment is at 8s against a 5s budget" is.

---

## 3. The latency/throughput trade (the PACELC "else")

```
   You rarely get both at once. Trading:

   ┌──────────────┬──────────────────────────────────────────────────┐
   │  MORE LATENCY│  higher throughput (batching, more consumers,   │
   │              │  bigger outbox batches, read replicas)          │
   ├──────────────┼──────────────────────────────────────────────────┤
   │  LESS LATENCY│  lower throughput (smaller batches, synchronous │
   │              │  processing, smaller order window)              │
   └──────────────┴──────────────────────────────────────────────────┘

   The PACELC "else": in normal operation you TRADE a little latency (async hop)
   for decoupled, recoverable consistency — the balance lags a moment.

   In THIS system:
     • the API is fast (low latency, segment 1) — the event is queued
     • the balance is a moment stale (traded latency for decoupling)
     • throughput is bounded by consumer count ≤ partition count
```

**The decision you make deliberately:** "I keep the API's latency low by queuing
publishes (outbox). I accept a small balance-freshness latency. I cap throughput at
the partition count." Each is a number you can state.

---

## 4. Back-pressure — the part that keeps latency and throughput from fighting

```
   If egress < ingress, work piles up. What lives in that pile, and what happens
   when it overflows?

   ┌─────────────────────────────────────────────────────────────────┐
   │  1. THE OUTBOX = a durable, bounded, observable pre-Kafka buffer │
   │     Kafka slow → outbox rows accumulate (not dropped)          │
   │     → observed by outbox DEPTH                                 │
   ├─────────────────────────────────────────────────────────────────┤
   │  2. KAFKA RETENTION = the broker-side buffer                     │
   │     consumers lag → messages sit in the topic until retention   │
   │     → observed by CONSUMER LAG                                  │
   │     retention MUST exceed the worst-case reprocessing window    │
   │     or a lagging consumer loses data                            │
   ├─────────────────────────────────────────────────────────────────┤
   │  3. THE PRINCIPLE: every unbounded queue is a future incident.  │
   │     make every buffer durable + bounded + observable.           │
   └─────────────────────────────────────────────────────────────────┘

   → outbox depth + consumer lag are the two back-pressure metrics. Rising =
     egress < ingress; the buffer will eventually overflow.
```

**The anti-pattern:** an in-memory queue with no cap and no metric. It grows until
OOM. The L5/L6 move: "every buffer I add answers 'what caps it, and which metric
tells me it's filling?'"

---

## 5. Throughput ceilings (name them with the mechanism)

```
   ┌────────────────────────────────────────────────────────────────┐
   │  ceiling                        the mechanism                 │
   │  ─────────────────────────────  ─────────────────────────────  │
   │  consumer throughput           partition count (per-partition  │
   │                                 ordering)                       │
   │  Postgres write throughput     one node; PgBouncer pool size   │
   │  relay publish rate            Kafka acks + outbox batch size  │
   │  overall pipeline              the slowest stage (Amdahl's)    │
   └────────────────────────────────────────────────────────────────┘

   To raise any ceiling: find the slowest stage FIRST, then raise it. Raising a
   non-bottleneck stage changes nothing.
```

---

## 6. How this shows up here (the statements)

- **User latency** is the API response, which is fast because publishing is queued
  (outbox), not inline.
- **Balance freshness** is a traded, bounded latency — documented, not hidden.
- **Throughput** is bounded by consumer count ≤ partition count; the partition
  decision is a scaling decision made early.
- **Back-pressure** is two metrics — outbox depth and consumer lag — with retention
  sized above the reprocessing window.
- **The slowest-stage rule** — profile before scaling; the pipeline is only as fast as
  its slowest stage.

---

## 7. The one-paragraph latency/throughput answer

> "I keep the API's p99 low by *queuing* event publication (outbox) instead of
> publishing inline, so the user isn't waiting on Kafka. I accept a bounded
> balance-freshness latency and document it. Throughput is bounded by consumer count,
> which is bounded by partition count — so I set the partition count deliberately. I
> manage back-pressure with two observable buffers: outbox depth (pre-Kafka) and
> consumer lag (in-Kafka), with Kafka retention sized above my worst-case reprocessing
> window so a lagging consumer never loses data. And I alert on percentiles, not
> means, because the tail is what users feel."
