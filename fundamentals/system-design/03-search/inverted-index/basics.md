# Basics: inverted index

[Back](README.md)

## Why

Learn inverted index by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: posting list size

Corpus = 10 million documents, average 500 words.

```text
total terms = 10,000,000 × 500 = 5 billion
unique terms ≈ 200,000
posting list per common word ≈ 5,000,000 docs (a very common term)
posting list per rare term    ≈ 50 docs
```

A single rare-term lookup reads ~50 × 8 bytes (doc IDs) = 400 bytes. A conjunction of 2 rare terms intersects two ~50-element lists → 50 steps. A common-term lookup reads 5,000,000 × 8 = 40 MB. That is why stopword lists exist: dropping "the", "a", "of" removes the largest posting lists and saves the index from degenerating into a scan.

Storage: 5 billion postings × 8 bytes ≈ 40 GB of posting lists before compression. Byte-aligned delta + bit-packing usually gets 3–5× reduction.
