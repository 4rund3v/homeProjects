# 07 — Redis: Cache and Job Queue

**Folder:** `07-redis-queue/`
**Milestone:** M3 (stateful foundations)

---

## Teach first: what Redis actually is

Redis is an in-memory data store that also happens to be a distributed key-value system with rich data types, pub/sub, and — critically for this project — a **job queue**.

### The two modes you'll actually use

| Mode | Data | Purpose |
|---|---|---|
| **Cache** | Ephemeral, TTL'd keys | Speed up repeated reads; hold session state |
| **Queue / Pub-Sub** | Messages | Decouple work from producers; run background jobs |

For Outline, Redis does both: it holds the session store and acts as a queue for background work (search indexing, notifications, image resizing).

### Why Redis and not Kafka

Redis is a **task queue**, not an event bus. It:
- **Consumes** messages (pop from queue; producer can't replay).
- Supports **priority queues** and **delayed execution**.
- Offers **blocking pop** (workers sleep until work appears).
- Guarantees **at-least-once** delivery by default (message is only removed after ack).

Kafka is for **log-centric, replayable, high-throughput** streaming. Redis is for **task-queue semantics**: *do this thing when you can.*

> **Tradeoff — Redis vs. Kafka/RabbitMQ.** For a system like Outline (a moderate-throughput app with background tasks), Redis is the right fit. Kafka adds operational weight and only pays off at much higher scale. RabbitMQ sits between — more sophisticated queues, less operational burden than Kafka. Don't choose by "which is more scalable"; choose by what your workloads *actually need*. For this project: Redis.

---

## Persistence: the surprise

"Redis is in-memory, so no persistence" is the wrong mental model. Redis has two persistence modes:

- **RDB snapshots** — periodic full snapshots to disk. Simple, coarse-grained recovery.
- **AOF (Append Only File)** — every write is logged; replay on startup. Finer-grained, slightly slower writes.

Redis can do both. For a **cache**, disable persistence (data is reproducible). For a **job queue**, you *must* enable AOF — otherwise killing the pod loses unprocessed jobs.

> **Failure mode — unprocessed jobs on crash.** Without AOF, a Redis restart loses all queued tasks. Workers wake up to find nothing; producers see jobs "done" that never ran. **For a queue, AOF is not optional.** For Outline, use `appendonly yes`.

---

## Memory management: eviction

Redis stores data in RAM. What happens when it's full?

- **`noeviction`** (default) — commands that would grow memory are refused. Predictable, safer for a queue.
- **`allkeys-lru`** — evict least-recently-used keys of any type. Best for a pure cache.
- **`volatile-lru`** — evict LRU *only among keys with a TTL*. Safe default for mixed use.
- **`allkeys-random` / `volatile-random`** — random eviction. Rarely what you want.

> **Threshold — always set `maxmemory` explicitly.** Without it, Redis uses whatever RAM is available and gets OOM-killed by the kernel — which is exactly the failure you can't observe in logs. Setting `maxmemory` gives you graceful degradation and makes the eviction policy actually do something.

> **Senior lens** — **for a queue, use `noeviction`.** Evicting a queued job is the same as dropping it silently. If memory pressure fills the queue, you want the *producer* to fail loudly, not the queue to quietly lose work. For a cache, `allkeys-lru` with `maxmemory` is the right shape.

---

## Deployment modes

| Mode | Description | Use for |
|---|---|---|
| **Standalone** | One Redis instance | Dev, low-stakes cache |
| **Master-Replica + Sentinel** | 1 primary, N replicas, Sentinels elect new primary on failure | General-purpose; typical prod |
| **Redis Cluster** | Sharded keyspace across N nodes | Very large datasets, horizontal scale |

For Outline: **master-replica with Sentinel** is overkill but instructive; a single primary + one replica (with a `statefulset` + a small sentinel) is enough. Redis Cluster is not worth it at this scale.

> **Tradeoff — HA vs. simplicity.** A single Redis instance is the cheapest and most debuggable. If it dies, the queue is dead and the session store is empty. Sentinel adds HA but adds three more processes and a quorum dance. Redis Cluster adds sharding but adds keyspace complexity and forbids some operations (multi-key commands, transactions with cross-shard keys). **Pick the least that survives your worst realistic failure.** For this project: Sentinel mode teaches the concept, Cluster doesn't pay off.

---

## Kubernetes-specific notes

Redis on k8s typically runs as a **StatefulSet** (per doc 06):

```yaml
kind: StatefulSet
spec:
  serviceName: redis
  replicas: 2
  volumeClaimTemplates:
  - metadata: { name: data }
    spec: { accessModes: [RWX], resources: { requests: { storage: 20Gi } } }
```

Two details:

- **Redis is *not* fundamentally stateful** — it can be rebuilt from a backup. It gets state only when you use it as a queue or with persistence.
- **RWX is important** for Redis because replication can move the primary. A single-writer RWO volume would work if the primary is pinned to one node, but Sentinel's failover may promote a pod on a different node.

> **Threshold — Redis AOF size.** AOF files grow forever unless `appendfsync everysec` is used with periodic `BGREWRITEAOF`. On a PVC without auto-expansion, a queue-heavy workload will eventually fill the volume. CNPG-style tooling (`redis-operator` or `redis-ha`) handles this; raw Redis doesn't.

---

## Bitnami Redis chart: what to configure

For this project, use the **Bitnami Redis chart** (`bitnami/redis`), which handles master/replica/sentinel/cluster topology via values:

```yaml
# values.yaml
architecture: replication        # master/replica/sentinel (vs. "cluster")
auth:
  enabled: true
  password: "changeme"           # Pattern B in practice: use existingSecret
persistence:
  enabled: true
  size: 20Gi
  storageClass: ""               # default; if you need RWX, name it explicitly
sentinel:
  enabled: true
  replicas: 3
master:
  persistence:
    enabled: true
  configmap: |                   # open map (see values-vs-configmap.md)
    appendonly yes
    maxmemory 1gb
    maxmemory-policy noeviction
```

> **Senior lens** — the `configmap` field here is an *open map* — the exact pattern discussed in `03-helm-packaging/values-vs-configmap.md`. Redis's `redis.conf` has hundreds of directives; making every one a values key would be absurd. Explicit for the 5-10 that matter (`maxmemory`, `appendonly`, `appendfsync`), open map for the rest.

---

## The workflow you'll live in

```
kubectl exec -it redis-master-0 -- redis-cli ping
kubectl exec -it redis-master-0 -- redis-cli info memory
kubectl exec -it redis-master-0 -- redis-cli info stats
kubectl exec -it redis-master-0 -- redis-cli llen outline:queue
kubectl exec -it redis-master-0 -- redis-cli brpop outline:queue 0
kubectl exec -it redis-sentinel-0 -- redis-cli -p 26379 sentinel master outline
```

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| Persistence | AOF for queues, `noeviction` policy |
| Memory | Always set `maxmemory`; monitor `used_memory` |
| Eviction policy | `noeviction` for queues, `allkeys-lru` for caches |
| Topology | Master + Sentinel for HA; Cluster only at large scale |
| Storage class | RWX for failover-capable setups |
| Config values | Explicit for 5-10 keys, open map for the long tail |

---

## Failure modes you must deliberately cause

1. **Fill memory past `maxmemory`** → see which policy engages (eviction vs. refusal).
2. **Kill the primary** → Sentinel promotes a replica; measure failover time.
3. **Restart a replica without persistence** → session store is empty; cache miss storm.
4. **Restart the primary *with* AOF** → verify queued jobs survive.
5. **Set `maxmemory-policy` to evict a queued job** → observe silent work loss (learn why `noeviction` for queues).

---

## Exit criteria (Redis part of M3)

- [ ] Redis running with AOF persistence and `maxmemory` set
- [ ] Sentinel enabled (3 sentinels) for HA; failover verified
- [ ] Outline connects; sessions persist across app restarts
- [ ] Queued jobs survive a Redis restart (AOF replay works)
- [ ] `used_memory` alerted; eviction policy understood and applied correctly

Next: `08-object-storage` — S3 for attachments and files.
