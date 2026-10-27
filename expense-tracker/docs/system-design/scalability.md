# Scalability — in Depth

> What "scale" actually means here, which axis is the constraint, and the exact
> mechanism on each axis. The discipline: scale the thing that's *measurably* the
> bottleneck, one at a time.

---

## 1. The three scaling axes (and which one you're on)

```
   AXIS 1 — VERTICAL (scale up)
     Bigger node. More CPU/RAM. One machine.
     ✓ trivial, no coordination   ✗ has a ceiling; a node loss = total loss
     → THIS PROJECT'S DEFAULT. A single k3s node scales up first.

   AXIS 2 — HORIZONTAL (scale out)
     More instances of the same stateless thing behind a LB.
     ✓ survives one instance; scales past one box   ✗ needs shared state + LB
     → the API scales out (stateless, behind NGINX).
     → Postgres does NOT scale out trivially.

   AXIS 3 — FUNCTIONAL (split)
     Decompose so parts scale independently (API / consumer / reporting).
     ✓ each scales to its own load   ✗ more moving parts, more consistency to reason about
     → the consumer already scales independently of the API.
     → a reporting read model is the next functional split (light CQRS).
```

**The rule:** an interview answer that says "add more replicas" before naming the
bottleneck is a guess. Name the bottleneck, *then* the axis.

---

## 2. The real bottlenecks in this system, in order

```
   ┌───────────────────────────────────────────────────────────────────┐
   │ 1. THE SINGLE NODE                                               │
   │    Caps everything. Vertical scaling helps; a node loss is a    │
   │    total outage. This is the #1 honest constraint to name.       │
   ├───────────────────────────────────────────────────────────────────┤
   │ 2. KAFKA CONSUMER THROUGHPUT = PARTITION COUNT                  │
   │    You can't run more loan-updater replicas than partitions.    │
   │    Throughput ceiling is set at topic-creation time. This is a   │
   │    scaling decision made early, not a knob you turn later.      │
   │    → the partition-count choice is a *scalability* decision.     │
   ├───────────────────────────────────────────────────────────────────┤
   │ 3. POSTGRES WRITE PATH ON ONE NODE                              │
   │    The outbox + balance writes land on one Postgres.            │
   │    → first scale-out step is a READ replica (dashboards),       │
   │      not write sharding. Sharding is far away from needed.      │
   ├───────────────────────────────────────────────────────────────────┤
   │ 4. CONNECTION POOL (PgBouncer)                                  │
   │    Many app connections → few real Postgres connections.        │
   │    Pool exhaustion shows up as "the DB is slow" when it's        │
   │    actually "no free connections."                               │
   └───────────────────────────────────────────────────────────────────┘
```

---

## 3. The scaling plan, axis by axis (and when to trigger each)

### The API — horizontal

```
   today: 1 API replica on the node
   trigger: CPU or p99 latency climbs under load
   move:  2–N API replicas behind NGINX (it load-balances across them)
   cost:  the API must stay stateless (it is — JWT, outbox is the seam)
   note:  on one node, "replicas" still run on the same box; the win is
          rolling updates, not more hardware.
```

### The consumer — horizontal *bounded by partitions*

```
   today: 1 loan-updater
   trigger: consumer lag climbs (ingress > egress)
   move:  add consumer replicas UP TO the partition count
          (beyond that they sit idle — Kafka assigns 1 partition per consumer)
   cost:  to go beyond the partition count you must REBALANCE + add partitions,
          which is a schema/ops change, not a config change
   note:  the partition count is the throughput ceiling — set it deliberately now
```

### Postgres — read scaling, then write sharding (far away)

```
   step 1: a READ replica / hot standby for dashboards + reports
           (the write path stays on the primary; reads fan out)
   step 2: when write throughput itself is the bottleneck — consider
           partitioning (by time, on balance_changes/expenses) or sharding
   note:  a personal expense tracker will NOT hit step 2. Name it, defer it.
```

### The node — vertical, then real HA

```
   today: one node; scale up (bigger machine) is the only lever
   the honest statement: "RTO/RPO today = restore time / backup interval.
   Real HA needs a second node + a quorum (etcd/Patroni) + a VIP."
   → the single-node caveat is a *documented limitation*, not a bug
```

---

## 4. The numbers that make scaling concrete (interview currency)

- **Consumer ceiling:** if `expenses.v1` has 4 partitions, consumer throughput tops
  out at ~4× one consumer. To double throughput → 8 partitions (an offline topic
  operation, so plan it, don't flip it casually).
- **Postgres read replica:** cuts read load on the primary ~proportionally; a
  dashboard + 3 reports could move almost all reads to a replica.
- **PgBouncer pool sizing:** `pool_size ≈ real_connections_needed`, and
  `max_client_connections = pool_size × consumers`. Exceed it and clients queue.

---

## 5. The "scale what's measured" discipline

```
   BEFORE scaling anything, name the metric that proves the need:
     • API        → p99 latency / CPU  (not "it feels slow")
     • Consumer   → consumer lag       (the Kafka health signal)
     • Postgres   → connection wait, cache hit ratio, seq scans
     • The node   → RPO/RTO + backup/restore time

   Then pick the SMALLEST axis that addresses the metric.
   "I saw consumer lag double, so I added one consumer replica (now 2 of 4
   partitions)."  ← that's a scaling answer with a cause, an action, and a limit.
```

---

## 6. How this shows up here (the defensible statements)

- **Vertical now** — single node, scale up is the only meaningful lever today.
- **The Kafka key/partition decision is a scaling decision** — made once, early.
- **Read replica is the first Postgres move** — for dashboards, not sharding.
- **The API is stateless by design** — it scales horizontally without coordination
  because the outbox + JWT removed per-request state.
- **Single-node HA is deferred and documented** — RPO/RTO stated honestly.
