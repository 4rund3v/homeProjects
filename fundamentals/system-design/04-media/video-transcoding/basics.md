# Basics: video transcoding

[Back](README.md)

## Why

Learn video transcoding by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: bitrate ladder and storage

```text
source = 30 min video, H.264 5 Mbps ≈ 1.1 GB
ladder = 4 renditions: 0.5, 1, 2.5, 5 Mbps
```

```text
ladder storage = 30 × 60 × (0.5 + 1 + 2.5 + 5) Mbps × 1 min
              = 1,800 × 9 / 8 GB
              ≈ 2.0 GB (vs 1.1 GB original, ~80% overhead)
```

Adaptive playback at 3 Mbps observed bandwidth: player starts at 2.5 Mbps rendition (~30 s to buffer 3 s of content), stays there; when bandwidth drops to 1.2 Mbps, switches to 1 Mbps at next segment boundary (~2 s later). Rebuffer probability ∝ `buffer / segment duration`. With 4 s segments, buffer 30 s → 12 segments of headroom before a bandwidth drop forces a rebuffer.

Worker math: encoding 30 min at 1× real-time on 8 cores = 30 × 60 / 8 = 225 s per rendition; 4 renditions = 900 s total. 1,000 videos/day → 1,000 × 900 s = 900,000 s ≈ 10.4 days single-worker. 50 parallel workers → ~12.5 hours per day batch, inside a 24-hour SLA.

Manifest publish: the manifest lists 4 renditions; a segment 4k for rendition 1 is only valid if all 4 segments k exist. A manifest that publishes early with missing segments causes client errors at the missing rendition.
