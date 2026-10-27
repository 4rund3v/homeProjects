# Basics: bloom filters

[Back](README.md)

## Why

Learn bloom filters by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: 1 million URLs, 1% false positive

```text
n = 1,000,000
target FP = 1%
m (bits)  = -n·ln(p) / (ln 2)² = -1,000,000·ln(0.01)/(0.693)² ≈ 9.6M bits ≈ 1.2 MB
k (hashes) = (m/n)·ln 2 ≈ 9.6 · 0.693 ≈ 6.6 → use 7
```

7 independent hashes per insert and query; memory is 1.2 MB. Compare: an exact set of 1 million 32-byte URLs is ~32 MB.

Sensitivity to over-insertion: if 2 million keys are inserted into a filter sized for 1 million, the fill fraction rises and the FP rate jumps from 1% to roughly 23%. Track `inserts` count; when it exceeds 80% of design `n`, rebuild at the new size — not by adding bits to the same filter.

Deletion: a plain Bloom filter cannot delete. A counting Bloom filter (4-bit counters per bit) supports delete but uses 4× the memory (≈ 4.8 MB here) and overflows if the count exceeds 15.
