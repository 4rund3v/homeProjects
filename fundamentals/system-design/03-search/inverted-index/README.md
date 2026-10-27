# Inverted index fundamentals

[Back](../../README.md)

## Why

A document index must answer "which documents contain term X?" without scanning every document. An inverted index stores term → posting lists instead of document → terms.

## How

```text
document → tokenizer → terms
term → (doc_id, term frequency, position, metadata)
```

Query terms become postings. Intersection, union, and phrase checks happen on the compressed posting lists.

## Under the hood

Each posting list is stored in a separate structure. Classic layout:

- Term dictionary
- Per-term posting list of `(doc_id, tf, [positions])`
- Skip lists or block pointers for fast intersection

For phrase queries, positions are kept and checked with a relative-offset scan. Document frequency and average field length feed the ranking step.

## Production use cases

Document search, log search, autocomplete, and faceted navigation.

## Trade-offs

Small term sets with huge posting lists (think "the", "a") are hot. Consider a stopword list, but do not rely on it for correctness. Keep term frequency and positions only when the ranker or phrase query needs them.

## Lab

Build an inverted index over a sample corpus. Compare scan time and query time for a random single term, a conjunction, and a phrase.

## Worked examples

**Situation: 10M documents, 500 words/doc, query "cat".**
```text
total terms = 10M × 500 = 5 billion
unique terms ≈ 200,000
df("cat")    = 500,000 (5% of docs)
posting list = 500,000 × 8 bytes = 4 MB
```
Query "cat": read 4 MB posting list, sort top 100 by BM25. p50 = ~5 ms on a 100 MB/s SSD.

Conjunction "cat AND red": intersect two ~500K lists. The shorter list (assume "red" df = 200K) is the inner loop: 200K × ~0.1 ns = 20 µs. Union "cat OR dog": ~500K + ~400K = 900K candidates → rank 900K → p50 = ~15 ms.

Stopword "the" df = 9M (90% of docs): posting list = 9M × 8 bytes = 72 MB. Reading it per query is 720 ms on a 100 MB/s disk — 144× the cost of "cat". Dropping "the" saves 72 MB of I/O per query.

```text
"cat":       4 MB read, 5 ms
"cat AND red": 20 µs intersect
"cat OR dog":  900K rank, 15 ms
"the":       72 MB read, 720 ms  ← drop it
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
