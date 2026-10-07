# Crypto Utilities

## What this project exists to solve
Learn to select and use the right cryptographic primitive for each task, by comparing small, bounded experiments. The project does not teach cryptography from first principles; it teaches disciplined usage of standard libraries with testable, documented tradeoffs.

## Success criteria / completion metrics
- One small, documented experiment per primitive: hash/MAC, authenticated encryption, asymmetric signing, and password hashing.
- Each experiment uses test vectors or documented parameters and records why specific algorithms and parameters were chosen.
- A reflection in `NOTES.md` that identifies common pitfalls and would-be misuse patterns.
- `NOTES.md` explicitly states where the experiments stop and production use requires more.

## Prerequisites and dependencies
- `go-fundamentals`, `python-refresh`.

## Tools, libraries, and runtime
- Go `crypto` (stdlib only for the learning exercises).
- Python: `cryptography`, `hashlib`, `hmac`, and `passlib` or `argon2-cffi`; managed via `uv` (see `../uv-setup.md`).
- Test vectors from NIST or library docs.
- Optional profiling of password hashing only to understand work-factor behavior.

## Learning objectives (skills practiced)
- Algorithm selection: hash vs. MAC vs. encryption vs. signature vs. password hash.
- Parameterization: key lengths, iterations, salt handling, and randomness quality.
- Common mistakes: key reuse, comparing secrets in non-constant time, rolling custom primitives.
- Test-vector usage and when to refuse to roll your own.
- Distinguishing JWT/JWS (signatures) from encryption.

## Architecture / design note
Organize as small, single-responsibility scripts or modules rather than a service:

```
exercises/
  hash_mac/
  aead/
  sign_verify/
  password_hash/
common/
  vectors.py / vectors_test.go
NOTES.md
```

Each exercise has a single documented scenario and one assertion about the intended security property. Keep exercises side-by-side in version control so comparison is obvious.

## Test strategy
- Use published test vectors where available.
- Property tests for known-bad inputs (wrong key, wrong ciphertext, wrong signature).
- Explicit negative tests showing misuse is detected (e.g., encrypt-then-MAC vs. MAC-then-encrypt comparison in comments).
- Do not write security proofs; document why this project is not a security review.

## Documentation checklist
- `README.md` with project purpose, setup via `uv`, and a note that this is learning-only.
- `NOTES.md` with primitive selection rationale, misuse examples, and library-specific caveats.
- Comments on each exercise stating when production use requires additional controls (HSM, rotation, audit, etc.).

## API contract
None. Each exercise is a script with documented inputs and assertions.

## UI / status surfaces
CLI only. Output is assertions and explanatory print statements.

## Security boundaries to think about
- Do not invent protocols or primitives; use stdlib or audited libraries only.
- Do not compare secrets with `==`; use `subtle.ConstantTimeCompare` in Go or `hmac.compare_digest` in Python.
- Secret material must not appear in logs, notebooks, or lock files.
- Password-hashing exercises must use salts and tunable work factors deliberately.

## Profiling plan
Profile only password hashing to understand iteration-count effects. Document that performance is intentionally a defense, not a bug, and that profiling is for awareness, not optimization.

## How this project fits into the curriculum
Informs `tls-setup` and `keycloak-setup` where certificates and tokens are manipulated. Do not study JWT structures here; study them in the token-handling projects with real protocols.

## Suggested milestone walkthrough
1. **Hashing and MAC.** Exercise SHA-256 vs. SHA-3 and HMAC with a known key and message. Document collision resistance and MAC purpose.
2. **Authenticated encryption.** Encrypt then authenticate with a chosen AEAD; verify with test vectors. Explain why unauthenticated encryption is not acceptable.
3. **Signatures.** Sign and verify with RSA/Ed25519; compare with a verification key mismatch.
4. **Password hashing.** Hash a password with argon2 or bcrypt; compare parameter choices and their runtime effect.

## Reference notes and resources
- NIST cryptographic standards and test vectors.
- Go `crypto` package documentation.
- Python `cryptography` docs.
- OWASP Cryptographic Storage Cheat Sheet.
