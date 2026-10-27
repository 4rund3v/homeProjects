# proj-auth-crypto

> Own the layer everyone assumes you understand. From "who are you?" to "this byte was signed by that key."

This project is a **standalone learning unit** on authentication, tokens, and the cryptography underneath them. It is not built on any other project. Read it in order, top to bottom, and by the time you reach the capstone you can explain the entire system to a panel cold.

The goal is **theory → true worked examples → a small runnable system**, in that order. Every folder teaches the concept, shows it at the byte level, and names the *exact tool and command* a senior runs. No application code — only the **logic and the precise CLI invocations**.

---

## Why this order?

Authentication is not one thing. It's a stack of primitives, each answering a different question, and each one is only safe *because of* the one below it. If you skip the cryptography, the token layer is a black box you're just trusting.

```
┌──────────────────────────────────────────────────────────┐
│ 08. Capstone       assemble: login → tokens → mTLS → DB │
├──────────────────────────────────────────────────────────┤
│ 07. Key mgmt       KMS/HSM, rotation, envelope, secrets │
├──────────────────────────────────────────────────────────┤
│ 06. Service accts  k8s SA, workload identity, mTLS S2S   │
├──────────────────────────────────────────────────────────┤
│ 05. OAuth / OIDC   4 flows, IdP vs client vs resource    │
├──────────────────────────────────────────────────────────┤
│ 04. JWT            anatomy, claims, rotation, revocation │
├──────────────────────────────────────────────────────────┤
│ 03. Asymmetric     RSA/ECC, sign≠encrypt, certs, PKI     │
├──────────────────────────────────────────────────────────┤
│ 02. Symmetric      AES modes, KEK, IV, MAC, at-rest      │
├──────────────────────────────────────────────────────────┤
│ 01. Hashing        SHA, bcrypt/argon2, HMAC, salts       │
├──────────────────────────────────────────────────────────┤
│ 00. Mental model   id/auth/authz, what a token IS, the   │
│                    3-legged dance, why each layer exists │
└──────────────────────────────────────────────────────────┘
```

**Read 00–03 bottom-up to build the primitives. Read 04–06 top-down to see them assembled into tokens and flows. 07 is the operational spine (key rotation touches everything). 08 is where it all comes together.**

- **01–03** are the *crypto*: what a hash, a symmetric cipher, and an asymmetric key actually do, at the byte level, and which tool runs which.
- **04–05** are the *tokens*: JWTs and the OAuth/OIDC flows that hand them out. These are the pieces a panel probes hardest.
- **06** is *machines authenticating as themselves* — service accounts, workload identity, service-to-service mTLS.
- **07** is *who keeps the keys and how you rotate them without dropping traffic*.
- **08** is the capstone: the decision log + a single-file runbook that builds all of it.

---

## Folder structure

```
proj-auth-crypto/
├── 00-mental-model            ← The whole thing in one diagram: id/auth/authz, what a token IS, the 3-legged dance, why each layer exists
├── 01-hashing                ← MD5/SHA-256/SHA-512, bcrypt/argon2, HMAC, why salt + stretch, collision classes, never roll your own
├── 02-symmetric-encryption   ← AES (GCM/CTR), KEK, key size, IV, MAC vs encryption, at-rest vs in-transit
├── 03-asymmetric-encryption ← RSA/ECC, public/private, sign≠encrypt, key sizes, cert chains, CAs, PKI
├── 04-jwt                    ← header/payload/signature, alg confusion, JWKS, claims, short access vs long refresh, rotation, revocation
├── 05-oauth-oidc            ← the 4 flows (auth code, client creds, PKCE, refresh), OIDC on top, IdP/client/resource, redirect URIs, scopes vs claims
├── 06-service-accounts       ← k8s SAs, workload identity, mTLS per-pod cert, cloud SAs, why apps use these not user creds
├── 07-key-management         ← KMS, HSM, key rotation, envelope encryption, "never store the key next to the data", rotation drills
└── 08-capstone              ← "build it": login → rotating refresh JWT → argon2 password → mTLS service-to-service → AES-GCM field → JWKS endpoint
```

---

## How to use this

Each folder is self-contained and follows one shape:

1. **Teach first** — the concept named, then the mechanism. Never "use RSA" — always "public/private key, sign = private, verify = public, and *why* asymmetric beats symmetric for *signing* (many verifiers, one signer)."
2. **True worked examples** — a real `eyJhbGci...` broken into its three parts; a real `openssl genpkey` / `openssl req`; what "bcrypt cost 12" actually costs in seconds; a real `aes-256-gcm` IV + auth tag.
3. **Which tool, which command** — openssl, libsodium, argon2, Vault, cosign, JWKS tooling. Named.
4. **Thresholds** — the concrete numbers where behavior changes ("AES-128-GCM is the default; AES-256 when the data outlives the decade," "bcrypt 10–14 sweet spot, 12 ≈ 250ms").
5. **Failure modes** — deliberately cause the break the primitive exists to survive.
6. **L5/L6 lens** — the panel probes and the concrete artifact that stops each.
7. **Exit criteria + cross-refs** — done means, and which sibling doc each concept links to.

The first seven folders are reading. The capstone is where the *commands* live. Do not skip 00 — "what a token *is*" is the single question a panel asks first.

---

## Reading order + time

```
~15 min │ 00 mental-model       the diagram + the vocabulary
 ~20 min │ 01 hashing          hash vs KDF, salt, stretch
 ~20 min │ 02 symmetric        AES-GCM vs CTR, IV, MAC
 ~25 min │ 03 asymmetric       RSA/ECC, sign≠encrypt, certs
 ~25 min │ 04 jwt             anatomy + the alg-confusion failure
 ~25 min │ 05 oauth-oidc      the 4 flows + redirect URIs
 ~20 min │ 06 service-accounts SA → workload identity → mTLS
 ~25 min │ 07 key-management  KMS/HSM, envelope, rotation drills
 ~60 min │ 08 capstone        the decision log + runbook (the payoff)
```

Total: a few hours of reading. By the end you can walk a panel through **the first 500ms of a login, what happens when the signing key leaks today, and signing vs. encryption** — the three probes 04/05/00 set up and 08 proves you can answer.

---

## The senior engineer's mental model

As you read each folder, keep four questions running:

- **Who is being authenticated, and who is trusting the proof?**
- **What's the blast radius if this key / token / cert leaks right now?**
- **What does rotation look like, and can I do it without dropping in-flight traffic?**
- **What would on-call need at 3am when this silently expires?**

The goal is not to configure tools. It's to build the intuition that lets you reason about a token, a key, or a cert you've never seen before.
