# Basics: probabilistic overview

[Back](README.md)

## Why

Learn probabilistic overview by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: choosing a structure for a unique-visitor counter

```text
key space = 100 million visitor IDs per day
question  = "is this visitor new today?"
exact set = 100M × 8 bytes = 800 MB
Bloom (1%, 16 hash fns) = 100M × 11 bits ≈ 140 MB
```

The exact set answers "yes/no" with no false positives. The Bloom filter answers "no" with certainty and "yes" with 1% false-positive rate — the app must confirm a positive against the authoritative store. For cache-aside patterns (avoid a DB lookup for a key that is definitely absent), a Bloom filter at 1% FP saves ~99% of DB reads on the negative path.

For top-K queries on 100 million events: exact map needs 800 MB; a Count-Min Sketch at ε = 0.01 (width = e/0.01 ≈ 272) and depth = 4 uses `272 × 4 × 8 bytes ≈ 8.7 KB` — 90,000× smaller, at the cost of overestimating rare keys by up to 1%.

The decision is memory vs error, not correctness. A billing system cannot use an approximate count; a "top N ads" dashboard can.
