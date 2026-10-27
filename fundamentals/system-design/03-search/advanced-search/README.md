# Advanced search patterns

[Back](../../README.md)

## Why

A single lexical score is not enough for production search. Users misspell, use synonyms, expect filters, and care about freshness, location, popularity, and authorization.

## How

Use staged retrieval:

```text
query parse → lexical candidate retrieval → filters → geo/business features → rerank top K → response
```

Keep candidate generation broad enough for recall. Rerank only a bounded top K so expensive features do not dominate latency.

## Under the hood

### Filters versus scoring

A filter answers a boolean question and can be cached. A scoring clause changes rank and must run for candidates. Move exact constraints into filters.

### Synonyms and analyzers

Tokenization, normalization, stemming, synonyms, and language-specific analyzers alter the index. Analyzer changes usually require reindexing; version analyzer configuration with the index.

### Prefix and autocomplete

Use edge n-grams, prefix indexes, or a completion structure. Keep autocomplete separate from full-document ranking because its latency and query distribution differ.

### Hybrid retrieval

Combine BM25 with vector similarity or business signals. Normalize component scores before blending; raw scores have different scales. Evaluate recall, relevance, freshness, and fairness separately.

### Security filtering

Apply authorization filters before returning candidates. Do not rely on post-processing after top-K: unauthorized documents can displace authorized results and leak counts or snippets.

## Production use cases

Marketplace search, nearby commerce, enterprise document retrieval, typeahead, and log exploration.

## Observability

Zero-result rate, click-through by query class, p95/p99 latency, candidate count, rerank cost, index freshness, and unauthorized-result tests.

## Lab

Build a two-stage search. Compare BM25 top 10 with BM25 plus freshness and distance features. Measure relevance and p95 latency; then add an authorization filter and test adversarial queries.

## Worked examples

**Situation: p95 SLO = 100 ms, two-stage search.**
```text
BM25 top 100:       20 ms
feature fetch ×100: 0.5 ms × 100 = 50 ms sequential
                    10 ms parallel (10 fetchers)
blend + sort:        5 ms
```
Sequential: 20 + 50 + 5 = 75 ms ✓
Parallel:  20 + 10 + 5 = 35 ms ✓

At 5,000 qps: 5,000 × 35 ms = 175 s/s of CPU for parallel fetch. 10 fetchers × 5,000 qps = 50,000 concurrent fetches. Each feature store must sustain 50,000 reads/second. If the feature store's p99 is 5 ms, 50,000 × 5 ms = 250 s/s of feature-store time — 2.5× the 100 ms SLO. The feature store is the bottleneck. Reduce top-K to 50: 5,000 × 10 ms × 50/100 = 2,500 s/s → inside SLO.

Security filter before top-K: 1,000 candidate docs → 5 authorized → rank within 5. Without pre-filter: rank 1,000, take top 5, return. The user sees the 5 most-relevant *of the 1,000* — leaking that 995 docs exist and are less relevant.

```text
top 100: 35 ms, 175 s/s CPU
top 50:  20 ms, 17.5 s/s CPU
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
