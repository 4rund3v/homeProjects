# BM25 and parameter tuning

[Back](../../README.md)

## Why

TF-IDF is a starting point. BM25 improves it by saturating term frequency and accounting for document length in a way that is stable across a corpus. It is the default scoring in most search engines.

## How

```text
score(t, d) = idf(t) * ( tf * (k1 + 1) ) / ( tf + k1 * (1 - b + b * len(d) / avg_len) )
```

- `tf` — term frequency in document `d`.
- `len(d)` — document length.
- `avg_len` — corpus average length.
- `k1` — a saturation parameter.
- `b` — a length normalization parameter.

`idf(t)` is usually `log(1 + (N - df + 0.5) / (df + 0.5))`.

## Under the hood

The denominator is a rational function of `tf`:

- As `tf` grows, the score approaches `idf * (k1 + 1)`. This is saturation: more mentions help up to a point.
- `k1` controls how quickly saturation happens. Small `k1` saturates fast.
- `b` controls how strongly a long document's per-term score is damped. `b = 0` ignores length.

## Parameter tuning

| Parameter | Effect |
|---|---|
| `k1` low | saturation fast, term counts matter less |
| `k1` high | saturation slow, term counts matter more |
| `b = 0` | length ignored |
| `b` high | long docs penalized more |
| `b` low | length effect small |

Tune on labeled data, not intuition. The right values depend on the corpus's length distribution and query style.

## Production use cases

Web search, document retrieval, log search, and hybrid ranking where BM25 is the lexical baseline.

## Trade-offs

- Pure BM25 does not capture semantics: synonyms, spelling errors, and near-meaning need a separate signal.
- The parameters are not transferable across very different corpora.
- Reindex the corpus whenever the length distribution changes; an outdated `avg_len` degrades ranking.

## Lab

Re-index a corpus and vary `k1` and `b` on a grid. Measure nDCG on a labeled set. Plot the surface; look for flat regions and cliff regions.

## Worked examples

**Situation: 2 documents, query "cat", k1=1.2, b=0.75.**
```text
N = 2, df = 2, avg_len = 3.5
idf = log(1 + (2-2+0.5)/(2+0.5)) ≈ 0.18

doc A: 5 occurrences, len=5
doc B: 1 occurrence,  len=2
```

Doc A: `tfSat = 5×2.2 / (5 + 1.2×(0.25 + 0.75×5/3.5)) = 11/6.585 ≈ 1.67` → score = 0.18 × 1.67 = 0.30
Doc B: `tfSat = 1×2.2 / (1 + 1.2×(0.25 + 0.75×2/3.5)) = 2.2/1.815 ≈ 1.21` → score = 0.18 × 1.21 = 0.22

Doc A wins. Now `b = 0`:
Doc A: `den = 5 + 1.2 = 6.2` → 11/6.2 = 1.77 → score = 0.32
Doc B: `den = 1 + 1.2 = 2.2` → 2.2/2.2 = 1.00 → score = 0.18

Length normalization off: doc A's advantage grows. `b = 0.5`: doc B `den = 1.615` → score ≈ 0.25, closer to doc A.

Tuning grid: k1 ∈ {0.5, 1.2, 2.0}, b ∈ {0, 0.5, 0.75, 1.0}. Measure nDCG@10. Web search: k1≈0.5, b≈0.75. Log search: k1≈2.0, b≈0.5 (count matters more).

```text
k1=1.2,b=0.75: A=0.30, B=0.22
k1=1.2,b=0.0:  A=0.32, B=0.18
k1=2.0,b=0.5:  A=0.33, B=0.25
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
