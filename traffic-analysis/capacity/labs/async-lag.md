# Lab: drive the producer rate, find the async knee, find the straggler

## Prereqs

- The extended stack: a Kafka topic `orders`, one consumer group `shop` with *two* consumers, *four* partitions.
- A producer you can throttle (the `k6` producer script in `capacity/examples/k6-produce.js`).
- The `kafka_exporter` metrics visible: `kafka_consumergroup_lag`, `kafka_consumergroup_lag{partition=...}`.

## Step 1 — the producer rate

Drive the producer at 500 msg/s, held for 60 s. Record:

| Metric | 500 msg/s |
|---|---|
| `kafka_consumergroup_lag` (group) | 0 (steady) |
| Per-partition lag (4 partitions) | 0 / 0 / 0 / 0 |
| Consumer p99 (work time) | ~20 ms |
| `rate(kafka_consumergroup_committed[1m])` | ~500 msg/s (keeping up) |

The consumer *keeps up*. The produce rate (500) equals the consume rate (~500). The lag is *flat at zero*.

## Step 2 — raise the producer to 3000 msg/s

The consumer's *per-message* work is ~20 ms. Its *throughput ceiling* is roughly `1 consumer × (1000 ms / 20 ms)` = ~50 msg/s *per partition*... but with 4 partitions and 2 consumers, the group can drain ~`4 partitions × (1000/20)` = ~200 msg/s *if* the work is *fully parallel across partitions*. In practice it is higher. The *knee* is somewhere between 500 and 3000.

Record at 3000 msg/s:

| Metric | 3000 msg/s |
|---|---|
| `kafka_consumergroup_lag` (group) | *climbing* (100, 400, 1200, ...) |
| Per-partition lag | 300 / 300 / 400 / 400 (uneven!) |
| Consumer p99 | ~20 ms (the *work* is unchanged) |
| `rate(...committed)` | *flattens* at the consumer's ceiling (~200–500 msg/s) |

The *produce* rate (3000) exceeds the *consume* ceiling. The lag *climbs*. **This is the async knee.** The producer is 3000; the consumer can only drain ~500; the gap (~2500 msg/s) is the *rate the lag grows*.

## Step 3 — the *straggler*

Look at the *per-partition* lag. It is *uneven*: partitions 0 and 1 are at 300, partitions 2 and 3 are at 400. That *unevenness* is the straggler signature: one consumer (the one owning partitions 2 and 3) is *slower* than the other.

The *group* lag (the average) says "we are behind." The *per-partition* lag says "*which* consumer is the problem." The senior engineer's habit: **never read the group lag alone. Read the per-partition lag. The straggler is the *max*, not the *mean*.**

## Step 4 — the Little's-law check

```
# The consumer's steady-state ceiling, per the lab
W_consumer = 20 ms/message
λ_max      = 1 / 0.020 = 50 msg/s   (per consumer, single-threaded)
Group (2 consumers) = ~100 msg/s  *if fully independent*
```

The *measured* consume ceiling (~500 msg/s) is *higher* than the naive Little's-law prediction (~100). Why? Because the consumer is *not* single-threaded — it has a worker pool, and the work is *batched*. The *effective* `W` is lower than the *per-message* p99, because the consumer processes in *batches*. **The Little's-law `W` is the *mean* time *per message including batch overhead*, not the per-message p99.** Use the *mean*, not the p99, in Little's law.

## Step 5 — the *queue wait* is the invisible number

At 3000 msg/s with a *climbing* lag, the *end-to-end* latency of a message is:

```
e2e = producer_ack (~5 ms) + queue_wait (growing) + consumer_time (~20 ms)
```

The *queue_wait* is *not measured* — it is the *lag-driven* component. A message produced *now* waits *longer* than one produced a minute ago, because the lag grew in the interim. The *e2e p99* is *unbounded* while the lag climbs. The *consumer p99* (20 ms) *does not show it*. **The consumer p99 is the *work*; the lag is the *wait*. Two different numbers. The wait is the one that is *blowing up*.**

## Restore

Stop the producer. The lag *drains* (the consumer keeps working at its ceiling until the queue is empty). The lag *decays* to 0. The *shape* of the decay is the *consume rate* — it drains at ~500 msg/s, not instantaneously.

```
# Watch the drain
kafka_consumergroup_lag  # 1200 → 900 → 500 → 0, at the consumer's ceiling
```

## Follow-up questions

- The lag is *steady* at 1000 (not climbing). Is that an incident? (A *steady* lag is *bad but stable* — the system is *behind but keeping up*. The *climbing* lag is the incident. A steady lag means the consumer and producer rates are *equal*; the system is *operating* at a fixed delay. The *climbing* lag means the producer is *faster*; the delay is *growing*. The *alert* is on the *climb*, not the *level*.)
- You scale the *consumer group* from 2 to 8 consumers (with 4 partitions). Does the lag drain faster? (No. With *more consumers than partitions*, the extra consumers are *idle* (a partition can only be owned by one consumer at a time). The ceiling is set by the *partition count* × the *per-partition* throughput. Scaling consumers past the partition count does *nothing*. The *knee* is the *partition* count, not the consumer count. To raise the ceiling, add *partitions*.)
- The producer rate is 3000, the consumer ceiling is 500, the lag is *climbing* at 2500 msg/s. How long until the lag is 100,000 messages? (`100000 / 2500 = 40 s.`) At what point does the *disk* fill up (Kafka's retention)? (The *retention* is the *real* bound. If the topic's retention is 100,000 messages, the lag *caps* at 100,000 and the *oldest* messages are *dropped* (or the producer is *throttled*). The *disk* is the *ultimate* queue. See `capacity/03`.)
