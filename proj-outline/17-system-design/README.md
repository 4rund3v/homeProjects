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

**Back-of-envelope arithmetic (the kind a panel will ask you to do on the whiteboard):**

Assume: 10 active users, 8h workday, 200 documents edited/created per day in aggregate, each doc ~5KB text + 2MB of attachments on average, one search request every ~30s of active time.

- **Requests:** ~200 edits × ~5 API calls each (save, autosave, list, read, search) = **1,000–5,000 requests/day** ⇒ ~10 req/day avg, peaked at ~3 RPS at morning.
- **Data written:** 200 × (5KB + 2MB) ≈ **400 MB/day** (attachments dominate; text is noise).
- **Storage growth:** 400 MB/day × 30 = ~12 GB/month ⇒ 150 GB/year.
- **RAM steady-state:** Postgres 2–4 GB, Redis 1 GB, Outline server+worker 2 GB, MinIO ~1 GB per node ⇒ ~8 GB across 3 nodes (2.4 GB/node).

The *design* takeaway: **even a 100× version of this scale (1,000 users, 40 GB/day, 4 TB/yr) is still a single Postgres instance's territory.** You'd need ~10,000× before sharding is forced by write volume, and you'd hit the *isolation* threshold (multi-tenancy needing hard separation) far earlier.

> **The honest framing** — you're *deliberately over-building* (3-node cluster, HA Postgres, service mesh, DR) to *learn the patterns*. A senior reading your design says: "The scale doesn't need this; the *learning objectives* do. I'm buying the lesson cheaply." **Name that tradeoff out loud** — it's the L6 move.

---

## The core concepts, in the order they decide outcomes

### Consistency and CAP

The question you must answer for *every* piece of state: **what does the user see when a partition happens?**

- **CAP, honest version:** you can pick at most two of Consistency, Availability, Partition-tolerance — *and partitions always happen on a network* (packet loss, a down switch, a bad NAT, a split in a WAN link), so the real choice is **CP vs. AP** (you'll partition; the question is what you give up when you do).

> **The math behind CAP (the thing a panel will derive, not recite):** a quorum of N replicas can only *commit* a write when it lands on `⌈N/2⌉ + 1` of them. That's the minimum that can't split into two independent quorums — the classic *pigeonhole* guarantee. So:
>
> - N = 1: quorum 1. No HA at all; a single node death = full outage.
> - N = 2: quorum 2. **Worse than N = 1** — either node dying kills writes; you lose HA and add a network peer. This is why 2 is never a quorum size.
> - N = 3: quorum 2. Survives *one* node loss. The minimum sensible HA configuration.
> - N = 5: quorum 3. Survives *two*. Diminishing returns on fault tolerance; you pay more quorum traffic per write.
>
> **The CP consequence under partition:** if your 3-replica cluster partitions into 1 + 2, the majority (2) can still commit writes; the minority (1) *cannot* — it stalls. **That stall is CP.** If instead you let the minority commit, you'd get two diverged "last wins" on rejoin — that's AP, and you've chosen to *lose* consistency to preserve availability. **You can't have both across the split; the quorum size is exactly what forces the choice.**
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

The exit criteria asks for *five* ADRs. Here are the other four, as **fill-in templates** so you can pattern-match your own without starting from a blank page:

```
# ADR-0043: Use MinIO (distributed, EC:2, 4 local-PV nodes) not a plain NFS volume
Status: Accepted
Context: Outline attachments + all in-cluster backups must survive a
node loss; NFS would make the whole object store go down on one host.
Decision: MinIO in distributed mode, EC:2, 4 pods × local PVs (one per
node), no shared backend.
Consequences: + survives 2-of-4 node loss for both reads and writes;
+ S3 API so CNPG/Outline/backup tooling all agree on one substrate.
Rejected: NFS (single point of failure; RWX semantics differ from S3),
standalone MinIO (no redundancy — a single pod death = total outage
of every backup we store there).
Condition to revisit: if we ever need >2 simultaneous node losses
for our data tier, we move to 6+ nodes or to a real cloud S3.
```

```
# ADR-0044: Keycloak as the IdP, not Outline's built-in local auth
Status: Accepted
Context: Every "user" login needs MFA-able identity; a local password
table adds another credential store to breach, and Outline alone
wouldn't serve Jenkins/Harbor/Grafana with a shared login.
Decision: Keycloak in-cluster; Outline + Jenkins + Harbor all point
to the same realm via OIDC.
Consequences: + one credential surface, + short-lived JWTs, +
password/MFA lifecycle owned by a purpose-built tool.
Rejected: Outline's local auth (no federation; another credential store),
a public SaaS IdP (we're *owning the whole stack* — the point of the project).
Condition to revisit: if we add 10+ apps that need SSO, we should
consider a hosted IdP for managed patching.
```

```
# ADR-0045: ingress-nginx over Traefik or haproxy
Status: Accepted
Context: We need L7 routing by host, TLS termination via cert-manager
DNS-01 ACME, and per-service rate limits.
Decision: ingress-nginx + cert-manager.
Consequences: + mature controller, + cert-manager can auto-issue/renew,
+ huge docs surface, + one of the few ingress controllers that does
per-IP/per-service rate limits via annotation.
Rejected: Traefik (weaker ACME story at this point; the ingress
resource shape has shifted across major versions — drift risk),
MetalLB + raw HAProxy (less per-service control, more YAML to write
by hand).
Condition to revisit: if we add service-mesh routing (doc 18), we'll
retire per-service ingress rate limits and rely on the mesh's
traffic policy instead.
```

```
# ADR-0046: k3s (for M2) + kubeadm (later) — not RKE2
Status: Accepted
Context: We need a cluster that stands up in minutes to reach the
interesting layers (Jenkins, observability) *and* we need to actually
learn the control plane.
Decision: k3s first for speed; a parallel kubeadm cluster later for
the control-plane learning pass.
Consequences: + fast start, + minimal per-node footprint (3 nodes is
enough), - k3s defaults (SQLite storage, embedded etcd toggle) are
slightly off-upstream so some k8s behaviors need verification.
Rejected: RKE2 (functionally k3s, no advantage for us), air-gapped
kubeadm bootstrap (weeks of extra setup to get to the same day-2 state).
Condition to revisit: if we ever run in a cloud, we'd use the
cloud's managed control plane and stop reasoning about etcd.
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

## The L5/L6 lens: what panels probe to *refute* you

The table below is *not* "what I'd say" — it's **what a hostile panel will ask to expose that you're reciting**, and **which concrete artifact** (a number, an ADR, a measured value) proves you're not. Bring those artifacts to the interview; don't narrate them from memory.

| Panel probe | The refute they're looking for | The concrete artifact that *stops* the refute |
|---|---|---|
| "Why this DB?" | Can you state *the number* at which Postgres stops being the right answer? | Your estimate (the 40 GB/day figure above) + a line: "single Postgres stays the answer up to *~10k writes/sec sustained*; beyond that I'd add read replicas and *then* look at sharding by tenant. Here's my written estimate." |
| "What's the consistency model?" | Do you know *why* each state gets its model, not just that it does? | The per-state table *with the reject-line*: "I rejected eventual consistency on doc content because read-your-writes is user-visible; rejected strong consistency on the search index because it *adds* 200ms latency with zero user-visible correctness gain." |
| "What breaks if the network partitions?" | Can you *derive* the quorum math or is it memorized? | Say out loud: "N=3 ⇒ quorum 2. The 1-node side *cannot* commit. I *choose* that stall because the alternative — AP with diverged commits — loses the read-your-writes invariant." |
| "How do you scale writes?" | When does "read replicas" stop being the answer? | A written threshold: "I shard at ~500 tenants × 500 docs × active-write ratio above X, or when a *single tenant* exceeds 40% of one Postgres's write capacity. Before that, read replicas + better queries." |
| "What's your biggest tradeoff?" | Are you aware of your *over*-building, or are you just rationalizing it? | The *named* over-build: "In prod I'd run 1 node + 1 Postgres for this scale; the reason I'm not is the *learning objective.* Here's the doc line where I state it." |
| "Walk me through a decision." | Can you give the four-part structure *without notes* on a decision you *didn't* ADR? | Pick one off-menu (say, "why Jenkins not Argo CD as the primary author?") and narrate: decision / constraint / rejected alternative / revisit condition. |

> **The meta-skill, restated as a check:** an L6 *narrates the tradeoff, states the constraint, names the alternative, and gives the revisit condition.* That four-part structure — **decision / constraint / rejected alternative / revisit condition** — is the single most reusable thing in this document. **The *panel* is going to pick one of your non-ADR decisions and ask for the four-part structure on it.** Prepare at least three.

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
