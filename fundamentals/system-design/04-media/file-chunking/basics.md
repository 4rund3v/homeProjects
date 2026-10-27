# Basics: file chunking

[Back](README.md)

## Why

Learn file chunking by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: 10 GB upload, 512 MB chunks

```text
file     = 10 GB = 20 chunks of 512 MB
bandwidth = 100 Mbps sustained
```

```text
time per chunk = 512 MB × 8 / 100 Mbps = 41 s
total upload   = 20 × 41 s ≈ 820 s ≈ 14 min
```

If one chunk fails at chunk 14, resuming sends only chunks 15–20 = 6 × 41 s ≈ 246 s. Without chunking, a failure at that point restarts the full 14 minutes.

Metadata cost: 20 chunks × (index, hash, size, status) ≈ 20 × 100 bytes = 2 KB. At 100,000 concurrent uploads, that's 200 MB of upload-manifest state — trivially held in a key-value store.

Hash verification: SHA-256 of 512 MB takes ~1 s on modern hardware. Total hash work for 10 GB = 10 s, ~1% of upload time. The final file hash prevents silent chunk loss: if chunk 7's stored hash mismatches its content hash, the manifest rejects the commit.

Chunk size trade-off: 8 MB chunks → 1,250 chunks for 10 GB, 125 KB of manifest metadata, but 1,250 PUT requests with per-request overhead; 512 MB chunks → 20 chunks, 2 KB metadata, but a single failed chunk wastes 41 s.
