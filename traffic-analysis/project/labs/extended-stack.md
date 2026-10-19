# Lab: the extended stack, measured end to end

The base labs (`baseline`, `break-the-system`) measure the *minimum* stack. This lab measures the *extended* stack (mesh + cache + queue) and reads the *three* latency shapes (`project/01b-data-path`) off the panels.

## Prereqs

- The full extended stack running: MetalLB → NGINX → Envoy → app → (Redis | Postgres | Kafka).
- `redis_exporter`, the mesh's Envoy metrics, and the `kafka_exporter` all scraped.
- `k6` on the host, plus the producer script.

## The three shapes, in one run

Drive a *synchronous* load (the `/api/products` path: cache + DB) at 200 VU for 60 s. Simultaneously, drive a *producer* into the `orders` topic at 500 msg/s for the same 60 s.

Read the *three* shapes off the *three* subsystems:

### Shape 1 — the cache (synchronous, bimodal)

```
redis_keyspace_hits / (redis_keyspace_hits + redis_keyspace_misses)   # hit ratio
histogram_quantile(0.95, ...app...)                                    # app p95 (the fast mode)
histogram_quantile(0.99, ...app...)                                    # app p99 (the slow mode)
```

The p95 and p99 are *far apart* because the distribution is *bimodal* (fast hits, slow misses). That gap is the *cache's* contribution to the tail. If the gap is *small*, the cache is not doing its job (everything is a miss) or the *hit* is slow (a big value).

### Shape 2 — the mesh (the masked retry)

```
envoy_cluster_upstream_rq_retry        # the tell
envoy_cluster_upstream_rq_time         # the request time, as the sidecar sees it
envoy_cluster_upstream_cx_reuse        # the connection-reuse rate
```

At steady load, `rq_retry` should be ~0 and `cx_reuse` should be *high* (connections are reused). If `rq_retry` is *climbing* while the app p99 is *flat*, the mesh is *masking* a flapping upstream (`load-balancing/05`). If `cx_reuse` is *low*, the mesh is *churning* connections — a *mesh-level* pool, a second pool in the stack.

### Shape 3 — the queue (the invisible wait)

```
kafka_consumergroup_lag{group="shop"}                        # the queue depth
rate(kafka_consumergroup_lag{group="shop"}[5m])              # the climb (the incident)
histogram_quantile(0.99, ...consumer processing...)          # the *work*, not the *wait*
```

At 500 msg/s the lag is *flat at 0* (the consumer keeps up). The *consumer p99* is the *work*; the *queue wait* is ~0 (the lag is 0). Raise the producer to 3000 msg/s and the lag *climbs*; the *consumer p99* stays *flat* (the work is unchanged) while the *queue wait* is *unbounded*. **The consumer p99 does not show the queue. The lag does.**

## The cross-shape read

The *three* shapes are *independent* subsystems, but they *interact*:

1. **Cache down → DB pool pins.** The cache failure *shifts* the synchronous load onto the DB (`database-latency/05`). The DB pool is the *victim*.
2. **Mesh retry storm → upstream overload.** The mesh *amplifies* a flaky upstream (`load-balancing/05`). The *upstream* is the victim.
3. **Queue lag climbing → producer backpressure.** The *producer* should *throttle* when the lag climbs (the *consumer* is the limit). Without backpressure, the *producer* keeps producing, the lag *caps* at retention, and the *oldest* messages are *dropped*.

The senior-engineer habit: **when one shape's panel goes red, the *next* panel you look at is the *victim's*, not the *trigger's*.** The trigger is the *symptom*; the victim is the *damage*.

## The combined dashboard

One row per shape:

```json
{
  "rows": [
    { "title": "Cache (bimodal)",
      "panels": [
        {"title": "Hit ratio", "targets": [{"expr": "redis_keyspace_hits / (redis_keyspace_hits + redis_keyspace_misses)"}]},
        {"title": "App p95 / p99 (the two modes)", "targets": [
          {"expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint))", "legendFormat": "p95"},
          {"expr": "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint))", "legendFormat": "p99"}
        ]}
      ]
    },
    { "title": "Mesh (masked retries)",
      "panels": [
        {"title": "Retries (the tell)", "targets": [{"expr": "sum(rate(envoy_cluster_upstream_rq_retry[1m]))"}]},
        {"title": "Conn reuse", "targets": [{"expr": "sum(rate(envoy_cluster_upstream_cx_reuse[1m])) / sum(rate(envoy_cluster_upstream_cq_total[1m]))"}]}
      ]
    },
    { "title": "Queue (the invisible wait)",
      "panels": [
        {"title": "Consumer lag", "targets": [{"expr": "kafka_consumergroup_lag{group=\"shop\"}"}]},
        {"title": "Lag climb (the incident)", "targets": [{"expr": "sum(rate(kafka_consumergroup_lag{group=\"shop\"}[5m]))"}]}
      ]
    }
  ]
}
```

Read the *three* rows in one pass. A *real* incident is *usually* one row going red, with the *victim* row (the *next* one in the interaction) going red *soon after*. The *sequence* (which row moved *first*) is the *diagnosis*.

## The question that ties it together

At 3000 msg/s producer and 200 VU synchronous load, *which* row goes red *first*, and *which* is the *victim*?

(A: the *queue* row goes red *first* (the lag climbs at 3000 > 500 ceiling). The *synchronous* row is the *victim* *only if* the cache or DB is *shared* with the consumer. If the consumer and the sync path share a DB pool, the *queue*'s load *competes* with the *sync* path for the pool, and the *sync* p99 *climbs* *because of the queue*. The *sequence* (queue first, sync after) is the *root-cause* ordering.)
