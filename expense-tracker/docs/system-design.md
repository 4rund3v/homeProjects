# System Design

> **Deep-dive versions live in [`system-design/`](system-design/)** — one doc each for
> scalability, reliability, consistency (CAP/PACELC), latency/throughput, and the
> "design a system" worksheet, with worked examples and the L5/L6 framing. This file
> is the one-page overview / index. Read the folder for depth.
>
> The cross-cutting concepts that sit *under* the architecture and OOP decisions:
> **scalability, reliability, consistency, availability, latency, back-pressure, and
> the trade-offs between them.** Each tied to a concrete choice in this project.
> Patterns are in [`architecture-patterns.md`](architecture-patterns.md) and
> [`design-patterns.md`](design-patterns.md); the system itself is in
> [`architecture.md`](architecture.md).

---

## How to read this

System design is the discipline of **naming trade-offs before you're forced into them**.
Almost every concept below is a *dial*, not a switch — you set it somewhere, and the
skill is knowing what you're trading away. For each concept: what it is, where the dial
sits in this project, and the cost of the setting.

---

## Scalability

**The question:** what happens when load grows?

**Three axes:**
- **Vertical (scale up)** — bigger machine. Simplest; has a ceiling. **Your default
  here** — a single k3s node scales up before anything else.
- **Horizontal (scale out)** — more instances. Needs statelessness and shared state.
  Your API can scale out (stateless behind NGINX, [`infrastructure.md`](infrastructure.md)
  §5); Postgres does not scale out trivially.
- **Functional (split)** — decompose so parts scale independently. The consumer scales
  independently of the API; later, reporting could split from the write path (light CQRS,
  [`architecture-patterns.md`](architecture-patterns.md)).

**Where the real limits are in this system:**
- **Kafka consumer throughput** is bounded by **partition count** — you can't run more
  consumers than partitions ([`kafka-guide.md`](kafka-guide.md) §7). This is why the
  partition-count decision ([`kafka-guide.md`](kafka-guide.md) §5) is a scaling decision,
  not just a config detail.
- **Postgres** is the write bottleneck for a single node; the answer at scale is
  replicas (read scaling) and then partitioning/sharding — both deferred and documented
  as deferred ([`infrastructure.md`](infrastructure.md) §3 single-node caveat).
- **The single node** caps everything. Learn horizontal patterns; run vertical; document
  the gap.

**The discipline:** scale the thing that's measurably the bottleneck, one at a time.
"Add replicas" before you've seen CPU/connections/lag climb is guessing.

---

## Reliability

**The question:** does it keep working correctly when things fail?

**Reliability is built from small decisions, each addressing a specific failure:**

| Failure | The reliability mechanism here |
|---------|-------------------------------|
| API crashes after commit | nothing needed — it's committed ([`event-flows.md`](event-flows.md) §5) |
| Kafka down | transactional outbox queues; relay catches up |
| Relay crashes mid-publish | duplicate event → idempotent consumer absorbs it |
| Consumer crashes mid-event | offset committed after DB write → reprocessed safely |
| Poison message | dead-letter topic + alert |
| Loan balance drift | reconciliation + rebuild-from-events |
| Old data growth | partitioning + archival ([`data-lifecycle.md`](data-lifecycle.md)) |
| Bad deploy | Helm rollback ([`infrastructure.md`](infrastructure.md) §4) |
| Node loss | **not handled on one node** — backups + documented caveat |

**The principle:** *make failures cheap and recoverable, not impossible.* You cannot
prevent crashes; you make them harmless. Every row in that table is a decision to
*fail safely* rather than *never fail*.

**MTBF vs MTTR:** you can't drive mean-time-between-failures to zero, so drive
**mean-time-to-recovery** down — that's what runbooks ([`runbooks.md`](runbooks.md)) and
rollbacks are for. Reliability engineering is mostly about fast, practiced recovery.

---

## Consistency

**The question:** when a reader looks, do they see the latest write?

**Models, strongest to weakest:**
- **Linearizable** — every read sees the latest write. Strongest, most expensive.
- **Sequential** — operations appear in some order consistent with real time.
- **Causal** — cause precedes effect.
- **Eventual** — reads converge to the latest write *given no new writes and enough
  time*.

**Where this system sits — and why it's a deliberate choice:**
- **Within Postgres:** strong consistency. The expense insert + outbox write are one
  transaction; the balance change + outstanding update are one transaction
  ([`event-flows.md`](event-flows.md)).
- **Across the async boundary:** **eventual consistency**. After `POST /expenses/`, the
  loan balance updates a moment later. This is the trade you make for a decoupled,
  resilient pipeline — and it **must be documented in the API contract**
  ([`api-contracts-guide.md`](api-contracts-guide.md) §5), not hidden.

**The ordering guarantee that makes eventual consistency safe:** keying by `loan_id`
means balance changes apply *in order* ([`kafka-guide.md`](kafka-guide.md) §2).
Eventual + ordered + idempotent = correct, just not instant. That combination is the
heart of the design.

**The discipline:** know exactly where your consistency boundary is, and never promise
stronger consistency than you deliver. "Expense recorded, balance updating" is honest;
"done" is not.

---

## Availability

**The question:** what fraction of the time does the system respond correctly?

**The tension with consistency:** under network issues, you often can't have both — this
is CAP. Availability is usually expressed in "nines" (99.9% ≈ 8.7h downtime/year).

**Here:** on a single node, availability is fundamentally limited — a node loss is an
outage ([`infrastructure.md`](infrastructure.md) §3). The honest posture:
- **Maximize availability of the write path** — the API keeps accepting expenses even
  when Kafka is down (outbox absorbs it), which is a real availability win from the
  architecture.
- **Accept low availability of the box** — it's a learning environment; document it.
- **Design for higher availability** you don't yet run — replicas, RF=3 — so the path
  exists when you need it.

---

## CAP theorem (and why it's usually misquoted)

**The real statement:** when a **network partition** occurs, a distributed system must
choose between **consistency** and **availability** *for the duration of the partition*.
(The "P" — partition tolerance — isn't optional in a distributed system; the choice is
C vs A *during* a partition.)

**Applied here:**
- **Kafka under partition:** brokers choose availability for produce/consume with
  `min.insync.replicas` tuning — you can favor not-losing-data (consistency, higher
  `min.insync.replicas`) or not-blocking (availability). On one node this is moot; in
  prod it's a real dial.
- **Your async boundary:** you chose **availability** — the API stays up when Kafka is
  down — and accepted **eventual consistency** for the balance. That's a CAP-flavored
  trade made explicit.

**The discipline:** stop saying "CAP means pick two." Say "during a partition, I favor
___ over ___, and here's the consequence." That's the useful version.

---

## PACELC (the more complete framing)

CAP only describes behavior *during* a partition. **PACELC** adds: **else** (normal
operation), there's a **latency vs consistency** trade too.

- *If* **P**artition: choose **A**vailability or **C**onsistency.
- **E**lse (normal): trade **L**atency for **C**onsistency.

**Here:** in normal operation you trade a little latency (the async hop through Kafka)
for decoupled consistency — the balance is briefly stale. PACELC names that everyday
trade that CAP ignores. It's the more honest lens for most systems, including this one.

---

## Latency

**The question:** how long from request to useful response?

**Budget the async path** ([`observability.md`](observability.md) §5):
- **API response** — synchronous; keep it fast. This is why publishing is *queued*
  (outbox), not done inline — the API never waits on Kafka.
- **Produce latency** — relay → broker ack.
- **Consume/processing latency** — consumer's work per event.
- **End-to-end** — expense recorded → loan balance updated. This is what the user
  actually feels; measure it with the envelope's `produced_at` timestamp.

**Percentiles, not averages:** p99 is what users feel; the mean hides the tail. Alert on
p99 latency, never the average ([`observability.md`](observability.md) §3).

**The discipline:** set a latency *budget* per path, measure percentiles, and know which
hop is yours to optimize. Don't optimize the mean.

---

## Throughput

**The question:** how much work per unit time?

**Bounded by:**
- **Ingress** (produce rate) vs **egress** (consume rate) — the gap is lag
  ([`observability.md`](observability.md) §5).
- **Consumer parallelism** ≤ partition count.
- **Postgres write throughput** on the node.
- **PgBouncer** connection limits ([`postgres-guide.md`](postgres-guide.md) §4).

**The relationship to latency:** pushing throughput up (batching, more consumers)
usually trades against latency and ordering guarantees. Know which you're optimizing.

---

## Back-pressure

**The question:** when a consumer can't keep up, what happens — does the system buffer
infinitely, drop, or push back?

**In this system:**
- **The outbox is a back-pressure buffer** — if Kafka is slow, events queue durably in
  Postgres rather than blocking the API or being dropped. This is the *good* kind of
  back-pressure: durable, observable (outbox depth), and bounded by disk.
- **Consumer lag is the signal** — rising lag means egress < ingress and the buffer
  (Kafka retention) will eventually overflow. Alert on lag
  ([`observability.md`](observability.md) §5).
- **Retention is the overflow policy** — if consumers fall behind past retention,
  messages expire and are lost. So retention must exceed your worst-case reprocessing
  window ([`kafka-guide.md`](kafka-guide.md) §6).

**The discipline:** every unbounded queue is a future incident. Make buffers durable,
bounded, and *observable* — which is exactly what outbox + lag + retention give you.

---

## Idempotency (the reliability keystone)

**The question:** is it safe to do the same thing twice?

**Why it's central:** at-least-once delivery guarantees duplicates
([`kafka-guide.md`](kafka-guide.md) §3), so every operation that can be retried must be
idempotent.

**Here:**
- **Consumer:** `event_id` unique constraint → applying twice is a no-op
  ([`event-flows.md`](event-flows.md) §3).
- **API creates:** an idempotency key on `POST /expenses/` lets a client retry safely
  ([`api-contracts-guide.md`](api-contracts-guide.md) §2) — decide whether you need it.
- **Archival:** verify-before-drop is idempotent in effect — a re-run doesn't double-drop
  ([`data-lifecycle.md`](data-lifecycle.md) §3).

**The principle:** *design for retries, then make retries safe.* Idempotency is what
turns "at-least-once" from a liability into a feature (safe replay = free disaster
recovery).

---

## Coupling & cohesion

**The question:** how much does changing one part force changes elsewhere, and how
strongly do related things belong together?

**Here — this is what the boundaries buy**
([`architecture.md`](architecture.md) §6): the UI↔API contract, the outbox seam, the
Avro contract, and the idempotency key are all *decoupling points*. Each lets one side
change without the other.

**Cohesion** is the other half: everything about "expenses" belongs together
([`project-structure-guide.md`](project-structure-guide.md) §2). High cohesion + low
coupling = a system you can change one part of at a time.

---

## Observability as a design input

Not an afterthought — a design constraint. You can't operate what you can't see, so the
system is designed to be observable:
- **Correlation ID** in the event envelope ([`avro-guide.md`](avro-guide.md) §3) so one
  expense is traceable across the async boundary.
- **Outbox depth** as a first-class metric ([`observability.md`](observability.md) §3).
- **Reconciliation** as a continuous correctness check
  ([`data-lifecycle.md`](data-lifecycle.md) §5).

Design the signals *with* the system, not after.

---

## The trade-off map (one table)

| Dial | Toward one end | Toward the other | Where you set it here |
|------|----------------|------------------|-----------------------|
| Consistency ↔ Availability | strong, blocking | eventual, available | eventual across async; strong in DB |
| Latency ↔ Throughput | fast, low batch | high batch | fast API (queued publish); batch the relay |
| Durability ↔ Speed | `acks=all`, sync commit | `acks=1`, async | durability for financial events |
| Simplicity ↔ Flexibility | concrete, simple | abstract, pluggable | simple first; abstract on the 2nd case |
| Scaling up ↔ out | vertical | horizontal | vertical now; horizontal-ready API |
| Cost ↔ Retention | short retention | long retention | retention > reprocessing window |

**The meta-skill:** for each row, know where you've set the dial and *why*. If you can't
say why, you've set it by accident.

---

## Checkpoint questions

- Where is your system **eventually consistent**, and is that documented in the
  contract?
- What makes the write path **available even when Kafka is down**, and what's the cost?
- Name a dial you set toward **durability** and one toward **speed**, with the reason.
- What is your **back-pressure buffer**, and how do you observe it filling?
- Why must **Kafka retention exceed the reprocessing window**?
- Which scaling axis is your **current bottleneck**, and how do you know?

---

## Decisions to record in `design.md`

- The consistency posture per path (strong in DB, eventual across async) and how it's
  communicated.
- The availability posture and the documented single-node limitation.
- The durability settings chosen (`acks`, `synchronous_commit`) and their cost.
- The back-pressure design (outbox) and its observability (depth/age alerts).
- The scaling axis you'd hit first, and the plan for it.
