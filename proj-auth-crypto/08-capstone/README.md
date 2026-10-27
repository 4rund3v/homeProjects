# 08 — Capstone: Build It (Decision Log + Runbook)

**Folder:** `08-capstone/`

We've now got every piece. Here's the shape of a *real* service that uses all of them — and **why each decision was made.** Then a single-file *runbook* of the actual shell/CLI commands to build it. **No source code.** The commands, not the app.

The service, named **`auth-svc`**, does six things. Each one maps to a folder:

| Job | The primitive | The folder |
|---|---|---|
| (a) user login | argon2id password KDF | `01` |
| (b) issue short access + rotating refresh JWT | asymmetric signing, JWKS, refresh rotation | `04` / `05` |
| (c) store a hashed password | argon2id + per-user salt | `01` |
| (d) service-to-service mTLS with workload identity | workload cert, k8s CA, per-pod | `06` / `03` |
| (e) store a sensitive field AES-GCM in a DB | envelope encryption (DEK/KEK) | `02` / `07` |
| (f) expose a JWKS endpoint for consumers | public-key distribution | `04` / `03` / `07` |

---

## Teach first: the decision log (the *why* of every choice)

**Decision 1 — Store the password with argon2id, not "salted SHA-256" or bcrypt, at the KDF's cost on *production hardware.***
- *Why argon2id over bcrypt:* argon2id is **memory-hard** — it caps an attacker's *parallelism* (a GPU farm can't cheaply parallelize across RAM), whereas bcrypt caps only *rate*. **`01`'s threshold: argon2id `m`~64MB / `t`~4 / `p`~1.**
- *Why not "salted SHA-256":* that's a **fast digest** — a farm hashes it in billions/sec. A password store *must* be the slow KDF (`01`'s KDF-vs-digest split).
- *The salt:* **32 random bytes, unique per user, stored in plaintext next to the hash** (`01`). Not a secret; its job is to kill rainbow tables + make per-user storage independent.
- *The cost target:* **~250ms on the box that actually serves logins** — not your laptop. You re-measure; the cost drifts down as CPUs get faster.
- *The compare:* **constant-time.** A non-constant-time `==` leaks "how many leading bytes matched" — a timing oracle (`01`'s failure).

**Decision 2 — Issue a *short* access JWT (5 min) + a *rotating* refresh JWT, signed with Ed25519/P-256.**
- *Why 5 min access:* the access token is **stateless** — its *only* revocation is `exp` (`04`). A 5-min token dies in 5 min; a 24h token *outlives a lockout* (`04`'s failure #6).
- *Why rotating refresh:* **rotation is the theft detector** (`04`). Each refresh token is usable exactly once; a *replay* of a stale one → the IdP kills the *whole family* (all outstanding for that subject), not just the token.
- *Why Ed25519/P-256 over RSA:* **small certs, fast sign, cheap JWKS fetch** (`03`'s key-size threshold: P-256 ≈ RSA-3072 ≈ 128-bit; a JWKS public key is 32 B vs 384 B).
- *The refresh token shape:* an **opaque `jti`-bearing JWT** (not a human-readable blob) — held *server-side*, so it's revocable/replay-checkable (`04`).

**Decision 3 — Sign the JWTs with a key held in the KMS; publish the public half at JWKS.**
- *Why the key lives in the KMS:* **never store the key next to the data it protects** (`07`'s load-bearing rule). The signing key's *usable form* never materializes in the app; the KMS does the sign op and returns the signature.
- *Why a JWKS endpoint:* that's how consumers verify **locally without a phone call** (`04`'s stateless verify; `00`'s "proof without a call"). The public key is *not* secret — it's *distributed* (`03`).
- *The rotation drill:* **new keypair + new `kid`, the JWKS lists both, consumers pick up the new `kid` within the cache TTL, the old key retires after the max access lifetime** (`04`'s JWKS-vs-KMS cross-ref; `07`'s drill).

**Decision 4 — Authenticate service-to-service with mTLS + per-pod workload identity, *not* a shared secret or a user cred.**
- *Why mTLS over plain TLS:* **mTLS gives identity, not just encryption** (`06`). Plain TLS says "someone reached me over TLS"; mTLS says "the workload *named X*, proven by a CA-signed cert." A compromised pod *can't* spoof another service.
- *Why per-pod certs issued by the CA:* **the cert's CN/SAN is the workload identity** (`06`/`03`); short-lived leaves mean a *stale cert expires anyway* (`03`'s leaf-lifetime rule). The capstone issues the cert *per pod* and rotates on schedule.
- *Why not a user cred for the service:* **a machine shouldn't borrow a human's token** (`06`'s three failures: outlives the session / no audit / permission inheritance). The service authenticates *as itself*; the user's scope attaches as a *claimed context*, not the credential.
- *The k8s shape:* **a projected/bound SA token** (short, aud-bound, auto-rotating) — *never* the legacy mounted-Secret token (`06`'s threshold).

**Decision 5 — Encrypt the sensitive DB field with AES-256-GCM, DEK per record, wrapped under the KMS KEK.**
- *Why GCM over raw AES / CBC:* **GCM is AEAD** — confidentiality *and* integrity (the 16-byte tag). CBC is padding-oracle + no tamper detection (`02`'s mode table).
- *Why per-record DEK:* **blast radius = one record per DEK; one KEK covers all** (`02`/`07`'s threshold). Re-wrap the DEKs on rotation; *the data is untouched* (`07`'s KEK-rotation drill).
- *Why the DEK bytes never sit next to the ciphertext:* that's the *single-row leak = plaintext* failure (`02`/`07`). The row holds `{nonce, ciphertext, tag, wrapped-DEK, kek-id}` — never the raw DEK.
- *The `openssl enc -gcm` gotcha:* `openssl enc -gcm` **drops the tag** (`02`). The capstone uses a *library that emits the tag* (libsodium / Go `crypto/aes`+`gcm` / WebCrypto), or hand-rolls Encrypt-then-HMAC if forced to openssl.

**Decision 6 — Expose JWKS, but *pin the accepted algs and reject `alg:none` on every consumer side.**
- *Why the pin:* **the `alg` in the header is not trusted** (`04`/`03`). An attacker sends `alg:none` (unsigned, accepted as signed) or HS256 signed with the *public* key as the HMAC secret (alg-confusion, `03`). **The check is an explicit whitelist + `none` rejection, enforced *before* you touch the claims.**
- *Why the JWKS endpoint specifically:* it's the *distribution* of the public half; consumers *fetch + cache* it. The *cache TTL* is the rotation-window control (`04`/`07`'s cross-ref).

> **The one-paragraph threat model.** The *threats* that shape every decision above: **(1) an attacker with a *leaked DB*** → argon2id cost + per-record DEK + KMS-held KEK (`01`/`02`/`07`); **(2) an attacker with *a stolen access/refresh token*** → 5-min access + rotating refresh + family-kill on replay (`04`); **(3) an attacker with *a leaked signing key*** → the 5-step JWKS demote-and-rotate + in-flight overlap (`04`/`07`); **(4) an attacker *inside the cluster* calling a peer as a *spoofed identity*** → mTLS + per-pod certs + RBAC (`06`); **(5) a *wrong-identity* S2S call (cert/SAN mismatch)** → the CA-chain check rejects it (`06`). **Every decision maps to one of the five. That's the whole threat model.**

---

## The runbook (single-file: the actual commands, not the app)

**Toolchain:** `openssl` (keys/certs), the argon2 KDF (via a CLI like `argon2` or a library — *the cost + salt are the load-bearing parts*, not the tool), `kubectl` (the SA + bound tokens + the RBAC), a KMS (`gcloud kms` / `aws kms` / `vault`), the JWKS tool (`jose` CLI or the IdP's endpoint). **No app source; just the commands a senior runs.**

### Step 0 — the CA (the trust anchor; the decade-scale root, `03`)

```bash
# Root CA (self-signed; the one key whose leak opens the whole system)
$ openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out ca.sk.pem
$ openssl req -x509 -new -key ca.sk.pem -sha256 -days 3650 \
      -subj "/CN=auth-svc-workload-ca" -out ca.crt

# A service leaf (CN = the workload identity; CA:FALSE; the right keyUsage for signing)
$ openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out svc.sk.pem
$ openssl req -new -key svc.sk.pem -subj "/CN=auth-svc" -out svc.csr
$ openssl x509 -req -in svc.csr -CA ca.crt -CAkey ca.sk.pem -CAcreateserial \
      -days 90 -sha256 \
      -extfile <(printf "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature") \
      -out svc.crt

# Verify the chain + the keyUsage + the CA:FALSE (the rogue-CA check, `03`'s failure)
$ openssl verify -CAfile ca.crt svc.crt
$ openssl x509 -in svc.crt -noout -text | grep -A1 'Key Usage\|Basic Constraints'
```

> **The KMS/HSM step (`07`):** the *root CA private key* goes **into the HSM/KMS** (`gcloud kms` / `vault`) — the *usable form never leaves it*. The leaf is *short-lived* (90 days, rotated by the mesh; the *root* is decade-scale).

### Step 1 — the password (argon2id, per-user salt, the KDF cost, `01`)

```bash
# Generate the per-user salt (32 random bytes) + hash at the production cost
$ SALT=$(openssl rand 32 | xxd -p)
$ argon2 --no-password --encode --random-salt --encoding=base64 \
      -m 65536 -t 4 -p 1 'correct-horse-battery'   # m=64MB, t=4 passes, p=1
# → $argon2id$v=19$m=65536,t=4,p=1$<salt>$<hash>
#    (the `m/t/p` + salt are stored in the hash string — that's the per-user row)
```
> *The compare is constant-time in the app (a library's `argon2.verify`) — the *command* above is for *you* to see the cost; the *production path* re-runs argon2id at the **stored** cost and compares in constant time (`01`'s first-500ms).

### Step 2 — the signing key + JWKS (Ed25519 in the KMS, public half at the endpoint, `04`/`03`/`07`)

```bash
# The signing keypair (Ed25519: small, fast — the JWKS workhorse, `03`)
$ openssl genpkey -algorithm ed25519 -out jwt-sk.pem
$ openssl pkey -in jwt-sk.pem -pubout -out jwt-pk.pem
$ openssl pkey -in jwt-sk.pem -text -noout | grep -A3 'ASN1 OID'   # sanity: ed25519

# The JWKS (the PUBLIC half, with a `kid`; the capstone serves this at /
# .well-known/jwks.json; consumers fetch + cache it, `04`)
$ jose jwk create -i jwt-pk.pem -a EdDSA -k "2026-10" | jq .   # → the JWK with kid
# (in practice the IdP/Keycloak serves the JWKS; this is the shape it must have)

# The KMS holds the PRIVATE half: the jwt-sk never sits next to the tokens it signs (`07`)
$ gcloud kms keys create jwt-signer --key-ring auth-svc-keys --location us-east1
$ gcloud kms keys import-key jwk:jwt-sk.pem --key jwt-signer --key-ring auth-svc-keys
```

**The rotation drill (`07`, the "signing key leaked today"):** new keypair + new `kid` → the JWKS lists **both** → new tokens sign under the new key → the old tokens verify under the old key for **the max access lifetime** → retire the old key from the JWKS → consumers' cache TTL covers the gap.

### Step 3 — the service account + mTLS identity (k8s bound token + workload cert, `06`/`03`)

```bash
# The k8s SA + a BOUND token (short, aud-bound, auto-rotating — never the legacy Secret, `06`)
$ kubectl create serviceaccount auth-svc -n auth
$ kubectl create token auth-svc -n auth --audience=https://kubernetes.default --duration=1h
#    → a short-lived, audience-bound JWT (the SA's credential)

# RBAC (the AUTHZ row, `00`): the SA's allowed verbs — separate from the identity
$ kubectl get role,rolebinding -n auth     # → what auth-svc may do (the token proves who; the RBAC decides what)

# The mTLS service cert = the per-pod leaf from Step 0 (CN = the workload, CA:FALSE, keyUsage digitalSignature)
# The mesh/CA issues it per-pod + rotates on a schedule (`06`; the leaf is short-lived, `03`)
```
> **The S2S call** = **mTLS**: each side presents its CA-signed leaf, each verifies the other's chain against the root it trusts. **The identity is the cert's CN/SAN** — a wrong-identity caller (CN ≠ the expected service) fails the chain check (`06`'s drill).

### Step 4 — the sensitive field (AES-256-GCM, DEK per record, KMS envelope, `02`/`07`)

```bash
# Generate a fresh DEK (AES-256) + wrap it under the KMS KEK (the envelope, `02`)
$ DEK_HEX=$(openssl rand -hex 32)
$ gcloud kms keys wrap -i <<<"$DEK_HEX" -o dek-wrapped.bin --key keK-main --key-ring auth-svc-keys
#    → the WRAPPED DEK is what you store in the row; the raw DEK never lives next to the data

# Encrypt the field (AES-256-GCM). NOTE: `openssl enc -gcm` DROPS THE TAG (`02`'s gotcha) —
# the capstone uses a library that emits the nonce + ciphertext + tag (the AEAD 4-tuple):
$ NONCE_HEX=$(openssl rand -hex 6)
$ printf 'ssn:123-45-6789' | libsodium-aead-encrypt \
      --cipher aes-256-gcm --key < dek-wrapped.bin --nonce "$NONCE_HEX" \
      > field.enc                 # emits { nonce(12) ‖ ciphertext ‖ tag(16) }
# row = { nonce, ciphertext, tag, wrapped-DEK, kek-id }   ← NEVER the raw DEK bytes

# The rotation unit is the DEK, not the row: re-wrap the DEKs under a new KEK, data untouched (`07`)
$ gcloud kms keys re-wrap dek-wrapped.bin --key keK-main-v2 --key-ring auth-svc-keys
```

### Step 5 — the consumers + the JWKS endpoint (the pin, `04`/`07`)

```bash
# A consumer verifies the JWKS key + pins the accepted algs + rejects alg:none (`04`'s checklist)
$ jose jwk pub --input jwks.json --kid 2026-10     # pick the key by kid
$ jose jwt print --input token.jwt --verify --jwk jwks.json --alg EdDSA   # reject anything not EdDSA
# The pin (the load-bearing check, `03`'s alg-confusion): the verifier only accepts the pinned
# alg set — `none` is rejected, and a HS256-as-EdDSA confusion is rejected.

# Expose the JWKS (the capstone's /.well-known/jwks.json is the Step-2 JWK, with kid)
$ jose jwk json --input jwt-pk.pem --kid 2026-10   # the public key, as the JWKS serves it
```

**The `jose` CLI is the "JWKS tool" this project names** (`jose`, `oauth2-cli`, or the IdP's own endpoint). **`cosign`** is the sibling for *image/manifest signing* (`06`/`03`'s "a digest check of the signed manifest").

---

## Deliberately cause (the *list from the spec, with the exact trigger)

1. **Leak the signing key.** Take `jwt-sk` out of the KMS → *every token it signed is forgeable.* **Trigger the `07` drill:** demote-to-verify-only → new keypair + new `kid` → old tokens verify for the max access life → retire. **The blast radius: past/present/future tokens. If it was the *root CA*, the overlap *doesn't exist* — re-issue the workload CA + leaves.**
2. **Replay a refresh token.** Use refresh token A → get B (A revoked) → **re-send A** → the IdP's `refresh_token_reuse` → **the whole family is killed, re-login forced** (`04`). *The rotation is the detector; the family-kill is the response.*
3. **Hit a service with the wrong identity.** A S2S call presenting a cert whose **CN ≠ the expected service** → the mTLS chain check **rejects on the SAN mismatch** (`06`). *A spoofed IP can't spoof the identity — the cert says who you are.*
4. **Swap an envelope key mid-write.** Re-wrap some DEKs under `keK-v2`, then **demote the old KEK before the re-wrap count hits zero** → **a record still under the old KEK can't be read → reads broke on a partial rotation** (`07`). *Staged rotation: the old KEK stays decrypt-only until all DEKs are migrated.*
5. **Run a bad `--verify` with `alg:none`.** Craft an **unsigned token** (`alg:none`, empty signature, `sub:"admin"`) and hit a consumer → **it must reject** (`04`/`03`'s alg-confusion). *If your verifier honors the header's alg, you have the vulnerability. The pin + the `none` rejection is the fix.*

---

## The one-diagram payoff (the whole system, the wall map)

```
                user ──argon2id(01)──► auth-svc ──Ed25519 in KMS(04/07)──► access JWT(5min) + refresh(rotate)
                                                                                      │ JWKS(04/07)
                consumer ◄──verify(pinned alg + iss/aud/exp/jti)── public half ───────┘
                                                                            
                2nd service ──mTLS(per-pod cert from CA, 06)──► auth-svc
                                                                 │ workload CA (03, in KMS, 07)
                2nd service ◄──S2S call verified by CN/SAN + RBAC(06)──────────────────┘
                                                                            
                DB row: { nonce(12) ‖ ciphertext ‖ tag(16) ‖ wrapped-DEK ‖ kek-id }  ← AES-GCM(02)
                              │                                          │
                              │                                          └── KEK in KMS (07); DEK wrapped, never raw
                              └── the row NEVER holds the key bytes (07's load-bearing rule)
```

---

## Exit criteria for the capstone

- [ ] You can **state the six decisions and the *why*** (the decision log), each tied to a folder.
- [ ] You can **run the CA + leaf + `CA:FALSE`/`keyUsage` check** (Step 0) and **explain the `-extfile`.**
- [ ] You can **generate an argon2id hash at the production cost** (Step 1) and **name the constant-time compare.**
- [ ] You can **build the signing key + JWKS and walk the "signing key leaked today" rotation** (Step 2 + the `07` drill).
- [ ] You can **issue a k8s *bound* SA token + the RBAC split** (Step 3) and **say why not the legacy Secret.**
- [ ] You can **encrypt a field with the AES-GCM 4-tuple + wrap the DEK** (Step 4) and **call out the `openssl enc -gcm` tag gotcha.**
- [ ] You can **verify a token with a pinned alg + reject `alg:none`** (Step 5 + `jose`).
- [ ] You can **run all five "deliberately cause" drills and name the *specific* failure each exposes.**
- [ ] You can **walk a panel through the threat model** (the five threats → the six decisions → the five drills) **without notes.**

You've reached the end. Go back to `00-mental-model` and re-read *one* folder end-to-end — the one that felt least solid. That's the folder you're weakest on, and it's the one a panel will pick.
