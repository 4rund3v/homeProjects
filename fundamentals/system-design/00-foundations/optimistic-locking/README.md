# Optimistic locking patterns

[Back](../../README.md)

## Why

Optimistic locking assumes conflicts are uncommon and avoids blocking readers or writers. It detects that state changed before committing the update, then retries or reports conflict.

## How

Store a version with the record:

```sql
UPDATE document
SET body = ?, version = version + 1
WHERE id = ? AND version = ?;
```

If affected rows equals one, the write wins. If zero, another writer changed the record; reload, merge, retry with a bound, or return a conflict.

## Under the hood

The version is a fencing value for the record. The compare-and-swap condition makes the decision atomic at the storage boundary. A retry must re-read current state; blindly replaying the old write defeats the protection.

Merge policy matters: last-write-wins is easy but can lose user edits. Field-level merge, operation-based updates, or a conflict UI preserve more intent.

## Production use cases

- Collaborative document edits.
- Low-conflict profile updates.
- Cache refresh guarded by version.
- APIs using `If-Match: <etag>`.

## Trade-offs

| Benefit | Cost |
|---|---|
| No long waits | retry storms under contention |
| High read concurrency | conflict handling complexity |
| Simple storage primitive | merge semantics are domain-specific |

## Lab

Run concurrent updates with the same expected version. Verify exactly one succeeds. Add exponential backoff and a maximum retry count; measure how success rate and latency change as contention rises.

## Worked examples

**Situation: 100 concurrent writers on one document.**
P(success) per attempt = 1/100 = 1%. Expected attempts to succeed = 100. With exponential backoff (50 ms base, ×2, cap 2 s): total wait ≈ 50 × (1+2+4+...+256) ≈ 50 × 511 = 25.5 s for the unlucky writer. 99 writers conflict; only 1 succeeds on the first attempt. With a version check, 99 of 100 fail the `WHERE version=3` and retry. The system is correct but slow. Pessimistic would have queued all 100 in 2 ms = 200 ms total. The choice depends on whether 25 s is acceptable for the use case.

```text
optimistic:  1 success + 99 conflicts + retries ≈ 25 s worst case
pessimistic: 100 queued × 2 ms = 200 ms
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
