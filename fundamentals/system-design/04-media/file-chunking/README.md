# File chunking

[Back](../../README.md)

## Why

Large files should not be uploaded as one request. One timeout would restart all work, memory use would spike, and a partial upload would be hard to resume.

## How

```text
file → chunks → upload independently → verify each hash → commit manifest
```

A client starts an upload and receives an upload ID. Each chunk carries an index, size, and content hash. The server acknowledges chunks independently. A final commit verifies that every expected chunk exists and that the assembled file hash matches.

## Under the hood

The upload manifest is the source of truth:

```text
upload_id, total_size, chunk_size, expected_count,
chunk_index → hash, length, durable location
```

Chunk size trades overhead against retry cost. Large chunks reduce metadata and requests but waste more bandwidth on failure. Fixed chunks support deterministic offsets; content-defined chunks deduplicate better but complicate assembly.

Upload handlers must be idempotent: re-sending `(upload_id, chunk_index, hash)` returns success if the same chunk is already durable and rejects a conflicting hash.

Use a final content hash to catch missing, duplicated, or reordered chunks. Never mark a file complete merely because the client says it uploaded all parts.

## Production use cases

Object-store multipart upload, resumable video uploads, backups, and data export.

## Failure modes

- Lost client state: list server-side uploaded chunks.
- Corrupt chunk: reject hash mismatch.
- Abandoned upload: expire manifests and garbage-collect parts.
- Partial commit: use an atomic manifest state transition `OPEN → COMPLETE`.

## Lab

Upload a 1 GB test file in chunks. Kill the client halfway, resume, corrupt one chunk, and verify only that chunk retries. Confirm the final assembled hash.

## Worked examples

**Situation: 10 GB upload, 512 MB chunks, 100 Mbps.**
```text
chunks = 10 GB / 512 MB = 20
time/chunk = 512 × 8 / 100 = 41 s
total = 20 × 41 = 820 s ≈ 14 min
```
Failure at chunk 14: retry 6 chunks = 6 × 41 s = 246 s. Without chunking: full 820 s restart.

Metadata: 20 chunks × 100 bytes = 2 KB. 100,000 concurrent uploads = 200 MB manifest state.

Hash: SHA-256 of 512 MB ≈ 1 s on modern hardware. 20 chunks × 1 s = 20 s total. 20/820 = 2.4% of upload time.

Chunk size trade-off: 8 MB chunks → 1,250 chunks for 10 GB → 1,250 PUT requests (5% overhead per request ≈ 62 s). 512 MB chunks → 20 chunks → 20 requests (1% overhead ≈ 8 s). But a failed 512 MB chunk wastes 41 s; a failed 8 MB chunk wastes 0.6 s.

```text
512 MB:  20 chunks, 41 s/chunk, 8 s overhead, 41 s waste on fail
8 MB:   1250 chunks, 0.6 s/chunk, 62 s overhead, 0.6 s waste on fail
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
