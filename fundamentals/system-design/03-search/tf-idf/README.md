# TF-IDF scoring

[Back](../../README.md)

## Why

A document that mentions "cat" among ten thousand other words should not rank as strongly for a cat query as a document of only "cat cat cat". TF-IDF separates *term frequency* (how relevant to this doc) from *inverse document frequency* (how rare across the corpus).

## How

```text
score = tf(t, d) * idf(t)
idf(t) = log( N / (df(t) + 1) )
```

- `tf` is the raw or normalized count of term `t` in document `d`.
- `df(t)` is the number of documents containing `t`.
- `N` is the corpus size.

## Under the hood

The formula has three assumptions:

1. A query term is more informative the rarer it is.
2. A document mentioning the term more is more relevant.
3. Both must be combined multiplicatively.

Stopwords and common tokens have high `df`, so `idf` near zero. A rare token has low `df`, so `idf` large.

The practical variants differ:

- Raw `tf` — favors long documents; normalize by document length.
- Log `tf` — compresses counts: `1 + log(tf)`.
- Sublinear — same idea.
- A smoothing term in `idf` prevents division by zero when `df` is small.

## Production use cases

Classic document retrieval, autocomplete relevance, and as a base for richer rankers.

## Trade-offs

| Variant | Behavior |
|---|---|
| Raw tf | length bias |
| Log tf | dampens long docs |
| Smoothing idf | handles rare terms |
| Stopwords | drops high-df tokens, changes ranking |

## Lab

Rank a small corpus with raw and log `tf`. Compare the top results. Observe what happens when one document is 10× longer but has the same `tf`.

## Worked examples

**Situation: 5-document corpus, query "cat".**
```text
N = 5
df("cat") = 2
idf("cat") = log(5 / 2.5) ≈ 0.69

doc 1: 3 occurrences, 200 words
doc 3: 1 occurrence,  40 words

raw tf:   doc 1 → 3, doc 3 → 1
log tf:   doc 1 → 1+log(3)=2.48, doc 3 → 1+log(1)=1.00

doc 1 score (raw)  = 0.69 × 3   = 2.08
doc 3 score (raw)  = 0.69 × 1   = 0.69
doc 1 score (log)  = 0.69 × 2.48 = 1.71
doc 3 score (log)  = 0.69 × 1.00 = 0.69
```
Raw tf: doc 1 wins by 3×. Log tf: doc 1 wins by 2.5×. Doc 3 is a 40-word product description that is *only* about cats; doc 1 is a 200-word article mentioning cats three times. Log tf is closer to the human ranking.

A 10× longer document with the same tf: raw tf gives it the same score (length is not in the formula). Log tf gives it the same score. Neither penalizes length — that is what BM25's `b` parameter fixes.

```text
raw:  doc1/doc3 = 3.0×
log:  doc1/doc3 = 2.48×
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
