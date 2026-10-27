# 07 — Key Management: KMS, HSM, Envelope Encryption, and Rotation

**Folder:** `07-key-management/`

Every primitive in this project rests on a *key*. This folder is **who holds the keys, how they're protected, and — the part nobody tests — how you *rotate* them without dropping in-flight traffic.** The rule that's the whole topic: **never store the key next to the data it protects.** Violate that and every encryption in 02/03 is "encrypted in name only."

---

## Teach first: the key hierarchy, and *where each key lives*

The *envelope pattern* (02's KEK/DEK, 03's CA/leaf, 06's workload cert) all reduce to **one** hierarchy. Draw it once and the rest is *operations on this shape*:

```
        ┌───────────────────────────────────────────┐
        │  Root of trust  (HSM / KMS *root key)     │  ← the ONE key whose leak opens *everything
        │  - signs the workload CA (06)             │    (every cert it ever signed)
        │  - wraps the KEKs                          │
        │  - NEVER leaves the HSM in usable form     │
        └───────────────────────────────────────────┘
             │ wraps
             ▼
        ┌───────────────────────────────────────────┐
        │  KEK (Key Encryption Key)  in the KMS     │  ← rotated on a *schedule; re-wraps the DEKs
        │  - symmetric (AES-256) or asymmetric (RSA/ECC)
        └───────────────────────────────────────────┘
             │ wraps
             ▼
        ┌───────────────────────────────────────────┐
        │  DEK (Data Encryption Key), *per-record    │  ← what actually encrypts the *field (02)
        │  - fresh per record/table; *short-lived use
        └───────────────────────────────────────────┘
             │ encrypts
             ▼
        ┌───────────────────────────────────────────┐
        │  Data  (the AES-GCM ciphertext, 02)       │  ← lives in the DB; *never with the key
        └───────────────────────────────────────────┘
```

> ***The load-bearing rule (the one sentence this folder is about):* ***the *DEK that *encrypts the data *lives *outside the data's storage boundary, *wrapped by the *KEK, *which is *held by the KMS/HSM.** *The *row in the DB holds *the nonce + ciphertext + tag (02) — ***never the DEK bytes.*** *That *separation is *what "not storing the key next to the data" *means, *concretely.

### HSM vs. KMS — *the two custodians (name which you mean)

| | ***HSM (Hardware Security Module)** | ***KMS (Key Management *Service)** |
|---|---|---|
| *What it *is* | *a *physical (or virtual) *box that *generates + *holds keys *in a tamper-resistant boundary; *key ops happen inside | *a *cloud/hosted service *that *wraps an HSM or a *FIPS-validated module; *you call its API to *wrap/unwrap/sign/verify* |
| *The key *lives in* | *the *HSM's secure *memory (an *asymmetric private key *never *leaves it; *a *symmetric key *can't be *exported) | *the KMS's backing (an *HSM or a *cloud *key store; *the KMS *API is the *interface) |
| *The *operation model* | ***"the key does *its work *in the box"** (a *sign *call *returns *a signature, *not the key) | ***the same, *via API** (a `kms:sign` *returns a sig; `kms:encrypt` *returns *a wrapped blob) |
| *When you *use it* | *a self-hosted, compliance (a FIPS-validated HSM) *case | *the default for *cloud (AWS KMS, *GCP Cloud KMS, *Azure Key Vault) |

> ***The mechanism that *makes both *safe (the *one that *a panel will *press):* ***a *private key / a *symmetric key *never *materializes as *plaintext outside the *boundary.** *You *call "sign this", *you get *a signature back — ***you never get the key.** *That's *why the *hierarchy works: *the KEK/DEK *bytes can be *moved (as *wrapped blobs) *but the *usable form is *confined to the HSM/KMS. *The threshold:* *a *system where the DEK *bytes *sit in your app's memory / *a .env / *a DB *row* *is *a *system where *a single *leak *breaks the *envelope. *The HSM/KMS *boundary is *what *prevents that.

**The *command shape (a senior *runs these against a KMS, not a *file):**

```bash
# GCP Cloud KMS: *a key *ring + a key (an AES-256 wrapping key)
$ gcloud kms key-rings create data-keys --location us-east1
$ gcloud kms keys create keK-main --key-ring data-keys --location us-east1 \
      --purpose encryption

# *wrap a DEK under the KEK (the *envelope, 02): *the *DEK is generated *in the KMS, *wrapped out
$ gcloud kms keys wrap <dek-file> --key keK-main --key-ring data-keys --location us-east1
#    → *the *wrapped DEK *is what *you store next to the data (the *nonce+ciphertext+tag, *02)

# AWS KMS (the same shape, *different CLI):
$ aws kms create-key --key-usage ENCRYPT/DECRYPT --description "field encryption KEK"
$ aws kms encrypt --key-id <KEK-arn> --plaintext < dek.raw --query CiphertextBlob
```

**The *Vault *secret manager (the *other* *custodian — for *the non-KMS secrets):**
```bash
# *a *client secret, a *DB *password, a *HMAC key (01) *live *here, *not in code / *a .env
$ vault write -field=password secret/db/prod 'pgpass-…'
$ vault kv get secret/oauth/client   # → *the client secret (05), *pulled *at runtime, *never committed
```
> ***The split (the *two custodians, one rule):** ***the KMS/HSM *holds the *key *material (a signing key, a KEK); the *secret *manager *holds the *application secrets (a client secret, a DB *pass). *Neither *lives *next to the data it *protects. *A *leaked .env *breaks the app secrets; *a *leaked KMS *boundary is *the *root-of-trust *incident (03).**

---

## Envelope encryption — *the *concrete data path (02 *made operational)

The *capstone's *sensitive field (08) *is this, *step by step:

```
WRITE (encrypt a *field):
 1. generate a *fresh DEK (AES-256)                     ← *the data key, *per record
 2. encrypt the *field *with the DEK → *ciphertext + a *nonce + a GCM tag (02)
 3. *wrap the DEK *under the KEK *in the KMS            ← *the *envelope (KEK *never touches *the field)
 4. store { nonce, ciphertext, tag, wrapped-DEK, kek-id } in the *DB row   ← *the DEK bytes *never stored raw
 5. *the KEK *stays *in the KMS (07); *the wrapped DEK is *all the *row holds

READ (decrypt a *field):
 1. read the *row → *unwrap the DEK (KMS *unwrap *under the KEK)  ← *the DEK *materializes *only inside the KMS boundary
 2. AES-GCM *decrypt + *verify the tag (02)              ← *a *tampered record *fails here
 3. the *plaintext *never *lives *next to the key (the DEK is *a transient KMS object)
```

> ***Why the *DEK is *per-record (the *blast-radius *threshold, 02's *threshold):*** ***one *leaked *DEK *opens one record; *one *leaked *KEK *opens *every record it *wrapped.** *The *per-record DEK *is *the *blast-radius control: ***you *keep the *KEK *stable + *rotated on a *schedule, *and *you *accept *the *small cost of *storing one *wrapped-DEK *per record. *The *rule: ***the *unit of *key *rotation is the DEK, *not the row — *you *re-wrap the DEK, *you don't *re-encrypt the data.**

---

## Key *rotation — the *thing nobody tests, and *how you do it *without dropping traffic

**Rotation = *issue *a new key, *migrate, *retire *the old, ***while the *old one is *still *valid for the *in-flight *work it's *doing.*** The *word for *that *overlap is ***staged rotation** (a.k.a. *zero-downtime *key rollover.

### *The *three *rotation *objects (a *panel will ask which you're *rotating)

| *Object* | What rotates | *The *unit of *migration* | *The *drill (08's *drill log) |
|---|---|---|---|
| ***A *signing key** (04/03, *the JWKS key) | *a *new keypair + *a new `kid` | *new tokens use *the new key; *the JWKS *lists *both; *consumers *pick up the new `kid` *within the cache TTL | *the "the *signing key *leaked *today" drill (04's *5-step + 03's) |
| ***A *workload / mTLS *cert** (06/03, *the leaf) | *a *new leaf *cert, *re-issued *by the CA | *the *old leaf *stays valid *until it *expires; *the *new leaf is *issued + *pushed *by the mesh/CA | *the "a *workload cert *outlives *the *rotation" drill (06) |
| ***A KEK** (02/07, *the *envelope top) | *a *new KEK in the KMS | ***re-wrap the DEKs *under the new KEK** (the *DEKs are the *unit; *the data is *untouched); *the *old KEK *stays *decrypt-only *until *all DEKs are *migrated | ***the *KEK-rotation drill *below (the *one *a panel *will walk you through) |

### *The KEK-rotation drill, *in full (the *exact *sequence, *the L6 *answer)

```
1. *create a new KEK' *in the KMS
2. *for every DEK *still *wrapped under the old KEK: *re-wrap the DEK under KEK'
     (the *KMS *unwrap-old → *wrap-new; *the *DEK bytes move, *the *data does *not)
3. *mark the old KEK "decrypt-only" (a *status, *in the KMS) — *it can still *unwrap *the DEKs *in flight
4. *after 100% of DEKs *are *re-wrapped: *demote the old KEK to "archive" (a *retired, *decrypt-only)
5. *the *new KEK' is now the "active" KEK; *new records *wrap under it
   *the *overlap window is *steps 2–3: *the old KEK *stays *valid-for-decrypt *until the *migration *completes
```

> ***The *threshold (the *number that *governs the window):*** ***the *overlap = the *time it takes to *re-wrap *every outstanding DEK** *— *bounded, *not infinite. *You *know it's *done *when the *count of DEKs *still under the old KEK *hits zero. *A *panel will ask **"what if you *skip step 3 (you *demote the old KEK *too early?)"** → ***a record *whose DEK is *still *wrapped under the old KEK *can't be *unwrapped → *you *broke *reads. *That's *the "swapped an *envelope key *mid-write" failure (08's *deliberate *list.

**The *same *shape, *applied to the JWKS *signing key (04/03/07, *the *other *rotation a panel will probe):**
```
1. *generate a new keypair + new `kid`
2. *add the new *public key to the JWKS (the JWKS now *lists *the new + *the old)
3. *start signing *new tokens with the *new key; *the *old tokens *still verify *under the old key
4. *wait out the *max access-token life (04's 5–15 min) — *the *overlap window
5. *retire the old key from the JWKS (a *consumers' *cache TTL *covers the *transition)
```
> ***The *JWKS-vs-KMS *interaction (the *cross-ref a panel will *name):*** ***the JWKS is *the *public-key *distribution; the KMS *holds the *private *signing key. *You *rotate the *key in the KMS, *the JWKS *updates, *the consumers' *cache *refreshes *within the TTL. *If the *cache *outlives the *retirement, *you *have a *rotation that *didn't *happen (04's *stale-cache failure, 03's *leaf lifetime.

---

## *The secret *manager — *the *non-KMS half (where *the *app secrets *live)

*KMS *holds the *key material; *a *secret manager (Vault / *cloud SM / *k8s external-secrets) *holds the *application secrets. *The *split:
- ***Client secret (05, a *server-to-server credential):*** ***in the secret manager, *pulled at runtime, *never in code / .env / a *commit.**
- ***DB password, *HMAC key (01), *any shared secret:* *the secret manager, *versioned, *with *access = *the *RBAC *row (00.
- ***What *never *goes in the secret manager:** *a KMS *private key (that's the KMS's job), *and *the DEK *bytes (that's the *envelope, *02).

> **The threshold:** ***a secret manager *is for "a *secret *that a *process needs, *held by a *human/team, *with *an owner + *a rotation *schedule." *A KMS *is for "a *key *whose *usable form *must *never *materialize." *If you're *storing a *symmetric DEK *as a "secret", *you've *already *broken the *envelope (02's *rule) — *the DEK *belongs *in the KMS, *the *wrapped form *in the data *row.

---

## *Fit-to-project: *where *this *is the capstone's *spine

The capstone (08) *has *every key in this folder:
- ***The *JWKS *signing key** (04/03) → ***in the KMS/HSM**, *rotated *with the JWKS *drill *above.
- ***The *root CA + the workload CA** (03/06) → ***the HSM *root*, *the workload CA *in the KMS, *the *leaves *short-lived + *rotated (06.
- **The KEK* (02/07) → ***in the KMS**, *a *schedule-rotated *envelope top, *the *DEKs *per-record.
- ***The *client secret + the DB pass* (05) → ***in the secret manager**, *pulled at runtime.

**The *one *decision that *ties it *together (a *panel will ask "which key is *the root of *trust?"):**
- ***The HSM *root key** (the *top of the *hierarchy, *the *one whose leak opens *the *whole system). *Everything *below it (the workload CA, *the KEKs) *is *derived *trust (03's *chain. **The *threshold: ***the root is *the *decade-scale key; *the workload *leaves + the KEKs are *the *rotated, *short-lived ones. *You *rotate the *leaves *and the *KEKs *constantly; *you *rarely *touch the *root.**

---

## *Thresholds and tradeoffs *summary

| *Decision* | *Guidance* |
|---|---|
| ***Where the KEK *lives* | ***the KMS/HSM; *the *usable form *never *materializes outside *the boundary. *Never a .env / *a DB *row.** |
| ***The DEK** | ***per-record, *wrapped under the KEK; *the *row holds {nonce, ciphertext, tag, wrapped-DEK} — *never the DEK *bytes. |
| ***The signing key** | ***in the KMS; *the *public half *in the JWKS; *rotated *with the JWKS *drill. |
| ***The root CA** | ***the HSM *root, *decade-scale; ***the workload CA** *in the KMS, *quarterly; ***the leaves** *short-lived (06. |
| ***The *app secrets** | ***the secret manager (Vault / cloud SM / *k8s external-secrets), *versioned, *a *RBAC-gated *read. *Never code / .env / a commit. |
| ***The *rotation unit** | ***the DEK (envelope), *the JWKS key (signing), *the leaf cert (workload) — ***never the data. *The data *is *untouched; *the *envelope *changes. |
| ***The *overlap window** | ***bounded = *the time to *re-wrap *all outstanding DEKs (KEK) / *the *max access-token *life (JWKS) / *the *old leaf's *expiry (workload). *You *know *it's done *when the *count *hits zero. |

---

## *Failure modes you *must *deliberately *cause (the *drill *log)

1. ***The "the *signing key *leaked *today"** (04/03/07, *the HSM incident):* *the JWKS key *leaks. ***The *5-step *drill: (1) *demote the leaked key to *verify-only, (2) *new keypair + new kid, (3) *keep the old for in-flight (the *overlap = *max access life), (4) *retire, (5) *kill *any leaked refresh *families. ***The *blast radius: *every token *signed by it (past/present/future. *The KMS *drill: *if the *root CA *leaked, *you *can't *just rotate — ***you *have to *re-issue the *workload CA *and the *leaves (the *root-of-trust *drill, 03.
2. ***"Swapped an *envelope key *mid-write"** (07, *the *KEK rotation *half-done):** *re-wrap some DEKs *under the new KEK', *then *demote the old KEK *before *all DEKs are *migrated. ***A record *whose DEK is *still under the old KEK *can't be read → ***reads *broke on *a *partial rotation. *The *fix: ***staged rotation — the *old KEK *stays decrypt-only *until the *re-wrap *count *hits zero.
3. ***"Leaked the KMS *root"** (the *worst case, *the root-of-trust incident):* *the HSM *root *key *leaks. ***The *sequence: *immediately *invalidate the *workload CA *it signed, *re-issue the CA, *re-issue *all the leaves (06), *and *re-wrap the KEKs *under a *new root. *A *root *leak *is *the *one *where the *overlap *doesn't *exist — *you *lose the *anchor (03.
4. ***"A *secret in the .env"** (the secret-manager failure):* *a client *secret / a DB *pass *in code or a .env. ***A single *leaked .env = *the *whole app secret. *The *fix: ***the secret manager, *pulled at runtime, *a RBAC-gated read (00's *authz *row).
5. ***"Rotated the KEK, *the JWKS *cache *stale"** (the *JWKS-vs-KMS *failure, 04/03/07):** *rotated the signing key *in the KMS, *the JWKS *updated, *but a consumer's *cache *outlives the *old key's validity → ***a *valid token *is rejected (or a *retired key's *token *is still accepted. *The *fix: ***a bounded cache TTL + *refresh-on-`kid`-miss (04.
6. ***"A *wrapped-DEK *stored raw"** (the *envelope *failure, 02/07):** *the DEK *bytes *stored in the DB *row *next to the ciphertext. ***a single-row *leak = ciphertext + key = plaintext. *The *fix: ***the row *holds only the *wrapped DEK (the KEK *unwrap *is the only way to get the DEK, *inside the KMS.

---

## *The L5/L6 *lens: *what panels probe

| *Panel probe* | *The refute they're hunting* | *The artifact that *stops it* |
|---|---|---|
| ***"Where does the key *actually *live?"** | ***"in a config / a .env." *No boundary.** | ***The KEK + the *root CA are *in the KMS/HSM; *the *usable form *never materializes outside the boundary.** *The DEK *bytes *never live next to the data — *the row holds *a *wrapped DEK. *That's *"never store the key next to the data" *made concrete.** |
| ***"Walk me through a *KEK rotation."** | ***"I re-encrypt everything." *No *the *unit.** | ***I don't *re-encrypt the data.** *The DEKs are the *unit: *I generate a new KEK', *re-wrap each DEK *under it, *stage the old KEK as *decrypt-only *until *all DEKs *are re-wrapped, *then *archive it. *The *overlap *window is *the re-wrap *count; *the data *is untouched.** |
| ***"What's the *root of trust? *What if *that leaks?"** | ***"I'd rotate it." *No *the *root case.** | ***The root *key (in the HSM) *is the anchor; *a root leak *is the *one case *where the *overlap *doesn't exist** — *I *invalidate the *workload CA it signed, *re-issue *the CA + the leaves (06), *and *re-wrap the KEKs under a *new root. *I *rarely rotate the *root (decade-scale); *the leaves + KEKs *are the rotated, *short-lived ones.** |
| ***"HSM or KMS? *What's the *difference?"** | ***"They're the same." *No boundary.** | ***The HSM *is the *physical/virtual boundary where the key's *usable form *never leaves; the KMS *is the *API + the custody layer *over it.** *I *pick a KMS *for the cloud (it *wraps an HSM), *or a FIPS-validated HSM *for self-hosted. *The *principle is *the same: ***the key does its work *in the box, *not in my app.** |
| ***"Which is the *rotation *unit — the data or the key?"** | ***"I re-encrypt the rows." *No *the envelope.** | ***The DEK (envelope), *never the data.** *I *re-wrap the DEK; *the data *is untouched. *The *unit of rotation *is *a key that *wraps a data key, *not the data itself. *This *is the "rotation *without dropping in-flight traffic" *question (00.

> ***The meta-skill:** for *any "is *this key *managed *right?", *run the *4-part check:*** ***Does the key *materialize as *plaintext in *my app (it *must not)? / *is it *held by a KMS/HSM *boundary? / *is the rotation *unit a *key (the DEK) *and *not the data? / *is there a *bounded *overlap window + a *count that *tells me *when it's done?*** ***If you *can't produce *all four, *you've been "storing a key" *instead of "managing *a key in a *boundary."**

---

## Cross-refs (two topics interacting → name the sibling)

- ***The JWKS key *rotation** → `04-jwt` (the `kid` + the *cache TTL) *and `03` (the *key sizes / the *leaked-key *drill).
- ***The workload cert *rotation** → `06-service-accounts` (the per-pod leaf, *the mesh/CA *that *issues it) *and `03` (the *root/intermediate/leaf hierarchy).
- ***The KEK/DEK envelope** → `02-symmetric-encryption` (the GCM *field, *the per-record DEK, *the nonce+tag storage).
- ***The secret manager *the client secret** → `05-oauth-oidc` (the *server-to-server credential) *and `06` (the RBAC *row that *gates the *read).
- ***The "root-of-trust" *incident** → `03` (the CA *chain) *and `06` (the *workload identity it *anchors).
- ***Every drill *here* → `08-capstone` (the *runbook's *rotation section + the *deliberate-failure list.

---

## *Exit criteria for this folder

- [ ] You can ***draw the hierarchy** (HSM *root → KEK → DEK → data) *and *say *which key *lives where *and *what *never materializes.
- [ ] You can ***name the HSM-vs-KMS *difference** (the *boundary where the key does *its work vs the *API/custody layer).
- [ ] You can ***walk the KEK rotation** *as **re-wrap the DEKs, *stage the old as decrypt-only, *bounded *overlap = *the re-wrap *count, *the data *untouched.**
- [ ] You can ***walk the JWKS key rotation** *as **new keypair + new kid, *the JWKS lists *both, *the overlap = *max access *life, *the cache TTL *covers the *transition.**
- [ ] You can ***state the "root-of-trust" *drill** *for a *leaked HSM *root (invalidate the CA, *re-issue the CA + leaves, *re-wrap the KEKs — *the *one case *with no overlap).
- [ ] You can ***put each secret in the right custodian:** *the KEK/root CA *in the KMS/HSM, *the client secret + DB pass *in the secret manager, *never in code / .env / a *row next to the data.

Next: `08-capstone` — *all of it, *assembled: the *decision log + the *single-file runbook + the *deliberate-failure list.
