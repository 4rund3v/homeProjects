# 17 — System Design: The L5/L6 Differentiator

**Folder:** `17-system-design/`

---

## Teach first: what "system design" actually is (not the diagram)

Junior system design = draw boxes, name components, hope it's sensible. **L5/L6 system design is a sequence of tradeoffs made under real constraints, each one justified against an explicit alternative.** The diagram is the *output*; the design is the *argument*.

The bar is captured by one question an L6 interview panel will probe: **"Why this and not that?"** For every non-obvious choice you've made, you should be able to name:

1. The constraint that drove it (scale, cost, team size, latency budget, consistency need).
2. The alternative you rejected.
3. The cost you accepted.
4. The condition under which you'd reverse the decision.

If you can't answer all four for a decision, you made it by vibes, not design.

---

## The design sequence (do it in this order)

A senior designs *forward*, not to the diagram:

1. **Requirements** — split into functional (what it does) and non-functional (latency, availability, consistency, cost, security). **Non-functional requirements are where the design lives.** A vague "make it fast" is not a requirement; "p99 < 500ms at 10k RPS" is.
2. **Estimates** — back-of-envelope. How many requests? How much data per day? How much memory? These pin the scale and rule out most architectures immediately.
3. **API/data model** — what crosses service boundaries, what the data looks like. This is where most of the hard decisions are.
4. **Component design** — *now* draw the boxes.
5. **Failure analysis** — what breaks, how does the system degrade, what's the blast radius.
6. **Tradeoffs, explicitly** — the document's center of gravity.

> **Senior lens — estimates are a design tool, not homework.** They're how you rule out nonsense. If your estimate says "200 GB/day" and you're proposing a synchronous, strongly-consistent, three-replica synchronous-commit design, the estimate is telling you that's absurd and you need a different consistency model. **Do the estimate before you draw anything.**

### The estimates you'll actually do for Outline

- **Scale:** a homelab knowledge base is *small*. Maybe 10 users, a few hundred docs, attachments a few MB each. The interesting thing: **you're deliberately *over*-building** (3-node cluster, HA Postgres, service mesh, DR) to *learn* the patterns. A senior reading your design says: "the scale doesn't need this; the *learning objectives* do. Say that out loud — that's the honest framing." You wouldn't run a 3-node etcd quorum for 3 users in production; you run it here because you're buying the lesson cheaply. **Naming that tradeoff is itself the L6 move.**

---

## The core concepts, in the order they decide outcomes

### Consistency and CAP

The question you must answer for *every* piece of state: **what does the user see when a partition happens?**

- **CAP, honest version:** you can pick at most two of Consistency, Availability, Partition-tolerance — *and partitions always happen on a network*, so the real choice is **CP vs. AP** (you'll partition; the question is what you give up when you do).
- **Consistency model is a spectrum**, not a binary:
  - **Strong / linearizable** (Postgres single-writer, etcd): every reader sees the latest write. Expensive; you pay in latency and availability under partition.
  - **Eventual** (dynamo-style, Redis replicas after failover, DNS): reads may lag. Fast, available under partition.
  - **Session / read-your-writes** (Redis, many caches): consistent *within* a session, not across all replicas.
  - **Causal / read-your-updates** — between the above two.

For Outline:
- **Postgres = strongly consistent** for document content. *Correct* — you'd notice immediately if you saved a doc and read back the old version. A knowledge base is not a place for eventual consistency on the primary read path.
- **Redis = eventual within a failover window.** A replica promoted by Sentinel (doc 07) may briefly have stale data or miss a queued job. Acceptable: sessions re-establish, jobs re-run.
- **Search index (if you add it) = eventually consistent by design.** "I just edited a doc, does it show up in search?" — a second later is fine.

> **Tradeoff — the classic CP question: Postgres quorum under partition.** A 3-instance CNPG cluster tolerates one node loss, but if your network partitions the cluster 1+2, the side with 1 *cannot* make quorum and **the whole database goes read-only / unavailable** (CP). That's the correct, honest behavior for a strongly-consistent DB — and it means your *availability* of the database depends on *not* partitioning. A senior designs the **network to make partitions rare** (doc 13 node health, NPD, ingress design) rather than pretending the DB is highly available under a bad network. **Availability is a property of the whole system, not the database.**

### The consistency decisions Outline forces you to make

| State | Model | Why |
|---|---|---|
| Document content | Strong (Postgres) | Read-your-writes is user-visible correctness |
| Session (Redis) | Eventual within failover window | Re-derivable; jobs re-run |
| Attachment storage (MinIO) | Object durability, not ACID | Files are written once; reads are strong per object |
| Search index | Eventual | Acceptable latency; users forgive "just edited, not searchable yet" |
| Queue (jobs) | At-least-once, idempotent consumers | A missed job is worse than a duplicate; make handlers idempotent |

---

## Partitioning / sharding — the decision most people skip too early

For Outline at any realistic scale you **do not shard**. Single Postgres + read replicas is the right answer. The senior move is saying so *and* knowing *when you'd shard*:

- **Read scaling:** add Postgres read replicas; route reads to replicas. (Outline is read-heavy: many reads per doc, few writes.)
- **Write scaling (only if you ever hit it):** shard by tenancy — **each workspace gets its own Postgres** (multi-tenant with per-tenant DBs). This is the natural shard key for a knowledge base. **Don't build it now; design the boundary so it's *possible* — keep all queries scoped to one workspace's data.**

> **Threshold — the signal that you need to shard.** You don't shard at "the DB is slow." You shard when a *single logical partition* (one tenant) grows past what one Postgres can serve, or when you need *isolation* between tenants for security/billing. **Before that, read replicas + better queries + caching.** Sharding is a last-resort, high-cost decision; naming the threshold at which you'd do it shows the judgment L6s are graded on.

### Caching

Outline uses Redis (doc 07) as a cache *and* queue. The design decisions:

- **What to cache:** expensive-to-compute, read-heavy, tolerable-staleness things — rendered doc, user profile, search results.
- **Invalidation strategy:** the hard part. "Cache invalidation is one of the two hard things in CS." For docs: invalidate on write (write-through / write-invalidate) *scoped to that doc*. Accept a bounded staleness elsewhere.
- **TTL as a safety net:** even with invalidation, set a short TTL so a missed invalidation can't serve data forever.

> **Failure mode — stale cache serving wrong data after a write.** The classic. Write the doc, read through the cache, get the old version. Senior fix: **read-your-writes** — after a write, the user's own reads bypass or tag the cache so they see their write; other readers get eventual consistency. This is the *session* consistency model in action.

---

## Load balancing and rate limiting

- **LB:** ingress-nginx (docs 01, 10) is the L4/L7 edge. Within the cluster, Services are the L4 LB.
- **Rate limiting / backpressure:** what happens when a client hammers Outline? You don't let it take down shared resources. Options: ingress-level limits (per-IP), app-level token bucket, or a queue for heavy jobs (doc 07). **The design point: put the limit at the *boundary*, and shed load to protect shared dependencies (Postgres), not at the last mile.**

> **Tradeoff — reject early vs. queue early.** A hard 429 protects the system but tells the user "go away." A queue says "we'll get to it" but can grow unboundedly and hide an overload. **The L6 answer: reject fast with a clear signal, and only queue work that's safe to delay and bounded in size.** Unbounded queues are where overload lives.

---

## Failure domains and blast radius

Design the system so a failure is *contained*. The domains in this project:

- **Node** (doc 13) — pods reschedule; PDBs (doc 02) keep quorum.
- **Availability zone / rack** — in a homelab, "the whole machine" is your AZ. One Proxmox host = one AZ. That's an honest constraint to state.
- **Service** (network policy, doc 14) — a compromised pod is isolated.
- **Data** (Postgres, doc 06) — failover + PITR.
- **Identity** (Keycloak, doc 09) — if it's down, *nobody* can log in. That's a single point of failure you should think about deliberately.

> **Senior lens — every "availability" claim needs a failure domain.** Saying "Outline is HA" means nothing until you've said "survives the loss of any *single* node; does *not* survive a rack power failure." Name the domain, name the survival, name the RTO/RPO (doc 15). Vague HA is a red flag in a design review.

---

## ADRs — how a senior records the design

**Architecture Decision Records** are one-page documents for each significant decision:

```
# ADR-0042: Use CloudNativePG, not a raw Postgres StatefulSet
Status: Accepted
Context: Outline needs HA Postgres with PITR; we considered a raw
StatefulSet and a managed service.
Decision: CloudNativePG operator.
Consequences: + automated failover/PITR, + operator as a new moving
part to run, + we own the operator's upgrades.
Rejected: raw StatefulSet (no failover/PITR; too much ops surface we
don't need to learn twice), RDS-like service (we want to own the stack).
Condition to revisit: if CNPG maintenance becomes a disproportionate
burden, we'd move to a managed service.
```

> **The L5→L6 shift is visible right here.** An L5 writes code. An L6 writes *ADR + code*, because the ADR is how the *next* person — or the reviewer, or the promotion panel — understands **why the system is shaped the way it is.** A codebase without ADRs is a codebase that re-litigates every decision from zero. Document the decisions (doc 23 develops this further as a leadership skill).

---

## The multi-region / DR thought process (even in a homelab)

You won't run two regions, but **reason about it**: what would you *do*?

- **Split-brain avoidance** — two Postgres primaries is not HA; it's a correctness bug. DR = primary + a *cold* standby that promotes on failover (doc 15's RTO/RPO).
- **Data replication lag** — the DR standby's RPO is the replication lag. Measure it.
- **The control-plane question** — in a real multi-region system, *etcd / the control plane* is a harder HA problem than the apps. (You can't trivially split-brain the control plane.)

For the homelab the honest line: **you can't test two regions; you *can* test the RTO of a single-region disaster (doc 15) and you can *document* the multi-region plan you'd build.** Writing that plan is the design exercise; you don't need the hardware.

---

## The L5/L6 lens: what panels probe

| Probe | Junior answer | L5/L6 answer |
|---|---|---|
| "Why this DB?" | "Postgres, it's popular." | "Strong consistency is user-visible here (read-your-writes); Postgres + CNPG gives PITR; I rejected event-sourcing/dynamo because the write volume doesn't justify it. Here's the threshold that'd change it." |
| "What's the consistency model?" | "It's consistent." | "Per-state: Postgres linearizable, Redis eventual within failover window, search index eventual, cache read-your-writes. Here's why each is the *right* kind of consistency for that data." |
| "What breaks if the network partitions?" | "The load balancer handles it." | "Postgres goes read-only (CP). That's correct. My design invests in *not* partitioning (NPD, node health) rather than pretending the DB survives a bad network. RTO is X, RPO is Y." |
| "How do you scale writes?" | "Add replicas." | "Replicas scale *reads*. Writes: I don't need to shard yet; I'd sharded by tenant with per-tenant DBs, not by hash, for isolation + operational boundaries. Here's the threshold." |
| "What's your biggest tradeoff?" | (nervous silence) | "I'm over-building for the scale because the *objective* is learning the platform patterns cheaply. In prod, I'd run a single node and one Postgres. I'm buying the lesson now and paying the ops cost for it." |

> **The meta-skill:** an L6 *narrates the tradeoff, states the constraint, names the alternative, and gives the revisit condition.* That four-part structure — **decision / constraint / rejected alternative / revisit condition** — is the single most reusable thing in this document. Use it on every decision in every design you write.

---

## Exercises (do these, don't read them)

1. **Estimate Outline's day-2 numbers** (docs/day, attachments/day, RPS during a 10-user day). Write one page. Does it justify the 3-node cluster? Frame the answer honestly.
2. **Write 5 ADRs** for your current choices (CNPG, MinIO, Keycloak, ingress-nginx, k3s-vs-kubeadm). Each: decision / constraint / rejected alternative / revisit condition.
3. **Failure-domain map** — one page: for each domain (node, rack, service, data, identity), what survives, what doesn't, RTO/RPO.
4. **The consistency table** — for every piece of state in Outline, name the model and *why that's correct.*
5. **Design the scaling path** — "you have 500 tenants, each up to 500 docs. When do you shard, how, and why by tenant not by hash?"

---

## Exit criteria

- [ ] Requirements split into functional + non-functional; the NFRs are *quantified*
- [ ] Estimates written and used to rule out at least one architecture
- [ ] Consistency model named per state, with justification
- [ ] Failure-domain map with explicit survival + RTO/RPO
- [ ] The CP-vs-AP question answered for Postgres quorum honestly
- [ ] Scaling path with an explicit shard threshold (even if "we don't shard yet")
- [ ] 5+ ADRs using the four-part structure
- [ ] You can walk a panel through *any* non-obvious decision and give the four-part answer without notes

Next: `18-service-mesh` — the network-identity layer that service-to-service auth needs.
