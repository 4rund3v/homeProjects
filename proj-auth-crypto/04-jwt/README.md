# 04 — JWT: Anatomy, Claims, JWKS, Rotation, and Revocation

**Folder:** `04-jwt/`

A **JSON Web Token** is a *standard wire format* for a *signed* (or *encrypted*) JSON object. It is **not itself authentication** — it's the *evidence* (00's "bearer evidence of authn") that a *third party* can *check* *locally* *without* *a* *phone* *call.* The whole security of a JWT rests on **two** things: **(1) the *signature* (03's *asymmetric* *signing* over *the* *claims), and *(2) the *claims* *being small, bounded (*exp*), and *verified* (*iss/aud*).** Get *either* *wrong* and the token *is* *a* *credential* *leak* *or* *a* *forgery* *vector.*

---

## Teach first: the three parts, at the byte level

A JWT is *exactly* *three* *base64url* *segments* *joined* *by* *dots*:

```
eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjIwMjYifQ.eyJzdWIiOiJ1c2VyLTQyIiwibmJmIjoxNzYwMDAwMDAwLCJleHAiOjE3NjAwMDMwMDAsImlzcyI6Imh0dHBzOi8vaWRwLmxhYi5leGFtcGxlLyIsImF1ZCI6ImFwaS1jb25zdW1lciJ9.sigBytes…
│                                              │                                             │
└──── HEADER (b64url) ─────┘      └──── PAYLOAD / CLAIMS (b64url) ─────┘    └ SIGNATURE
```

*Decode all *three* (real command, the *whole* *anatomy* *at* *once):**

```bash
$ TOKEN="eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjIwMjYifQ.eyJzdWIiOiJ1c2VyLTQyIiwibmJmIjoxNzYwMDAwMDAwLCJleHAiOjE3NjAwMDMwMDAsImlzcyI6Imh0dHBzOi8vaWRwLmxhYi5leGFtcGxlLyIsImF1ZCI6ImFwaS1jb25zdW1lciJ9.sigBytes…"

# header
$ echo "${TOKEN%%.*}" | base64 -d 2>/dev/null
{"alg":"ES256","typ":"JWT","kid":"2026"}
# payload (the *claims* — *all of them are *public; *only the *signature* *is* the guarantee
$ echo "$(echo "$TOKEN" | cut -d. -f2)" | base64 -d 2>/dev/null
{"sub":"user-42","nbf":1760000000,"exp":1760003000,
 "iss":"https://idp.lab.example/","aud":"api-consumer"}
```

### Header — *how* *it* *was* *signed* (the *alg* is *NOT* *trusted)

```json
{ "alg": "ES256", "typ": "JWT", "kid": "2026" }
```

- **`alg`** — the *signature* *algorithm* (03's *choice): **ES256** (ECC P-256 *signing), **RS256** (RSA), **EdDSA** (Ed25519), or **HS256** (symmetric HMAC, the *danger* *one* below).
- **`kid`** — **Key *ID: which *public key* to *use* to *verify.** This is *the* *rotation* *handle* (03/07): a *resource* *server* fetches the **JWKS** (below), *picks* the key by `kid`, *verifies. **When you *rotate* the signing key, you *issue a *new kid; *old tokens* *still* *verify* under the *old kid *during the *overlap window.**
- **`typ`** — almost always `"JWT."` *Cosmetic.*

> *The load-bearing *rule (03's *alg-confusion* attack, the *whole* *reason* *this* *section* *exists):** *the* *`alg`* *in* *the header* ***is* ***not* ***trusted.** *A* *broken* *verifier* *that* *"trusts" *the* *header's `alg`* *will* *accept an *attacker's *`alg:none`* (an *unsigned token, *accepted* *as* *a* *signed one) or *an attacker's HS256 *signed with the *public key as the *HMAC secret (03's *signing/encryption* *confusion). *The only *safe* *check (04's *checklist, below): pin *the* *accepted* *algorithms* (a whitelist), reject `alg:none`, *and* *reject* *any* *symmetric↔asymmetric* *switch. **Never** *"let* *the* *token* *choose* *its* *own* *verification method."*

### Payload — *the* *claims* (the *public* data, the *integrity* *is* *what the *signature protects)

| Claim | Meaning | The *check* *a* *verifier* *must* *run* |
|---|---|---|
| **`sub`** | **Subject** — *the* *unique* *user/machine* *ID* (00's *identity* *row) | *Never* *empty. *Stable* across sessions. |
| **`iss`** | **Issuer** — *which IdP* *made* *this* | **Must equal the *expected issuer, exactly* (a token for `idp-a` *must not* *verify at `idp-b`). |
| **`aud`** | **Audience** — *who this token is for* | **Must include the *receiving* *service.** (Prevents "token for *app A* *used* *against *app B.") |
| **`exp`** | **Expiry** (Unix sec) | **Must be > now, AND short-lived** (access: *5–15 min). |
| **`nbf`** | Not-before | Must be < now (a *delayed* *activation, *rare). |
| **`iat`** | Issued-at | For *replay* *reasoning (the *age of the token. |
| **`jti`** | *JWT ID* — *unique* *per* *token* | **The *handle for *revocation** (below). |

> *The one-line *that* *sorts it:** *the* *claims are *public* *data* (anyone who *reads* the token *reads* them — *that's* *why* 00 said "the *signature protects integrity, not *secrecy**). **You *do not* *put* *the* *secret* *in* *the claims** (a *password, a *DEK bytes, a *private key). **What you *do* *put in claims: *the* *identity* (`sub`), *the* *bounded* *lifetime* (`exp`), *the* *issuer/audience* *contract* (`iss`/`aud`), *and* *the* *authz data* *the* *resource* *consults* (a *role, a *scope, 05).**

### Signature — *the* *guarantee* (03's *asymmetric* *signing over header+payload)

**The signature is:** `ES256( base64url(header) + "." + base64url(payload), SK )`. **The verifier** recomputes it with the **PK** and checks **bit equality.** *Any change to *either* *the header or *the payload* → *the* *signature* *breaks** (that's *the* *integrity* *guarantee). *You cannot *tamper* *with a claim without *breaking the signature.**

> **The *`alg:none`** failure, the *concrete* *attack:* *an attacker* *crafts* a *token with `alg:none` (an *unsigned, *empty signature)* *and* *sends* it *to a *broken* *verifier* *that* *"honors the header." The verifier *skips* *signature verification entirely** → *the attacker* *sets* *any* *claim (`sub: "admin"`) *and* *it's* *accepted. *The fix is *not* "a good library" — it's *an explicit *whitelist of accepted algs + an *explicit* `none` rejection, *enforced* *before* *you* *touch* *the** *claims.**

---

## JWKS — *how* *a* *verifier* *gets* *the public key *without a *phone call

**JWKS = JSON Web Key Set: the *endpoint* *where* *the* *IdP publishes its *public signing keys.** This is *the* *mechanism* that *makes* *stateless* *JWT verification* *possible (00's *"proof* *without a *call") — *and it's* *the* *piece* *that* *breaks* *at scale* *if* *the* *cache* *outlives the *rotation window.*

```
GET /<realm>/.well-known/jwks.json
→ { "keys": [
     { "kty":"EC","crv":"P-256","x":"…","y":"…",
       "alg":"ES256","use":"sig","kid":"2026" },
     { "kty":"EC","crv":"P-256","x":"…","y":"…",
       "alg":"ES256","use":"sig","kid":"2025" }   ← the *old* key, *still* valid for *in-flight* tokens
   ] }
```

**The *verification sequence* (the *exact* *thing a panel wants you to *run):**

1. *Parse* the token's **`kid`** from the *header.*
2. *Fetch* (or *use the *cached*) **JWKS*, pick the key where **`kid` matches.**
3. *Recompute* *the signature* *with that PK* → *check.*
4. *Validate claims:* **`iss` == *expected*, `aud` *includes* *me, `exp` > now, `nbf` < now.**
5. *If any step fails → *reject.*

> *The cache *threshold (the *scale* *failure):** a JWKS cache *that* *outlives* *the old key's validity window* = *a* *rotation* *that* *"works" *on the IdP *side* but *still* *accepts tokens signed with a *retired* key (or *rejects* tokens signed with a *fresh* key, *during the transition). **The rule: a *bounded* *cache TTL** (*seconds to a *few minutes), *and a* *refresh* *triggered on a `kid` miss** (if the *token's* kid is not in the cache, *fetch now, don't *reject). **Rotate the key on the *IdP, the JWKS *changes, the consumer *must* *pick up the new kid within *the *TTL.**

---

## Access vs. refresh — the *two* *kinds of token, and *why* the split exists

**This is *the* *most* *probed* *question in the *whole* *project. Split it:**

| | **Access token** | **Refresh token** |
|---|---|---|
| **Lifetime** | **Short: 5–15 min** | **Longer: hours to a *day* (bounded) |
| **Revocable?** | **By *exp only** (stateless, no *central* *state) | **By *the IdP* (it *knows* *all of them)** |
| **Carries** | the claims (authz data, 05) | *just* *an opaque ID* (`jti`) to *the refresh grant* |
| **Held in** | *the API call* (Authorization: Bearer) | *the session* (a *httpOnly* cookie / a store), never *sent to the *API as *a Bearer |
| **Job** | *"I'm *here now, *do the thing"* | *"Give me a *new access token *without* *re-auth"* |

*The mechanism that *makes refresh *tokens *a theft-detector (the *L6* *detail, 00's *panel* *question):**
- *On a refresh, the client sends the **old* refresh token; the IdP* ***issues a new refresh token AND *invalidates the old one in the same step — a *rotation, not a re-issue. **Each refresh token is **usable exactly once.**
- **The *theft detection:** if *an* *attacker* ***stole* ***a refresh token* and *replays it* ***after** *the legitimate client already *rotated* it, the IdP sees *two different requests presenting the *same (now-invalid) token.* *That is *the replay signal.**
- **The *response (the *family* *invalidation, *not just the token):** treat a *replayed/stale refresh token as a *credential-compromise event — *invalidate the *entire* refresh chain for that subject (all outstanding refresh tokens), not just the one. **This is *"rotation as detection": *the rotation guarantee is what makes the replay visible; the response is to *kill the family.

> **The *threshold (the exact numbers a panel wants):**
> - **Access: 5–15 min.** A 24-hour access token *is not* "a slightly long expiry" — it's *a credential that *survives password resets and lockouts.*
> - **Refresh: *rotate on use, *max age bounded (≤ *24h–30d, *and on *replay → *invalidate the *family* (all outstanding for that subject).**
> - **The *one-line: **access *short, refresh *rotating + revocable, *replay = kill the *family.**

---

## Revocation — *why* "stateless" is a *choice, not a *property

**A JWT's security is its *signature + its exp.** *Nothing else. **If you want to *revoke a *specific token* **before it expires, the *stateless* *verify cannot do it** (it *has no state). *The two *kinds of "revocation":**

- **Implicit (by *exp): *the token just *dies at `exp. *No *central state. *This* *is* *why* *access tokens are *short** (00).
- **Explicit (by *jti / by *family): *a *list of *revoked jti* (a *denlist), *or the refresh-*family* *invalidation above.** The cost: *now the verifier *holds* *state* (a *denlist, or an *introspection call to the *IdP) — *which is *the* *stateful* *path* (05's *introspection).

> **The *tradeoff (00's *"proof without a call vs. with a *call"):**
> - **Stateless (JWKS + *local verify + *short exp):** *fast, *no revocation state, *but* *a leaked access token is *alive until exp. *Right when the *blast radius must be *small** (a *5-min access token *dies in 5 min.
> - **Stateful (introspection / a *denlist):** *you* *can* *revoke immediately, but *every request pays a *network call* *and* *the IdP is a *SPOF.* **Pick per endpoint, *not per system.** *The capstone (08): **access *tokens are *stateless* (JWKS, 5-min *life, *revocation via *exp + the *refresh-family* kill), *and the refresh grant is *stateful* (the *IdP *holds it, *so it can be *revoked on *replay.**

---

## Fit-to-project: where JWTs *are* the *system in *this* project

1. **The *login (08): **user *authn (01's argon2 *password check) → *the service *issues a *short access JWT (5 min, `sub`, `exp`, a *scope claim, 05) + a *rotating refresh JWT (opaque `jti`, *held in the *session). *The first *500ms of a login (00's panel question) *is this sequence, *plus the *constant-time password compare (01).**
2. **The *JWKS endpoint (08): *the service *publishes its *public signing key (the *03* P-256/Ed25519 *public key, *with a `kid`) at `/.well-known/jwks.json**. *Every* *consumer* *fetches* + *caches* *it. **The *rotation drill (07) is *a new key + a new kid, *the JWKS *lists both, *consumers* *pick up the new kid within *the TTL.**
3. **Service-to-service (06): *a service's *workload identity is *carried as a *signed assertion (a JWT, *aud set to *the target service), *verified against the *CA's JWKS. **Same *primitive, *different `sub`** (*a machine, not a *human).
4. **The *`aud` *binding (05): *a token issued for `outline` *must not be accepted by `other-app`. **The `aud` claim *is* *the binding.**

> **The *threshold on *this* project:** *the capstone's access token is **5 min, ES256/EdDSA, `iss`, `aud`, `sub`, `exp`, `iat`, a `jti`** (for the refresh-*family* revocation), *and a *scope claim (05).** *The refresh token is **an opaque `jti`-bearing JWT** (not a human-readable blob, *so it can be revoked/replayed-checked), *held server-side, *rotated on every refresh.*

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| Access token life | **5–15 min.** Never a *day. |
| Refresh token | **Rotating on use, bounded max age, *replay → *kill the family.** |
| Signature alg | **ES256 / EdDSA / RS256.** *Pin* the accepted set. **Reject `alg:none`.** |
| `kid` | **Must match the JWKS entry** the *verifier picks. *The rotation handle. |
| JWKS cache | **Bounded TTL (sec–min), *refresh on `kid` miss (don't reject a *new kid.** |
| Revocation | **Access: *by exp (stateless).** *Refresh: *by family-invalidation (stateful, *the IdP holds it.* |
| Claims | **Identity (`sub`), *lifetime (`exp`/`nbf`), *contract (`iss`/`aud`), *authz (a scope/role, 05).** *Never a *secret. |

---

## The *security* *checklist (what a senior verifies, *in order)

1. ***Pin* *accepted algs; *reject `alg:none`; *reject symmetric↔asymmetric* *switch. **(03's alg-confusion, *the #1 token attack.**
2. **`iss` == *the expected issuer* (exact *string match, *not "a valid IdP").**
3. **`aud` *includes *me (the receiving service is a *named audience.**
4. **`exp` > now **and `nbf` < now, **and `exp` *is short (5–15 min for access.
5. ***`jti`** is *present (so refresh-*family* revocation is *possible.
6. ***JWKS cache is bounded + refreshes on `kid` miss (a rotation *doesn't break consumers.
7. ***Refresh tokens rotate on use, replay → *family kill (04's theft-detection.

---

## Failure modes you must deliberately cause

1. ***The `alg:none` *forgery (03's preview): craft an **unsigned token** (`alg:none`, *empty signature, `sub:"admin"`), *send it to your JWKS verifier. **It *must reject.** *If your verifier *honors the header's alg, **you have the vulnerability.**
2. ***The HS256-as-RS256 confusion (03's *attack): *sign a JWT with **HS256 using the *public key as the HMAC secret (which the attacker "knows," *it's public), *header says `alg:RS256`** (a *forgery), *send it. *A broken verifier *accepts.* *Your pinned-alg check must reject.*
3. ***The stale JWKS cache (rotation *breaks at scale): *rotate the signing key (new kid, *the JWKS now lists *the new key), *hit the consumer with a *token signed by the *new kid *while its cache *still has only the old one. *A naive consumer *rejects a valid token.** *Fix: refresh on `kid` miss.*
4. ***The refresh replay (theft detection): *obtain refresh token **A** (login), *use A → get **B**, *A revoked.** *Re-send* ***A** *again (a *replay). *The IdP's `refresh_token_reuse` → the family *kills B + *all outstanding, *forces re-login.** *Deliberately do *the replay* *and *watch the family go.
5. ***The `aud` *cross-app (the *token-for-A-vs-B *bug): *issue a token with `aud:"app-A", *present it to `app-B`. **It *must reject on `aud`.** *The `aud` claim is the *binding — a *missing check is *cross-app credential leakage.*
6. ***A long access token (the *credential that *outlives a lockout): *issue an access token with `exp` + *24h, *then *lock the user out. *The *24h token *still works** (it's *stateless, *exp is its *only revocation). *That's* *the 5-min rule.*

---

## The L5/L6 lens: what panels probe

| Panel probe | The refute they're hunting | The artifact that *stops* it |
|---|---|---|
| "***Walk me through *the first 500ms of a login.**" | "You'll start at 'issue a JWT.' *No sequence." | **(1) *the KDF (argon2id) *re-runs at the *stored* cost, (2) *constant-time compare to the stored hash (01), (3) *on match: *mint an access JWT (5 min, ES256/EdDSA, `iss/aud/sub/exp/iat/jti` + a scope) *and a rotating refresh (opaque `jti`, *held server-side), (4) *deliver the access token in-band, *the refresh in a httpOnly cookie / store.** *Steps 1–2 are the *authn; 3–4 are the *token issuance. **500ms is the *KDF cost — that's why the KDF *cost* is the *login latency budget.* |
| "***What if the private signing key leaked *today*?**" | "You'll say 'rotate it.' *No sequence / blast radius." | "***Blast radius: every token signed by it (past/present/future) *is compromised.** **The 5-step sequence (07's drill, *03's): (1) *immediately demote the leaked key to *verify-only, (2) *issue a new keypair + new kid, (3) *keep the old key *for verifying in-flight tokens for the *max access lifetime, (4) *retire it, (5) *any *leaked refresh *family* is *killed by *family-invalidation, *not key rotation.** *The key rotation *doesn't* revoke *in-flight* access tokens — *their exp does.* |
| "***Explain asymmetric *signing vs encryption *to a junior.**" | "You'll say 'public/private.' *No direction." | "*They're *opposite directions of the same keypair.* **Encryption: PK-locks, SK-unlocks (many lockers, one unlocker, *confidentiality.** **Signing: SK-makes, PK-verifies (one maker, *many checkers, *authenticity).** *A JWT is *signed* (not *encrypted*) because I need **many verifiers, one signer** (the IdP), *and the *claims are public* *data — only the *signature is the guarantee.*" |
| "***Stateless JWT — so how do you revoke?"** | "You'll say 'can't.' *No the *two* kinds.* | ***Implicit: by exp** (a *5-min access *token just dies — *no central state, *that's the point). **Explicit: by jti / by refresh-family** (a *denlist or *introspection — *stateful, *the IdP holds the refresh grant). *I keep **access stateless (short exp = revocation-via-exp)** and **the refresh grant stateful (so *replay → *family kill**.* |

> **The meta-skill:** for *any* "is this JWT safe?" — run the **7-step verify checklist** (the *security checklist above): *pin the alg / reject none / check `iss` / check `aud` / check `exp`+`nbf` / check `jti` / check the JWKS cache TTL + refresh-on-miss. **If you can't produce all seven, you've been "checking the signature" instead of "verifying the *claims + the *algorithm + the *cache."**

---

## Cross-refs (two topics interacting → name the sibling)

- **The signature** → `03-asymmetric-encryption` (03's *asymmetric signing is *the* JWT's *guarantee; *its key sizes / alg confusion / JWKS are *here*).
- **The `alg` / alg-confusion** → `03` (signing vs. encryption) *and* *04's own *pinned-alg check.
- **The claims as *authz data** → `05-oauth-oidc` (the *scopes/roles on the *token, *the `aud` binding, the *refresh grant).
- **JWKS + key rotation** → `07-key-management` (the KMS/HSM *holds the signing key, *the rotation drill, *the JWKS cache TTL is *a rotation-window *issue).
- **The refresh grant / introspection** → `05` (stateful *revocation, the OAuth *refresh *flow).
- **A service's JWT as workload identity* → `06-service-accounts` (the *`sub` is a machine, *the `aud` is *the target service).
- **The login that mints it** → `08-capstone` (the *first-500ms sequence, *the full runbook).

---

## Exit criteria for this folder

- [ ] You can ***decode a real JWT** *into header/payload/signature* *and say *which claims you verify and *why (`iss/aud/exp/nbf/jti`).
- [ ] You can **state the *pinned-alg + `none`-rejection rule** and *name the **HS256-as-RS256** confusion attack.
- [ ] You can **describe the JWKS fetch/verify/`kid`-pick/cache-refresh sequence** and *say *what a *stale cache does.
- [ ] You can **state the access/refresh *thresholds:** *5–15 min access, *rotating refresh, *replay → *family kill.
- [ ] You can **explain *stateless vs. *stateful revocation** and *which one *this* system uses for *which token.
- [ ] You can **rehearse "the signing key leaked *today"** as the *5-step sequence + the *why-exp-doesn't-fix-it* note.

Next: `05-oauth-oidc` — where JWTs *get issued by a flow* and the *scopes become the *authz* data on them.
