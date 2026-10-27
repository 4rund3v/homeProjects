# 03 — Asymmetric Encryption: Public/Private, Signing ≠ Encryption, Certs, PKI

**Folder:** `03-asymmetric-encryption/`

The *slow* half of the fork (00's diagram). Two keys: a **public** one anyone can hold and a **private** one you keep secret. This is the primitive that solves the "how do two strangers agree on a secret / how do I *prove* I'm who I am without handing out a shared key" problem. The single most common mistake: **thinking "asymmetric encryption" and "asymmetric signing" are the same operation.** They are *opposites* of each other, and the confusion is how alg-confusion attacks (04) are born.

---

## Teach first: the public/private split, and why it exists

A **keypair** is two *mathematically linked* keys:

- **Public key (PK):** freely distributed. Anyone can use it.
- **Private key (SK):** kept secret. Only one holder.

The link is: **what the public key does, only the private key can undo — and vice versa** (in the two ways below). No *third* key exists. **That link is the whole primitive.**

> **The two *opposite* operations — name them or nothing after this is clear:**
>
> | Operation | Direction | Who holds the key | The *guarantee* it buys |
> |---|---|---|---|
> | *Asymmetric encryption** | **PK encrypts → SK decrypts** | *many* holders have the PK; *one* has the SK | **Confidentiality** — "only the SK holder can read it." |
> | *Asymmetric signing** | **SK signs → PK verifies** | *one* holder has the SK; *many* have the PK | **Authenticity + integrity** — "only the SK holder *made* this, and it's *exactly* this." |
>
> **Read that table twice.** Encryption *inverts* signing. In encryption, the *public* key is the *input* and the *private* key is the *unlock*. In signing, the *private* key is the *input* and the *public* key is the *check*.
>
> **The L6 one-liner (what 00's "many verifiers, one signer" means):** signing is **asymmetric in *trust*** — **one** party can *create* (the SK holder) but **unlimited** parties can *verify* (everyone has the PK). That's why **JWTs (04) are *signed*, not encrypted**: the IdP signs *once* with its SK, and *every resource server on the planet* verifies with the PK. **No shared secret, no call-back, unlimited verifiers.**

---

## RSA vs. ECC — same job, two curves of the same hill

Both implement the same *operations* (encrypt/decrypt, sign/verify). They differ in **how** and **how big the key is for the same strength.**

| | **RSA** | **ECC (P-256 / Ed25519)** |
|---|---|---|
| Math | Integer factorization (factoring a big number) | Elliptic-curve discrete log |
| Key size for **~128-bit** security | **3072-bit** | **P-256** (256-bit curve) |
| Key size for **~192-bit** security | **4096-bit** | **P-384** |
| Public key bytes | 384 B @ 3072, 512 B @ 4096 | **32 B** @ P-256 / **32 B** @ Ed25519 |
| Signature bytes | 384 B @ 3072 | **64 B** @ P-256 / **64 B** @ Ed25519 |
| Verify speed | Fast | Slow (ECC verify is slower than RSA verify) |
| Sign speed | Slow (SK op) | Fast |
| Verdict | Fine, *huge* certs. Still the default in TLS *handshakes* for compatibility. | **The modern default** for new keys. Tiny certs, tiny signatures — *matters for JWTs and X.509.* |

> **Threshold — key sizes (the exact numbers a panel wants).**
> - **RSA: 3072-bit minimum, 2048 is *deprecated* (factoring is getting cheap — it's the "outlives the decade" case, but today it's already *not recommended for new*), 4096 for *long-lived* keys / compliance.**
> - **ECC: P-256 (≈128-bit) is the *equivalent-strength* pick for most work; P-384 (≈192-bit) for long-lived; **Ed25519** is the modern *signing* workhorse (fast, small, a *signature* scheme first).**
> - **The mapping to remember: RSA-3072 ≈ P-256 ≈ 128-bit security. RSA-4096 ≈ P-384 ≈ 192-bit.** If someone says "2048 is fine," they're reciting a 2015 standard.

### The command that actually generates these (real openssl)

```bash
# RSA-3072 keypair (PEM)
$ openssl genpkey -algorithm RSA -pkeyopt rsa_keysize_bits:3072 -out rsa.sk.pem
$ openssl pkey -in rsa.sk.pem -pubout -out rsa.pk.pem

# ECC P-256 keypair
$ openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out ec.sk.pem
$ openssl pkey -in ec.sk.pem -pubout -out ec.pk.pem

# Ed25519 (the modern *signing* default)
$ openssl genpkey -algorithm ed25519 -out ed.sk.pem
$ openssl pkey -in ed.sk.pem -pubout -out ed.pk.pem
```

**Which one for this project?** The capstone's **JWKS signing key** (04/07) → **Ed25519 or P-256** (small certs, fast sign, and JWKS consumers fetch *public* keys — small = cheap to fetch and cache). The **mTLS service certs** (06) → **P-256** (X.509 works with any of them; P-256 is the *portable* pick, Ed25519 certs are *newer* to some chains).

---

## A real self-signed cert, and why "self-signed" is a *trust anchor*, not a shortcut

This is the **exact `openssl req` a panel expects you to *run*, not recite:**

```bash
# 1. a P-256 key for the CA (the root)
$ openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out ca.sk.pem

# 2. a *self-signed* CA cert (the root of the chain; CN = our CA)
$ openssl req -x509 -new -key ca.sk.pem -sha256 -days 3650 \
      -subj "/CN=proj-auth-crypto-internal-ca" -out ca.crt

# 3. a *leaf* key + a CSR (Certificate Signing Request) for a service
$ openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out svc.sk.pem
$ openssl req -new -key svc.sk.pem -subj "/CN=svc-auth" -out svc.csr

# 4. *sign* the leaf with the CA (this is the actual "issue a cert" step)
$ openssl x509 -req -in svc.csr -CA ca.crt -CAkey ca.sk.pem -CAcreateserial \
      -days 90 -sha256 -extfile <(printf "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment") \
      -out svc.crt
```

**What that last `-extfile` is doing (the part juniors copy-paste and don't understand):**
- `basicConstraints=CA:FALSE` — **this leaf is *not* a CA.** It can't sign *other* certs. A **leaf that's marked CA:TRUE is a *CA-imposter* — the "rogue CA" failure (below).**
- `keyUsage=digitalSignature, keyEncipherment` — *this* cert is *for* signing (JWT/mTLS-S2S-auth) and for encrypting (TLS-server). **`digitalSignature` = it's an *authentic* cert, not just a *confidentiality* one.** A cert with only `keyEncipherment` *can't* sign a JWT.

> **The "self-signed ≠ shortcut" reframe (the mechanism, not a vibe):** a **self-signed root** *is* a **trust anchor.** "Trusting this cert" = "I assert this *root's* public key is real and I extend trust down the chain from it." A *self-signed leaf (CN=svc, *signed by the CA*)** is **not** a trust anchor — it's a *leaf* in a chain whose trust *derives from* the root. **The difference a panel probes: "is this cert *trusted because it *signs itself*, or because it *chains to a root I hold*?"** A *leaf* that *also* self-signs (CN=svc with *its own* signature, no CA) is **trust = that one *issuer*** — a *single* point of trust that's *harder* to rotate than a chain (07).

---

## Certificate chains, CAs, and PKI — the "who signed the signer" ladder

A **chain** is: **Root CA → (Intermediates) → Leaf**. Each cert is **signed by the one above it.** The **trust** is *in the root* (which you hold / pin / are configured with). **Everything below is *derived* trust.**

```
Root CA (self-signed, you *trust* it directly)
   │ signed-by
   ├─ Intermediate CA (signed by Root)        ← optional layer
   │    │ signed-by
   │    └─ Leaf (CN=svc-auth, signed by Intermediate or Root)
   │
   └─ (another Intermediate) … (another Leaf)
```

- *The role of each layer:**
  - **Root** — the *trust anchor*. Self-signed. *You* hold it (or pin it / ship it in the trust bundle). **Roots are *rarely* rotated** (a new root = every client re-trusts).
  - **Intermediate** — the *operational* layer you *do* rotate (07). Short-lived, signed by the Root, and *only* the Intermediates need a *new* Root when you want to *revoke a family* without touching the Root.
  - **Leaf** — the *short-lived* service cert (06's mTLS: minutes-to-hours). **Leaves are *cheap* to rotate *constantly* — that's the *whole point* of mTLS (06).**

> **Threshold — the *rotation* hierarchy (this is 07's drills, previewed):** **Root: *never / decade.*** **Intermediate: *quarterly to annual.*** **Leaf: *short — *hours to days* (06's mTLS).** **The rule: *rotate the *leaf* *constantly*; the *root* is the *anchor* you *don't* move.** A *panel* asks "what *breaks* when I *rotate the *root*?" → *everything* (every *client* re-trusts) — *that's* why the root *rarely* moves.

### CAs, in one paragraph
A **CA (Certificate Authority)** is a *named party* whose *public key* you *trust*, and *which* signs *other* certs. A **PKI (Public Key Infrastructure)** is the *system* of CAs + their trust relationship + the *mechanism* (CRLs / OCSP, 04's sibling) for *revoking* a cert *before* it *expires.* *In this project: your `ca.crt` *is* the *CA*; the *system* of "leaf certs issued *per-pod* by *this* CA, *validated against the *root* the service is *configured with* = the *PKI*" (06).**

---

## Signing vs. encryption — the *opposite-direction* test (the panel's exact question)

*The question a panel asks to *refute* you:** "Explain *asymmetric signing* vs *asymmetric encryption* *to a junior.*"

*The answer that *stops* it (mechanism, not slogan):**

> "They're *opposite* *directions* of *the same* *keypair.*
> - **Encryption:** the *sender* uses the *recipient's* **public** key to *lock* it; *only* the recipient's **private** key *unlocks* it. *Many lockers** (everyone has the PK), *one unlocker** (only the SK holder). It *proves* **confidentiality.**
> - **Signing:** the *sender* uses their own **private** key to *make* the signature; *everyone* uses the sender's **public** key to *check* it. *One maker** (only the SK holder), *many checkers** (everyone has the PK). It *proves* **authenticity + integrity.**
>
> *Why signing is *the* *use* here (JWTs, 04):** you *need* *many verifiers** (every *resource* server), *one signer** (the *IdP*). *Encryption* would be *wrong* — *you* can't *encrypt a *JWT to "the *resource"* because there *are* *many* resources, and the *JWT* must be *readable* (the *claims* are *public* *data*; only the *signature* is the *guarantee*). So: **sign with the *IdP's SK, verify with the *IdP's PK (fetched *via *JWKS, 04).*"

> *The alg-confusion (04's *failure, previewed here):** if you *verify* a *JWT* *expecting* **RS256** (asymmetric, verify-with-*public-key*), but the attacker sends **HS256** (symmetric, *MAC* with the *public key as the *secret*)… a *broken* *verifier* *will* *accept* it **because the *attacker *"knows" *the *public key* (it's *public!) and *can* *forge the *HMAC. *The fix (04's checklist): pin the *accepted* *alg* and *reject* *none* and reject any *asymmetric↔symmetric* *switch.** *This* is *the* *exact* *attack* *that* *lives* *in* *the* *signing/encryption* *confusion.*

---

## Fit-to-project: where asymmetric shows up in *this* system

1. **JWT signing (04):** the **IdP's** keypair (**Ed25519 / P-256*) signs the access/refresh JWTs. **Every consumer** *verifies* with the *public* key *fetched* from the **JWKS** endpoint (**04/07**). *This* is **"many *verifiers, one *signer"* in the *system.**
2. **mTLS service-to-service (06):** each **pod** *gets* a **leaf** cert *from* the **CA** (the *system* root). *Two* *pods* do **mTLS*: each presents a *leaf, each *verifies the *other's* *leaf against the *root* they're *configured with. *The CA is the *trust anchor; the *leaf* is the short-lived, per-pod *identity.**
3. *The root CA + *its* *rotation* (07):** the **`ca.sk`** is the *one* *key* *whose* *leak* *opens* *the* *whole* *system* (every *leaf it *signed). **That's** *why* *it* *lives in the *HSM/KMS* (07) and *why* *rotation* is *the* *root*'s *only *real *drill.*
4. **TLS handshake (the *in-transit* key-agreement, 02's sibling):** the *server's* **ECC/RSA** key (or a *fresh* **ECDH* *ephemeral* key, the *real* *in-transit* secret) *agrees* the *symmetric* *session key* that *then* *does* the *bulk* *encryption.* *Asymmetric establishes, *symmetric* *transmits* (00's *hybrid* pattern, the *most-repeated* *structure** in this project).

> *The threshold on *this* project:** the *capstone* (08) *uses* **Ed25519 or P-256** for the *JWKS* key (*small* certs, *fast* sign) and **P-256** for the *mTLS* CA (portable X.509). *The root CA cert is *the* *one* *long-lived* *key* (decade-scale, *in* the HSM, 07); *everything* *below* it (intermediates, leaves) is *short-lived* and *rotated* on *schedule.**

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| Algorithm | **P-256 / Ed25519** for new keys (small, fast). **RSA-3072** only for *compatibility*; **4096** for *long-lived/compliance*. |
| Key size floor | **RSA-2048 is *deprecated* for *new* (factoring is getting cheap).** |
| Cert lifetime | **Root: *decade.*** **Intermediate: *quarter–annual.*** **Leaf (mTLS): *hours–days* (06).** |
| keyUsage | A *signing* cert needs **digitalSignature.** An *encryption* cert needs **keyEncipherment.** *Both* → *both.* A *cert with *only* keyEncipherment *can't* *sign a *JWT.* |
| basicConstraints | **CA:FALSE on *leaves*** (or a *rogue CA*, below). *CA:TRUE only on *actual CAs.** |
| Signing vs encryption | **Encryption = *PK-locks, SK-unlocks* (confidentiality, *many* *lockers*).** **Signing = *SK-makes, PK-verifies* (authenticity, *many* *checkers*).** **JWTs are signed, not *encrypted.** |

---

## Failure modes you must deliberately cause

1. *A leaf marked `CA:TRUE` (the *rogue-CA* failure).** A *service* leaf that *can* *sign* *other* certs. *An* *attacker* *who* *compromises* *that* *leaf* *now* *issues* *trusted* *certs* (a *new* *CA*). *The fix: `basicConstraints=CA:FALSE` on *every* *leaf* (the `-extfile` above). **Deliberate drill: *issue* a *leaf* *with* `CA:TRUE`, *try* to *sign a *sub-cert from it against the *root* chain → *observe* the *chain* *validates* it. *Then* *re-issue* with `CA:FALSE` and *watch* it *fail.**
2. *The alg-confusion attack (previewing 04).** Forge a **HS256** JWT with the **public key as the *HMAC secret* (which the *attacker* "knows," it's public )* and *send it to a *verifier that "expects RS256." A *broken* verifier *accepts* it. **Deliberate drill: *craft* the HS256-*as-RS256* token, *hit* your *JWKS* *verifier, watch it *reject* (your pinned- alg check, 04). *If it accepts, you have *the *vulnerability.**
3. *A leaf that *also* *self-signs* (the *single-trust-anchor* failure).** A *service* cert *signed by *itself* (no CA). *Trust = *that* *one* *issuer* → *harder* to *rotate than a *chain (07). **Deliberate drill: *issue* a *self-signed* *leaf* (no CA), *verify it against the *root* chain → *it's* *not in the *chain* (a *single* *point* of trust, not a *chain.*)**
4. **Rotating the *root* *mid-system* (the *everything-breaks* failure).** A *new* *root* *CA* = *every* *client* *re-trusts.* **The *drill (07's *root* drill): *issue a *new* *root, migrate the *intermediates* to the new root* *first* (the *overlap window), then *retire* the *old* root. *Never* "swap the root."**
5. **A *missing/weak* `keyUsage` (the *can't-sign* failure).** A cert with only `keyEncipherment` *used* to *sign a JWT* → the *JWT* *signature* *can't be validated as a *digital signature* (the cert *says* it's *not for *that). **Deliberate drill: *sign* a *JWT with a cert whose keyUsage is `keyEncipherment only, *verify* → *observe* the *keyUsage* *mismatch* rejection (or, in a *broken* verifier, *the* *silent* accept).**

---

## The L5/L6 lens: what panels probe

| Panel probe | The refute they're hunting | The artifact that *stops* it |
|---|---|---|
| "Explain asymmetric *signing* vs asymmetric encryption *to a *junior.*" | "You'll say 'public does *one, private does the other.' *No direction." | "They're *opposite.* **Encryption: PK-locks, SK-unlocks* (many *lockers, *one unlocker, confidentiality*). **Signing: SK-makes, PK-verifies* (one maker, many checkers, authenticity*). *JWTs* *are* *signed* because *I* *need* *many* verifiers, one *signer (the IdP); encryption would be *wrong* — the *claims* are *public *data, *only the *signature* is the *guarantee." |
| "RSA or ECC? Why?" | "You'll say 'ECC is *faster.'" | "*Same* operations, different *size. **P-256 ≈ RSA-3072 ≈ 128-bit.** P-256's *public* key is *32 B, RSA-3072's *is* *384 B. **I *pick P-256/Ed25519 for *new* keys (tiny certs, *fast sign, *cheap JWKS fetch), *RSA only for *compatibility, *4096 for *long-lived/compliance.** *2048 is *deprecated.*" |
| "What's a *certificate *chain, *really?* *Who* *trusts *whom?" | "You'll say 'CA signs cert.' *No hierarchy." | "*Root* (the *trust anchor, *I* *hold/pin it) *→ *Intermediate* (the *operational layer I *rotate, *signed by the *root) *→ *Leaf* (the *short-lived *per-service cert, *signed by the *intermediate/root**). *Trust* *derives from* the root; leaves are *cheap* to *rotate (06's mTLS; intermediates *rotate* quarterly; the root *rarely* moves (decade)." |
| "What if the *private signing key* leaked *today*?" | "You'll say 'rotate it.' *No *sequence, *no blast radius." | "**Blast radius: every *token/cert signed with it, *past/present/future, *is* *compromised* (04/06). **The *sequence (07's drill): (1) *immediately* *demote* the *leaked* key to *verify-only*, (2) *issue* a *new keypair, sign new tokens/certs with it, (3) *keep the *old key* *for verifying* *in-flight* tokens *for *the *max token lifetime, (4) *retire* the old key, (5) *if it was a *root CA*, the intermediates *must* *re-sign* under the *new root* (the *overlap *window, 07).**" |

> **The meta-skill:** for *any* "is this cert safe?" — run the **5-part check**: *what's the keyUsage (signing? encryption?) / is the leaf `CA:FALSE`? / does it chain to *the root I hold? / is the lifetime *short (leaf) or *stable (root)? / is it the *right algorithm (P-256/Ed25519 new, *not* RSA-2048)?* If you can't produce all five, you've been saying "a cert" instead of "a *leaf in a *rotatable chain.*"

---

## Cross-refs (two topics interacting → name the sibling)

- **The JWT signature** → `04-jwt` (the signed *claims*, verified via JWKS) and `01-hashing` (a signature is *asymmetric signing over a digest*; the digest's *integrity* is what the signature *protects*).
- **The mTLS leaf cert** → `06-service-accounts` (per-pod issuance, the CA-as-trust-anchor, the short leaf lifetime).
- **The root CA / key rotation** → `07-key-management` (the HSM boundary, the *root-rotation* drill, the *intermediate/leaf* rotation hierarchy).
- **The TLS handshake / ephemeral ECDH** → `02-symmetric-encryption` (asymmetric *establishes* the session key, symmetric *transmits*; 00's hybrid pattern).
- **The alg-confusion vulnerability** → `04-jwt` (the *pinned-alg* check; *this* doc's signing/encryption confusion is the *attack surface*).

---

## Exit criteria for this folder

- [ ] You can **state the *opposite-direction* table** (*encryption* = *PK-locks/SK-unlocks* = *confidentiality* / *signing* = *SK-makes/PK-verifies* = *authenticity*) **without notes.**
- [ ] You can **name the key-size threshold**: *RSA-3072 min (2048 *deprecated), 4096 *long-lived; P-256 ≈ RSA-3072 ≈ 128-bit.*
- [ ] You can **run the 5-command self-signed-cert flow** (`genpkey` → `req -x509` root → `req -new` leaf → `x509 -req -CA … -extfile CA:FALSE`) **and explain *what* the `-extfile` *is doing.**
- [ ] You can **draw the *Root → Intermediate → Leaf* chain** and say which *layer* *rotates on which *cadence (decade / quarter / hours–days).
- [ ] You can **name the *rogue-CA* failure** (a leaf with `CA:TRUE`) and *the fix (`CA:FALSE`).**
- [ ] You can **rehearse "the signing key leaked *today"** as the **5-step** *demote → new keypair → sign new → keep old for in-flight → retire (07)* sequence.

Next: `04-jwt` — where the *signing* primitive (03) meets a *standardized wire format* and the **claims** that carry *authz*.
