# Basics: advanced search

[Back](README.md)

## Why

Learn advanced search by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: two-stage latency budget

```text
p95 SLO = 100 ms
stage 1 = BM25 candidate generation (top 100)
stage 2 = rerank 100 with distance + freshness + click features
```

```text
BM25 top 100            = 20 ms
feature fetch per doc   = 0.5 ms × 100 = 50 ms  (parallel: 10 ms)
blend + sort            = 5 ms
```

Sequential: 20 + 50 + 5 = 75 ms, inside budget. Parallel feature fetch: 20 + 10 + 5 = 35 ms. The difference is whether feature fetches are pipelined or awaited one by one.

Security filter: apply the authorization filter *before* top-K. If you filter after, a user with access to 5 of 1,000 documents gets the top 5 of the authorized set — but the ranking is computed over the full set, leaking relative relevance of documents they cannot see. With pre-filter, the 1,000 are reduced to 5 first, then ranked within the visible set.

Zero-result rate: if 3% of queries return 0 after filters, expand the filter (widen geo radius by 1.5×, drop one synonym) before returning an empty page.
