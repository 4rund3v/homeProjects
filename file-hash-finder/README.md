# File Hash Finder

**Goal:** Build a safe Go CLI that finds duplicate files by content.

**Scope:** Directory traversal, file metadata, SHA-256 (optionally BLAKE3), configuration, concurrent hashing, dry-run reporting.

**Out of scope:** Automatic deletion by default, GUI, network filesystems.

**Learning focus:** Go filesystem APIs, worker pools, cancellation, config validation, deterministic output, safe destructive-operation design.

**Depends on:** `go-fundamentals`.

## Milestones
- [ ] Walk a fixture tree and identify duplicates using SHA-256.
- [ ] Add ignore rules and minimum-size configuration.
- [ ] Add bounded parallel hashing; compare with serial behavior and use `-race`.
- [ ] Implement dry-run-first cleanup with explicit confirmation and tests.
