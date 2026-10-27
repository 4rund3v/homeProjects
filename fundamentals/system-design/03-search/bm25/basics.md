# Basics: bm25

[Back](README.md)

## Why

Learn bm25 by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: two documents, one query term

```text
corpus: 2 documents
doc A: "cat cat cat cat cat" (5 occurrences, len=5)
doc B: "cat dog"             (1 occurrence,  len=2)
avg_len = 3.5
query: "cat"
k1 = 1.2, b = 0.75
idf("cat") ≈ log(1 + (2 - 2 + 0.5)/(2 + 0.5)) ≈ log(1.2) ≈ 0.18
```

Doc A: `tf=5, len=5`
```text
num  = 5 × (1.2 + 1) = 11
den  = 5 + 1.2 × (1 - 0.75 + 0.75 × 5/3.5)
       = 5 + 1.2 × (0.25 + 1.071) = 5 + 1.585 = 6.585
tfSat = 11 / 6.585 ≈ 1.67
scoreA = 0.18 × 1.67 ≈ 0.30
```

Doc B: `tf=1, len=2`
```text
num  = 1 × 2.2 = 2.2
den  = 1 + 1.2 × (0.25 + 0.75 × 2/3.5) = 1 + 1.2 × 0.679 = 1.815
tfSat = 2.2 / 1.815 ≈ 1.21
scoreB = 0.18 × 1.21 ≈ 0.22
```

Doc A wins even though doc B mentions "cat" in a shorter document. Now set `b = 0` (no length normalization):

```text
doc A den = 5 + 1.2 = 6.2      → 11/6.2 = 1.77
doc B den = 1 + 1.2 = 2.2      → 2.2/2.2 = 1.00
```

Doc A's advantage grows to 1.77× vs 1.00× — the shorter document is penalized *less* because b is off. Lowering b below 0.75 (say b = 0.5) gives doc B `den = 1 + 1.2 × (0.5 + 0.5 × 2/3.5) = 1.615` → score ≈ 0.25, closer to doc A.

Tuning grid: vary `k1` over {0.5, 1.2, 2.0} and `b` over {0, 0.5, 0.75, 1.0}. Measure nDCG@10 on a labeled query set. The "correct" values are workload-specific: log search wants high k1 (count matters), web search wants lower k1 (mention saturation).
