# Architecture

> How the pieces fit together: the system shape, the request lifecycle end-to-end,
> the async flow, and the deployment topology. This is the map; the domain reasoning
> is in [`domain-decomposition.md`](domain-decomposition.md) and the component
> details are in their own guides.

---

## 1. System at a glance

```
                        ┌─────────────────────────────────────────────┐
                        │              Tailscale VPN                  │
                        │        (private access to the node)         │
                        └───────────────────────┬─────────────────────┘
                                                │
                        ┌───────────────────────▼─────────────────────┐
                        │           NGINX Ingress (k3s)               │
                        │   TLS · load balancing · rate limiting      │
                        └───────────┬─────────────────────┬───────────┘
                                    │                     │
                        ┌───────────▼──────────┐  ┌───────▼────────────┐
                        │   React UI (static)  │  │  Django / DRF API  │
                        │   LLM-generated SPA  │  │  (JWT, OpenAPI)    │
                        └──────────────────────┘  └───────┬────────────┘
                                                           │
                              ┌────────────────────────────┼───────────────┐
                              │                            │               │
                     ┌────────▼────────┐        ┌──────────▼─────────┐ ┌───▼──────────┐
                     │  PgBouncer      │        │  Kafka (KRaft)     │ │ Schema       │
                     │  (conn pooling) │        │  + Schema Registry │ │ Registry     │
                     └────────┬────────┘        └──────────┬─────────┘ └──────────────┘
                              │                            │
                     ┌────────▼────────┐        ┌──────────▼─────────┐
                     │  PostgreSQL     │        │  Kafka Consumer    │
                     │  (hot + warm)   │        │  (loan updater)    │
                     └────────┬────────┘        └──────────┬─────────┘
                              │                           │
                     ┌────────▼────────┐        ┌──────────▼─────────┐
                     │  PVC archive    │        │  updates loan      │
                     │  (cold events)  │        │  balances (PG)     │
                     └─────────────────┘        └────────────────────┘

                     Observability: Datadog agent + postgres_exporter +
                     Kafka exporters → dashboards & alerts
```

**Read it as four planes:**
- **Edge plane** — Tailscale + NGINX: who can reach the system, TLS, rate limits.
- **Serving plane** — React UI + DRF API: the synchronous request path.
- **Data plane** — Postgres (+PgBouncer), Kafka (+registry): storage and streaming.
- **Async plane** — the Kafka consumer: the background loan-update path.
- **Observability plane** — spans all four (drawn separately in
  [`observability.md`](observability.md)).

---

## 2. The synchronous path (record an expense)

The happy path for `POST /expenses/`:

```
1. SPA → NGINX → DRF API   (Authorization: Bearer <JWT>)
2. DRF authenticates the JWT → request.user          [drf-jwt-guide.md]
3. Permission + object ownership checked             [drf-jwt-guide.md §5]
4. Serializer validates the input shape
5. View calls ExpenseService.record(user, dto)       [domain-decomposition.md]
6. Service, in ONE Postgres transaction:
     a. build the Money value object (validate currency, positive)
     b. INSERT the expense
     c. INSERT an outbox row (the ExpenseRecorded event, unsent)   [event-flows.md]
     d. COMMIT — expense and outbox are atomic
7. Service returns the expense; serializer shapes the response
8. Response → SPA (202/201; loan balance NOT yet updated — documented async)
```

**The critical property:** step 6 is one transaction. The expense and its event are
atomic. There is no window where the expense exists without its event, or the event
exists without its expense. This is the transactional outbox
([`event-flows.md`](event-flows.md), [`kafka-guide.md`](kafka-guide.md) §4).

**What the API does NOT do:** it does not update the loan balance synchronously. The
response says "expense recorded and queued," and the contract documents the
eventual-consistency window ([`api-contracts-guide.md`](api-contracts-guide.md) §5).

---

## 3. The asynchronous path (update the loan)

Two actors, decoupled by the event:

```
Outbox relay (producer):
  1. poll the outbox table for unsent rows
  2. serialize each to Avro against the registered schema      [avro-guide.md]
  3. publish to the topic, keyed by loan_id, acks=all          [kafka-guide.md]
  4. mark the outbox row sent (after Kafka acks)
  → this is a separate process/deployment from the API

Consumer (loan updater):
  1. consume from the topic (consumer group), keyed ordering by loan_id
  2. deserialize via the schema registry                        [avro-guide.md]
  3. idempotency check: has event_id been applied? (unique constraint)
  4. in ONE transaction: INSERT the balance change + UPDATE loan.outstanding
  5. commit the Kafka offset AFTER the DB commit               [kafka-guide.md §3]
```

**The ordering guarantee:** keying by `loan_id` means all events for a loan are on one
partition, consumed in order → balance changes applied in order
([`kafka-guide.md`](kafka-guide.md) §2). **The durability guarantee:** offset is
committed after the DB write, so a crash reprocesses → at-least-once → made safe by
the `event_id` idempotency key.

**The decoupling:** the API doesn't know the consumer exists; the consumer doesn't
know how expenses are validated. They meet only at the Avro contract. That's what
makes each independently deployable and testable — the boundary from
[`domain-decomposition.md`](domain-decomposition.md) §4.

---

## 4. The read path (dashboards / reports)

Reporting reads from Postgres, not from Kafka:

- **Spend by category/source over time** — aggregate queries over the expenses table,
  backed by the indexes from [`postgres-guide.md`](postgres-guide.md) §3.
- **Current loan balances** — read the loan table (the projection maintained by the
  consumer).
- **Historical analysis** — query the archived Parquet if it goes back beyond the warm
  window ([`data-lifecycle.md`](data-lifecycle.md)).
- **Kafka health** (lag, throughput, ingress/egress, latency) — read from Kafka
  metrics, not the DB ([`observability.md`](observability.md)).

**Rule:** the read path reads *projections* (tables maintained by the write path), not
raw event streams. Don't make a dashboard consume Kafka.

---

## 5. Deployment topology (k3s)

All of the above runs on your single k3s node, reachable over Tailscale
([`infrastructure.md`](infrastructure.md)):

- **Namespaces** — separate `app`, `data` (Postgres/Kafka), `ingress`, `observability`.
  Isolation and clean RBAC even on one node.
- **Workloads as Deployments** — API (replicas behind the service), consumer
  (replicas ≤ partition count), outbox relay.
- **Statefulsets** — Postgres, Kafka (with PVCs for data; PVCs also back archival).
- **Ingress** — NGINX ingress controller with TLS, load balancing, rate limiting.
- **Helm** — each component packaged as a chart, values-parameterized per environment.
- **Terraform** — provisions the node/cluster and installs the Helm releases
  reproducibly.
- **CronJobs** — the archival/lifecycle automation ([`data-lifecycle.md`](data-lifecycle.md) §4).

**The single-node caveat you must internalize:** replication factor for Kafka and
Postgres HA don't really work on one node. Learn the production shapes (RF=3, Postgres
replicas) but accept that local k3s is a *learning* topology — a node loss loses data.
Document this; don't pretend it's production.

---

## 6. The boundaries that matter (summary)

Each boundary is a place you can change one side without touching the other. These are
the load-bearing walls:

| Boundary | Enforced by | Why it matters |
|----------|-------------|----------------|
| UI ↔ API | OpenAPI contract + generated client | UI is disposable; contract is stable |
| API ↔ domain logic | thin views, services own rules | testable without HTTP |
| API ↔ Kafka | transactional outbox | atomic expense+event |
| Producer ↔ consumer | Avro schema + registry | independent evolution |
| Kafka ↔ Postgres (consumer) | idempotency key | safe at-least-once |
| App ↔ infra | container image tags | deploy decoupled from source |
| Hot ↔ cold data | partitioning + archival policy | bounded growth, cheap history |

If you protect these boundaries, the system stays comprehensible as it grows. If you
erode them (UI importing backend types, views containing business rules, API writing
loan balances directly), every later phase gets harder.

---

## 7. Cross-references

- Entities & boundaries: [`domain-decomposition.md`](domain-decomposition.md)
- Auth pipeline: [`drf-jwt-guide.md`](drf-jwt-guide.md)
- The outbox + consumer flow in detail: [`event-flows.md`](event-flows.md)
- Topics/keys/retention: [`kafka-guide.md`](kafka-guide.md)
- Event contracts: [`avro-guide.md`](avro-guide.md)
- Schema/tuning/observability: [`postgres-guide.md`](postgres-guide.md)
- Tiers/archival/rebuild: [`data-lifecycle.md`](data-lifecycle.md)
- Deploy details: [`infrastructure.md`](infrastructure.md)
- Dashboards/alerts: [`observability.md`](observability.md)
