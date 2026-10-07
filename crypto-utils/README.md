# Crypto Utilities

**Goal:** Learn to use secure cryptographic primitives correctly, by comparing small experiments.

**Scope:** Hashes, HMAC, authenticated encryption, digital signatures, password hashing, randomness, and safe library APIs. Design tradeoffs and common mistakes are first-class. No invented cryptography.

**Out of scope:** Blockchains, certificate authority infrastructure, token formats, and any production credential store. Those belong to TLS/Keycloak lessons.

**Learning focus:** Choosing the right primitive, parameterization (work factor, algorithm, key length), why most mistakes are in usage, how to use test vectors, and what security review looks like for small components.

**Depends on:** `go-fundamentals`, `python-refresh`.

## Milestones
- [ ] Identify a small set of exercises covering hash, HMAC, symmetric encryption, asymmetric signing, and password hashing.
- [ ] Run each exercise with documented parameters, test vectors, and failure cases.
- [ ] Profile only the password-hashing exercise to understand work-factor behavior; discuss when profiling is worth the complexity.
- [ ] Write what is secure, what is merely obscure, and which choice you would make in each scenario.

## Tools
- Go `crypto` and Python `hashlib`, `hmac`, `cryptography`, and `passlib`/`argon2` equivalents.

**Environment (Python):** See [`uv-setup.md`](../uv-setup.md).
