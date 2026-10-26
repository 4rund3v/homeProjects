# System Design Fundamentals

A mechanism-first curriculum for designing systems that remain correct, fast, available, operable, and affordable under real load and failure.

## Learning path

```text
Concurrency → Transactions → Distributed reasoning → Specialized indexes/search/media → Probabilistic scale → Capstone
```

Start with `00-foundations`. Each topic answers, in order:

1. **Why** does this problem exist?
2. **How** does the design solve it?
3. **Under the hood**, what data structures, state transitions, and failure semantics make it work?
4. **When** should a senior engineer choose it, reject it, or combine it with another technique?

## Domains

| Stage | Folder | Focus |
|---|---|---|
| 0 | [Foundations](00-foundations/README.md) | Concurrency, transactions, locking, inventory correctness |
| 1 | [Distributed systems](01-distributed-systems/README.md) | CAP/PACELC, consistency, failure, transactions, consensus |
| 2 | [Geospatial](02-geospatial/README.md) | Spatial indexes and map-serving architecture |
| 3 | [Search](03-search/README.md) | Inverted indexes, ranking, Elasticsearch, retrieval |
| 4 | [Media](04-media/README.md) | Chunking, transcoding, adaptive playback |
| 5 | [Probabilistic structures](05-probabilistic/README.md) | Memory-efficient approximate answers |
| — | [Shared reference](reference/README.md) | Capacity, latency, back-pressure, idempotency, observability |
| — | [Labs](labs/README.md) | Measurable experiments and fault injection |
| — | [Capstone](capstone/README.md) | Integrate the ideas into one production design |

## Coverage matrix

| README topic | Canonical lesson |
|---|---|
| Concurrency; concurrency fundamentals | [Concurrency fundamentals](00-foundations/concurrency-fundamentals/README.md) |
| Race conditions | [Race conditions](00-foundations/race-conditions/README.md) |
| Mutexes, semaphores, deadlocks | [Mutexes, semaphores, and deadlocks](00-foundations/mutexes-semaphores-deadlocks/README.md) |
| Distributed locks | [Distributed locks](00-foundations/distributed-locks/README.md) |
| Transactions; database transactions | [Transactions](00-foundations/transactions/README.md) |
| Database isolation levels | [Isolation levels](00-foundations/database-isolation-levels/README.md) |
| Database locking & concurrency | [Database locking](00-foundations/database-locking/README.md) |
| Pessimistic locking strategies | [Pessimistic locking](00-foundations/pessimistic-locking/README.md) |
| Optimistic locking patterns | [Optimistic locking](00-foundations/optimistic-locking/README.md) |
| Flash sale inventory patterns | [Flash-sale inventory](00-foundations/flash-sale-inventory/README.md) |
| Introduction to distributed systems | [Distributed systems](01-distributed-systems/introduction/README.md) |
| CAP; CAP (alias) | [CAP and PACELC](01-distributed-systems/cap-pacelc/README.md#cap) |
| PACELC; PACLEC (alias) | [CAP and PACELC](01-distributed-systems/cap-pacelc/README.md#pacelc) |
| Consistency models | [Consistency models](01-distributed-systems/consistency-models/README.md) |
| Distributed transactions | [Distributed transactions](01-distributed-systems/distributed-transactions/README.md) |
| Failure handling patterns | [Failure handling](01-distributed-systems/failure-handling/README.md) |
| Consensus; CONCENSUS ALGO (alias) | [Consensus](01-distributed-systems/consensus/README.md) |
| Geospatial search introduction | [Geospatial search](02-geospatial/geospatial-introduction/README.md) |
| Geohash | [Geohash](02-geospatial/geohash/README.md) |
| QuadTrees | [Quadtrees](02-geospatial/quadtrees/README.md) |
| H3 hexagonal hierarchical spatial index | [H3](02-geospatial/h3/README.md) |
| Space-filling curves and Hilbert’s curve | [Hilbert curves](02-geospatial/hilbert-curves/README.md) |
| Google’s S2 library | [S2](02-geospatial/s2/README.md) |
| Designing a map rendering service | [Map rendering](02-geospatial/map-rendering/README.md) |
| Choosing a spatial index | [Spatial index choice](02-geospatial/spatial-index-choice/README.md) |
| Inverted index fundamentals | [Inverted indexes](03-search/inverted-index/README.md) |
| TF-IDF scoring explained | [TF-IDF](03-search/tf-idf/README.md) |
| BM25 and parameter tuning | [BM25](03-search/bm25/README.md) |
| Elasticsearch architecture essentials | [Elasticsearch](03-search/elasticsearch/README.md) |
| Advanced search patterns | [Advanced search](03-search/advanced-search/README.md) |
| Video transcoding and playback | [Video systems](04-media/video-transcoding/README.md) |
| File chunking | [File chunking](04-media/file-chunking/README.md) |
| Probabilistic data structures; overview | [Probabilistic structures](05-probabilistic/probabilistic-overview/README.md) |
| Bloom filters 1/2 | [Bloom filters](05-probabilistic/bloom-filters/README.md) |
| Count-Min Sketch 1/2 | [Count-Min Sketch](05-probabilistic/count-min-sketch/README.md) |
| HyperLogLog 1/2 | [HyperLogLog](05-probabilistic/hyperloglog/README.md) |

## Senior engineer quality bar

For every design, quantify workload and SLOs; state correctness invariants; identify the source of truth; model retries, timeouts, partitions, overload, and recovery; choose consistency deliberately; expose useful metrics; and account for cost and security. A diagram without those decisions is not a design.

## Suggested order

Read each domain README, then its topic `README.md`, `information.md`, and ordered `learn/` lessons. Run a lab before moving on. Finish with the [capstone](capstone/README.md) and review it using the [design checklist](design-review-checklist.md).
