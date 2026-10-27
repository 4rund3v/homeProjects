# Basics: tf idf

[Back](README.md)

## Why

Learn tf idf by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: tf-idf on a 5-document corpus

```text
N = 5 docs
query: "cat"
df("cat") = 2 (docs 1 and 3 contain "cat")
idf("cat") = log(5 / (2 + 1)) = log(1.67) ≈ 0.51

doc 1: 3 occurrences of "cat", 200 words total
doc 3: 1 occurrence of "cat", 40 words total

raw tf:    doc 1 → 3, doc 3 → 1
log tf:    doc 1 → 1+log(3)=2.48, doc 3 → 1+log(1)=1.00
```

Raw tf ranks doc 1 3× above doc 3. With log tf, the gap is 2.48×. If doc 3 is a 40-word product description that is *only* about cats, and doc 1 is a 200-word article mentioning cats three times, log tf is closer to the human ranking.

Sensitivity: the smoothing term in idf (`df + 0.5`) changes a rare term's score a lot. A term appearing in 1 of 1M docs gets `idf ≈ log(1,000,000 / 1.5) ≈ 13.4`. A term in 100k docs gets `log(1,000,000 / 100,500) ≈ 2.3`. The 10× frequency gap produces a 6× score gap — tuning `df` smoothing directly changes what "relevant" means.
