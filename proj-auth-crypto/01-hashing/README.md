# 01 — Hashing: Digests, KDFs, and HMAC

**Folder:** `01-hashing/`

Three different things all get called "a hash," and confusing them is how a senior gets walked into a wall. **Cryptographic digest** (SHA-256), **password KDF** (bcrypt/argon2), and **keyed digest / MAC** (HMAC) are *different animals with different jobs*. Name which one you mean, or you'll be "hashing" the wrong thing.

---

## Teach first: the two kinds of "hash" and why the split is the whole topic

### A. Digests (integrity + lookup) — one-way, *not* keyed

A **digest** maps arbitrary bytes to a fixed-size fingerprint. The property you use: **you can verify, not reverse.**

- **Preimage resistance** — given `H(x)`, infeasible to find *any* `x'` with `H(x') = H(x)`. This is why a stored digest is "safe" to compare against.
- **Second-preimage resistance** — given `x` and `H(x)`, infeasible to find a *different* `x'` with the same digest. This is why you can't **tamper with a file** and keep the same fingerprint.
- **Collision resistance** — infeasible to find *any* two inputs with the same digest. This is the property attacks actually break (SHA-1's known collision).

> **The naming trick a panel uses:** preimage ≠ collision. A collision (two colliding inputs, *both chosen by the attacker*) is what breaks SHA-1. **Preimage resistance (given *one fixed* target, find *any* preimage) is what keeps password digests from being reversed.** Don't say "SHA-1 is broken so it can't be a password hash" — that's conflating the two properties. SHA-1's *collision* break doesn't directly give you a **preimage** for a stored password; the password-hash kill is *speed* (below), not collision.

### B. Password KDFs (slow on purpose) — *keyed by a salt*, stretched

A **KDF** (Key Derivation Function) turns **user input + salt** into a digest, but deliberately *stretched* so each check costs real CPU. **Passwords are not data you protect from eavesdroppers — they're secrets you protect from *offline brute force*.** That changes the tool: you want the *most expensive* one-way function you can afford, not the fastest.

- **The KDFs:** `bcrypt`, `scrypt`, `argon2` (winner for memory-hardness). **Not** `pbkdf2` *at modern cost* (time-only, not memory-hard — use it only if you must, at very high iterations).
- **The mechanism:** `argon2` is *memory-hard* — it forces the attacker to allocate GBs of RAM per candidate. A GPU/ASIC that hashes fast can't cheaply parallelize across RAM. **That's the specific reason argon2 beats bcrypt for the *asymmetric* case** (attacker with 100k GPUs vs. you on one box).

### C. Keyed digests / MACs (integrity *with a shared secret*)

**HMAC** = `H(key || message)`, iterated. It's a digest *plus* a shared key: **anyone with the key can compute the tag; without it, they can't forge one.** This is symmetric integrity (00's fork). **HMAC is not for passwords** (not slow, not salted-per-user) — it's for **message integrity + authenticity over a shared key** (API signing, Webhook signatures, GCM's internal MAC in 02).

> **The one-line that sorts all three:**
> - **Digest** (SHA-256): "are these bytes what I think?" — *integrity*, no key, fast.
> - **KDF** (argon2): "did this person actually know the password?" — *stretch*, salted, slow.
> - **HMAC**: "did someone with my secret key sign this message?" — *authenticity*, keyed, fast.

---

## Worked example: the byte-level truth

### A real SHA-256, and why `MD5` and `SHA-1` are *never* for integrity or signatures

```bash
$ echo -n "password" | sha256sum
5e884898da28047151d0e5bf064330c37d0b3a17f313a0c6e11b2c4d9e0f123...  # 32 bytes (256 bits)
```

- **SHA-256** (32-byte digest): the modern default. Use for **integrity** (file fingerprinting, Git commit IDs are SHA-1 → moving to SHA-256) and as HMAC's base.
- **SHA-512**: for larger digests / SHAKE; rarely the pick.
- **SHA-1**: **deprecated** — known collision (2017 SHAttered). *Never* for signatures or integrity.
- **MD5**: **dead** — trivial collisions (2^30 or so in practice for chosen-prefix). *Never*, not even "internal, we don't care" — the tool exists in every attacker's box, and "internal" is not a property.

> **Threshold — digest choice.** SHA-256 for any modern use. SHA-1 deprecated (collisions). MD5 **never** for integrity or signatures. If you must compare *integrity*, SHA-256. If you're doing **password storage**, ignore all of this and go to section B — none of the digests are password KDFs.

### A real password KDF, and what "cost 12" *actually* costs

```bash
# bcrypt — the $2y$ prefix is the OpenBSD variant; 12 = the cost (2^12 = 4096 rounds)
$ htpasswd -bnC 12 alice 'correct-horse-battery'
alice:$2y$12$abcdefghijklmnopqrstuv0123456789abcdefABCDEFabcdef:…

# bcrypt cost 12 ≈ 250ms on a modern single core
# bcrypt cost 10 ≈ ~60ms, cost 14 ≈ ~1s  (roughly ×2 per cost increment)
```

**What "cost 12" means in *your* seconds:** on the *user's* login it's a one-time ~250ms (fine). On an **attacker with a leaked DB** it's ~250ms *per guessed password*. If they've got a 10,000-GPU farm, that's still the multiplier — which is exactly why **argon2's memory-hardness** is the senior move: you're capping their *parallelism*, not just their *rate*.

> **Threshold — password KDF sweet spot.**
> - **bcrypt**: cost **10–14** is the band; **12 ≈ 250ms** is the target. Below 10 → too cheap (a GPU does millions/sec). Above 16 → login latency is hostile to real users.
> - **argon2id** (the modern pick): `m` (memory) ~ **64–256 MB**, `t` (time) ~ **3–6 passes**, `p` (parallelism) 1–4. It's **memory-hard**, so it's the *asymmetric*-defeat case. `argon2id` > `argon2i` (the "i" is generic-data, the "d" is password-data — **always use the `d`/`id` variant for passwords**).
> - **The rule:** the KDF cost is the **one knob you *should* raise** as hardware gets cheaper. A cost that took 250ms in 2019 takes 150ms in 2026 — *re-check the cost on hardware you actually run, not on your laptop.*

### A real salt, and why "random per user" is the mechanism

```
stored = argon2id( memory=64MB, time=4, parallelism=1,
                   salt=<32 random bytes, unique per user>,
                   input=user_password )
```

- **The salt is unique per user.** Its job is **not** to make the password "harder" — it's to make **two identical passwords store differently** and to **kill precomputed rainbow tables** (an attacker's giant table of `password → digest` is useless when the digest depends on a per-user 32-byte random value they don't know).
- **The salt is stored in plaintext next to the hash.** It's not a secret. What's secret is the *password*.
- **Per-user** (the load-bearing word). A *global* salt (one for the whole table) defeats the whole point — identical passwords collide in the attacker's table.

> **Failure mode — the missing salt / global salt.** If you ever see a hash table where two identical passwords have identical stored values, your salt is **global or absent**. A lexicographically-sorted hash table where adjacent rows match is the tell.

### A real HMAC — the *fast* keyed integrity

```bash
$ KEY=0123456789abcdef  # shared secret (hex)
$ MSG="transfer=42&from=alice&to=bob"
$ printf '%s' "$MSG" | openssl dgst -sha256 -mac hmac -macopt hexkey:$KEY
(stdin)= 7b9a2c…   # 32-byte tag
```

**HMAC = SHA-256 of the *keyed* message.** Two parties who share `$KEY` can check *authenticity* (the message came from someone with the key) + *integrity* (it wasn't modified). **No salt, no stretch — because it's a message MAC, not a password KDF.** Use it for **API signing** (SigV4), **webhook signatures** (GitHub), and inside **AEAD** ciphers (GCM's MAC is a keyed construction — 02).

> **Threshold — HMAC vs. KDF.** If the threat is **"an attacker with a shared key, forging a message"** → **HMAC** (fast). If the threat is **"an attacker with your DB, brute-forcing a password"** → **argon2** (slow). *Never* use a fast digest as a password KDF, and *never* use a slow KDF where you need a fast MAC on every API call.

---

## "Never roll your own" — the concrete, not a vibe

This is the single most senior-sounding thing in this folder, and it's *mechanical*, not hand-wavy:

- **Never** `SHA-256(password + salt)` and call it a KDF. That's a **fast digest** — the attacker's GPU hashes it at billions/sec. A "salted SHA-256" is the #1 real-world password-store failure. The fix is a *slow, memory-hard KDF* (argon2id) **or** a high-iteration count.
- **Never** home-brew an "integrity" scheme by XORing hashes or chaining MD5. There is no property that's *cheap* and *one-way* that's *keyed* and *preimage-resistant* that you can prove — the proofs (collision resistance, the **length-extension** property that let you build **HMAC** from SHA in the first place) are why the known constructions are the only safe ones.
- **Never** a **global secret "salt"** or a **constant pepper** for every user — that's the global-salt failure above. Per-user 32-byte random.
- **The concrete command that *is* "using the right thing":**

```bash
# The one command that's a defensible password store
openssl passwd -6 -salt "$(openssl rand -base64 16)" -iterations 500000 'correct-horse-battery'
#   ( -6 = SHA-512-based, -iterations is the stretch; argon2id via a library is the senior default)
```

> **Senior lens — "roll your own" is a *process* failure, not a code one.** The specific tell in review: the digest function is called on the password with a *constant* and *no* cost parameter, or the "hash" is a home-burned chain. The ask in code review: *"which KDF, what's the cost, where's the salt, is it per-user?"* Four questions that expose 90% of the bad password stores.

---

## Fit-to-project: where hashing shows up in *this* system

1. **Password storage (the login, 08):** user logs in → **argon2id** verifies the stored hash. *This is the KDF, not a digest.* (01's section B.)
2. **Integrity of the JWT payload (04):** the JWT's signature is an **asymmetric** signing over the header+payload (03) — but the *payload's* integrity at the byte level rests on the fact that *any* flip changes the signed digest. If you used a *symmetric* JWT (HS256), that's an **HMAC** (01's section C) — fast, but the key is shared with every verifier (00's fork: why 04 defaults to asymmetric).
3. **Service-account / image signing (06):** **cosign** signs a container image with an asymmetric key (03) and the registry's verification is a *digest check* of the signed manifest.
4. **A webhook / API signature (if you had one):** **HMAC** (01's section C) over the body with a per-app secret.

> **The threshold on your *own* storage:** the capstone (08) stores the password with **argon2id** and stores *another* field encrypted with **AES-GCM** (02). Notice they're **different** primitives doing **different jobs** — the password is *hashed* (one-way, to verify), the field is *encrypted* (reversible, to hide). **A junior's mistake: hashing something you later need to read, or encrypting a password (which then leaks if the key leaks — it's reversible).**

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| Digest for integrity | **SHA-256.** Never SHA-1 / MD5. |
| Password KDF | **argon2id** (memory-hard: `m`~64–256MB, `t`~3–6, `p`~1–4) — or **bcrypt cost 12** (≈250ms) if the stack predates argon2. |
| KDF cost target | **~250ms on *production* hardware.** Re-measure; it drifts down as CPUs get faster. |
| Salt | **32 random bytes, unique per user, stored in plaintext next to the hash.** |
| Message authenticity (shared key) | **HMAC-SHA256** — fast, not for passwords. |
| "Is it the right primitive?" | One-way to verify → **digest/KDF**. Reversible to hide → **encryption** (02). Both → don't mix the jobs. |

---

## Failure modes you must deliberately cause

1. **Recover a password from the store.** Try to reverse a **bcrypt/argon2** hash → you *can't* (preimage resistance). Now see what **salt reuse** does: two users, same password, *global* salt → identical stored values → a **rainbow table** attack is back on the table. Fix: per-user salt.
2. **Time the KDF.** Measure a login's *wall time* at your current cost. If it's **< ~100ms**, it's cheap enough that an attacker's farm is a real threat — **raise the cost** (or switch to argon2id).
3. **The missing salt.** Drop the salt → identical passwords collide. This is the failure a *leaked DB* turns into a *credential-stuffing* windfall.
4. **HMAC as a password store.** Store `HMAC(secret, password)` as the "hash." The `secret` is *shared* (a KDF should be per-user + per-input) and it's *fast* → brute-force wins. It's the wrong primitive for the job (01 C vs B).
5. **The "encrypted password."** Encrypt the password at rest, store the *key in the same table* → reversible → a DB leak gives you the plaintext (or a trivially-decryptable one). A password is *hashed*, not encrypted. (The *other* sensitive field in 08 is the one you **encrypt** — that's the reversible case, and it *should* be.)

---

## The L5/L6 lens: what panels probe

| Panel probe | The refute they're hunting | The artifact that *stops* it |
|---|---|---|
| "How do you store a password?" | "You'll say 'hash it' and stop." | "argon2id, `m`~64MB / `t`~4 / `p`~1, **per-user 32-byte salt**, ~250ms on prod hardware. It's *memory-hard* so a GPU farm can't parallelize the way it can against bcrypt. I re-measure the cost on the box it actually runs." |
| "SHA-256 vs. bcrypt — which for a password?" | "You'll say 'the stronger one.'" | "Different jobs. SHA-256 is a **fast digest** — an attacker's farm does it in billions/sec. bcrypt/argon2 are **slow, memory-hard KDFs**. A password store *must* be the slow one; a *file-integrity* check *should* be the fast one." |
| "Why salt? Is it a secret?" | "You'll call the salt 'a secret.'" | "The salt is **not secret** — it's stored in plaintext next to the hash. Its *only* job is to **break the precomputed table** and make **per-user** storage *independent*. The secret is the **password**." |
| "HMAC or a KDF for an API signature?" | "You'll reach for the KDF." | "API signature is a **fast, keyed, per-request** integrity check → **HMAC-SHA256**. A KDF is *slow, per-user* — wrong shape. I pick the primitive by the **threat + rate**, not by habit." |
| "Walk me through what happens in the first 500ms of a login." | "You'll start at 'bcrypt.'" | "(1) read the **row** (user + salt + cost + KDF type), (2) re-run **argon2id** at the *stored* cost, (3) **constant-time compare** to the stored hash (a timing oracle leaks "how many leading bytes matched"). **Step 3 is the one juniors miss — a non-constant-time `==` leaks.**" |

> **The meta-skill:** for *any* "is this hash safe?" question, run the **four-question check** — *which KDF / digest, what cost, where's the salt (per-user?), is the compare constant-time?* — and you'll never be caught saying "salted SHA-256" again.

---

## Cross-refs (two topics interacting → name the sibling)

- **KDF for passwords** → `08-capstone` (the login's argon2id step).
- **HMAC as symmetric authenticity** → `02-symmetric-encryption` (GCM's MAC is a keyed construction) and `00-mental-model` (the symmetric-vs-asymmetric fork: HMAC shares the key with every verifier; asymmetric doesn't).
- **Digest + asymmetric signature** → `03-asymmetric-encryption` (a JWT's signature *is* an asymmetric signing over a digest) and `04-jwt` (the claims whose integrity the signature protects).
- **Image/manifest signing** → `06-service-accounts` (cosign signs the image; verification is a digest check).

---

## Exit criteria for this folder

- [ ] You can **sort** any "hash" into **digest / KDF / HMAC** and say which *threat* it defeats.
- [ ] You can name the **four password-store questions** and answer them for a *specific* system.
- [ ] You can state, without notes: **"a salt is not a secret; a password is *hashed*, not encrypted."**
- [ ] You can **time** your KDF and say whether the cost is in the **10–14 (bcrypt)** or **250ms (argon2)** band on *production* hardware.
- [ ] You can explain why **SHA-1's collision break** is *not* the reason you don't store passwords with SHA-1 (that's **speed** — a *preimage/brute-force* problem, not a collision one).

Next: `02-symmetric-encryption` — the reversible half of the "hide the bytes" job.
