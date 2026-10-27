# 02 — Symmetric Encryption: AES, Modes, IVs, and MACs

**Folder:** `02-symmetric-encryption/`

One key, two directions: **encrypt with K, decrypt with K.** This is the *fast* half of "hide the bytes" (00's stack) — and it's where 80% of real data-at-rest actually gets encrypted. But three mistakes live here: **choosing the wrong mode**, **reusing an IV**, and **encrypting without authenticating.** Get all three and you have a system that's "encrypted" and still fully readable / forgeable.

---

## Teach first: three separate decisions, all called "encryption"

People say "we encrypt with AES" and mean three different things. Split them:

1. *The cipher (AES-128 / AES-256)** — the raw block function. **You almost never use raw AES.** Raw AES is a **block cipher** (16-byte blocks, 16-byte ciphertext blocks). You use it *inside a mode*.
2. *The mode (GCM / CTR / CBC)** — how you chain blocks and handle your **arbitrary-length** message + a **nonce/IV**. **The mode is where the security actually lives.**
3. *The integrity (MAC / AEAD tag)** — proof the ciphertext wasn't tampered with. **This is a *separate* guarantee from confidentiality**, and most incidents are missing it.

> **The one-line that sorts it:** "AES" is the *engine.* "GCM" is the *vehicle* that also does *the integrity check* — you want **AEAD** (authenticated encryption) when possible. "The IV" is what makes **two identical messages produce different ciphertext** (so an attacker can't pattern-match). The **key** is what you actually keep secret — **and you must never store it next to the data it protects** (07).

### The modes, and which one you pick

| Mode | What it gives you | The failure it hides | Verdict |
|---|---|---|---|
| **AES-128/256-GCM** | Confidentiality **+ integrity** (AEAD, produces a 16-byte auth tag) | **IV reuse is catastrophic** (two messages, same key + IV → an attacker recovers the XOR of the two *plaintexts*). | **The default.** Use GCM, not "AES alone." |
| **AES-CTR** | Confidentiality only (a *stream* — XOR a keystream) | **No integrity at all.** You *must* add a MAC (Encrypt-then-MAC) or it's malleable. | Fine *if* you MAC it; otherwise it's the "encrypted but forgeable" trap. |
| **AES-CBC** | Confidentiality (a *padding* mode, PKCS#7) | **Padding-oracle attacks** + no integrity. **Deprecated for new work.** | Don't pick it; it's legacy. |

> **Threshold — the modern default.** **AES-128-GCM** for *most* data; **AES-256-GCM** when (a) the data **outlives the decade** (it'll be attacked with better hardware / a leaked key over time), or (b) you're **under FIPS 140-2/3** (which has historically *only* approved AES-192/256, not 128, and GCM is the approved mode). **128-bit GCM** is **not** "half as secure" — it's the *right* default; 256 is for *long-lived / compliance* cases, not for making 128 "faster."

### The IV / nonce — the non-obvious half

- **GCM's "IV" is a 12-byte *nonce*.** The rule that's in the RFC and kills people: **never reuse a nonce with the same key.** One reuse → the *authenticity* of *all* messages under that key collapses (an attacker can forge a valid tag).
- **CTR's IV** is a 16-byte value, incremented per block (or XORed with a per-block counter). Reuse of the *same counter under the same key* = **keystream reuse** = the two plaintexts XOR together (the "two-times-secure" cipher — *exactly* the 1990s "one-time pad broken" failure).
- **The mechanism:** random 12 bytes for GCM (store them *next to* the ciphertext — they're not secret). Deterministic (counter) for CTR. **Both are stored in plaintext with the ciphertext** — the *nonce is not a secret*, the **key** is.

> **The concrete storage format (what you actually write to disk / DB):**

```
record = version(1 byte)
       ‖ nonce(12 bytes, random, GCM)
       ‖ ciphertext(n bytes)
       ‖ tag(16 bytes, GCM auth tag)
```

You keep **4 things together** (version, nonce, ciphertext, tag) but **exactly one secret** (the key). The nonce and tag are *public* — that's what "AEAD" means.

---

## Worked example: a real `aes-256-gcm` IV + auth tag

```bash
# 32-byte key (AES-256), 12-byte random nonce, encrypt "ssn:123-45-6789"
$ KEY_HEX=$(openssl rand -hex 32)
$ NONCE_HEX=$(openssl rand -hex 6)
$ printf 'ssn:123-45-6789' | openssl enc -aes-256-gcm -K "$KEY_HEX" -iv "$NONCE_HEX" | base64
# NOTE: `openssl enc -gcm` does NOT emit the tag (the gotcha below)
```

**The `openssl enc` gotcha (the thing that bites people):** `openssl enc -aes-256-gcm` **does not include the authentication tag in the output** — it's a *known `enc` limitation.* So a `openssl enc` GCM round-trip **silently drops the AEAD guarantee** (it only gives you confidentiality). **The senior move is a library that emits the tag** (libsodium, Go's `crypto/aes`+`gcm`, a JS `WebCrypto` with `aead`). If you're forced to `openssl`, **encrypt with GCM *then* separately attach a HMAC** (Encrypt-then-MAC) — you've re-implemented the tag by hand. **Name this gotcha when you build the capstone's encrypted field (08); it's exactly the kind of detail a panel probes.**

**The libsodium / WebCrypto shape that *does* include the tag:**

```
# What a correct AEAD record looks like (the 4-tuple, 02's "teach first"):
nonce:      c3a1f9…  (12 bytes, random, NOT secret, stored in plaintext)
ciphertext: 4f2b9d…  (n bytes, the encrypted field)
tag:        9a02ee…  (16 bytes, the GCM *auth tag* — what "encrypted AND authenticated" means)
key:        (NEVER stored with the record — it lives in the KMS, 07)
```

**What you can *prove* with that tag:** tamper with **one byte** of the ciphertext and GCM's tag check **fails** (the whole record rejects). That's the **integrity** guarantee. Without the tag, a **bit-flip** in the ciphertext just *garbles* the plaintext at that position — the record "decrypts" to near-garbage and *you can't tell it was tampered with.* **This is why "encrypted but forgeable" is a real state, not a hypothetical.**

---

## MAC vs. encryption — the two jobs

These are *separate guarantees* and conflating them is the "I encrypted it, so it's safe" mistake:

| Job | Primitive | What it proves | The missing piece without it |
|---|---|---|---|
| **Confidentiality** (hide it) | AES (any mode) | No one *without the key* can read it | If the block is *tampered*, CBC/CTR just *corrupt* the output; **you don't know** |
| **Integrity + authenticity** (it's the real one, from a party with the key) | **MAC** (HMAC, 01) or the GCM **tag** | It wasn't modified, and it came from someone with the key | If you *only* encrypt, an attacker *can* modify the ciphertext and it will "decrypt" to garbage — no alarm |

> **The combined primitive is AEAD.** GCM *is* AES + a MAC fused into one tag. If your cipher is *not* AEAD (raw AES-CBC, CTR), you **Encrypt-then-MAC**: encrypt, then `HMAC(key2, ciphertext)` and store the MAC. **Never** MAC-then-Encrypt (that's malleable — padding-oracle, 01's sibling failure). **The order is load-bearing: Encrypt *then* MAC.**

---

## At-rest vs. in-transit — where symmetric encryption actually runs

The *same* primitive, two different deployment contexts:

- **In-transit:** TLS (the transport). Your "encrypt the API response" is *already* TLS — you don't add application-layer symmetric encryption on top for *transport*. **Don't double-encrypt the network path.**
- **At-rest:** the data **on disk / in the DB / in object storage** (08's sensitive field, the DB backups, the volumes). This is where **AES-GCM under a KMS envelope key** lives (07). **In-transit TLS does *not* protect at-rest data** — a stolen DB volume is a *plaintext-or-GCM* read.

> **Threshold — the decision that's actually a *question*, not a default.** "Do I encrypt this field at rest?" → **YES** if it's **PII / a *field* the *row* is about** (the capstone's `ssn`, `card`, `api_key`). **NO** if it's already covered by **disk-level** encryption *and* the *whole* volume is the boundary (you *would* be double-encrypting). **The rule: encrypt the *field* when the *field* is the secret; rely on volume encryption when the *whole volume* is the boundary. When in doubt, field-level GCM — it's cheap and it's the senior default.**

---

## KEK — the key that encrypts the keys (envelope, preview)

**KEK = Key Encryption Key.** The top of the key hierarchy (07 develops it fully):

```
data-encryption-key (DEK)  →  encrypts the *field*   (per-record or per-table)
        ↑ wrapped by
key-encryption-key  (KEK)  →  lives in the *KMS/HSM* (07)   (NEVER leaves the KMS in usable form)
```

**The mechanism — *envelope encryption* (the hybrid pattern, 00):** you generate a **DEK** (a fresh AES key), **encrypt the field with it**, then **encrypt the DEK with the KEK** (which only the KMS can unwrap). **The KEK never touches the field directly.** This is the "asymmetric to move a fresh symmetric key, symmetric to encrypt the bulk" pattern — the single most-repeated structure in this project. (07 has the full KMS command set; here just know the *shape*: **a DEK you use, a KEK you *can't* read, a *wrapping* relationship between them.**)

> **The reason it's a "key that encrypts the keys":** you can **rotate the KEK** (07) *without* re-encrypting every record — you **re-wrap** the DEKs under the new KEK. The data (encrypted with the DEKs) is *untouched*; only the *envelope* (the wrapped DEK) changes. **This is "rotation without dropping in-flight traffic" (00's 3am question), at the *encryption* layer.**

---

## Fit-to-project: where symmetric encryption shows up in *this* system

1. **The sensitive DB field (08):** a user record's `ssn` / `card` → **AES-256-GCM**, a fresh **DEK** per record or per table, **enveloped under the KEK in the KMS** (07). Stored as the **4-tuple** (version, nonce, ciphertext, tag) *without* the key. **The `openssl enc` GCM tag gotcha is *the* thing to call out when you build it.**
2. **The DB volume / disk encryption** (at-rest, the *second* layer under field-level) — you rely on the *infrastructure* (LUKS, cloud EBS) here and *don't* add app-layer encryption for the *transport* (TLS already does it).
3. **The KMS envelope (07):** the **KEK** is *never* in your app's memory; the **DEK** is *unwrapped inside the KMS/HSM boundary* (or, in a low-grade setup, your app fetches the DEK bytes from the KMS, which is the *weaker* variant — 07 distinguishes them).

> **The threshold on *this* project:** the **DEK** is **per-record** (so one *leak* doesn't open the whole table) but the **KEK** is **stable + rotated on a *schedule*** (07's rotation drills). *A per-record DEK means you store one wrapped-DEK *row* per record; the KEK is the *one* thing that, if it leaks, opens *everything.* That's the "never store the key next to the data" rule made concrete.**

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| Cipher + mode | **AES-128-GCM** default; **AES-256-GCM** for long-lived / FIPS data. **AEAD, not raw AES.** |
| Nonce / IV | **12-byte random for GCM, *never reused* under a key, *stored in plaintext* with the ciphertext.** |
| Integrity | **Always** — the GCM **tag** (or Encrypt-then-HMAC if not AEAD). **Never MAC-then-Encrypt.** |
| At-rest vs. in-transit | **In-transit = TLS** (don't double-encrypt). **At-rest = field-level GCM** when the *field* is the secret. |
| Key hierarchy | **DEK** encrypts data; **KEK** (in the KMS, 07) wraps the DEK. **Rotate the KEK, re-wrap the DEKs, *don't* re-encrypt the data.** |
| Key storage | **The key is NEVER in the DB / next to the ciphertext.** It's in the KMS (07). |

---

## Failure modes you must deliberately cause

1. **The IV/nonce reuse (the *catastrophic* one).** Encrypt **two different messages with the same key + same GCM nonce.** The *auth tag* becomes forgeable for *all* messages under that key (an attacker can build a valid tag for *any* ciphertext). **The mechanism:** GCM's nonce feeds a counter; reuse → same keystream → `plaintext1 XOR plaintext2 = ciphertext1 XOR ciphertext2` (recover two plaintexts) *and* the tag structure collapses. **The fix:** random nonce per record (and if you *must* use a counter, the counter's top bits are a *unique-per-key* base, 02's "deterministic" note).
2. **Encrypt-without-authenticate.** Take **AES-CTR** (or CBC) *without* a MAC, flip **one bit** of the stored ciphertext, "decrypt." It *decodes* to near-garbage at that position — **no alarm, no rejection.** That's the "encrypted but forgeable" state. **Add the tag** → the *whole* record rejects.
3. **Store the key next to the data.** Put the **DEK bytes in the same table row** as the ciphertext. A **single-row read** (a *leaked* DB, a *sloppy* log, a *SQLi*) gives **ciphertext + key = plaintext.** The rule: **the DEK is wrapped by the KEK in the KMS (07); the *row* holds only the *nonce + ciphertext + tag.***
4. **The `openssl enc -gcm` silent tag-drop (the *tool* gotcha).** Use `openssl enc -aes-256-gcm`, "decrypt" a *tampered* ciphertext — `openssl` **doesn't verify** the tag (it isn't in the output) → it *decodes garbage* *successfully.* **The tool *lies* about being AEAD.** Use a library that emits the tag (02's libsodium/WebCrypto note), or hand-roll Encrypt-then-HMAC.
5. **The KEK / DEK rotation *half*.** Re-wrap the DEKs under a new KEK but **leave the *old* KEK *active*.** Now a **record encrypted under the *old* KEK** *can't* be decrypted (the old KEK is gone or demoted) → **you just broke *reads*.** **The rule (07's drills): *staged* rotation — the old KEK stays *valid for decrypt* until *all* DEKs are re-wrapped; only then demote the old KEK to *decrypt-only* / *archive.***

---

## The L5/L6 lens: what panels probe

| Panel probe | The refute they're hunting | The artifact that *stops* it |
|---|---|---|
| "Why GCM and not CBC?" | "You'll say 'GCM is newer.'" | "GCM is **AEAD** — it gives *confidentiality and integrity** (the 16-byte tag) in one primitive. CBC gives *only* confidentiality and is a **padding-oracle** + **no-tamper-detection** trap. GCM's *cost* is **nonce management** (never reuse); I use a **random 12-byte nonce, stored in plaintext** with the ciphertext." |
| "What's the *key* you're actually protecting, and where is it?" | "You'll say 'in a .env.'" | "The **field** is encrypted with a **DEK** (fresh, per-record). The **DEK** is **wrapped by a KEK** that lives in the **KMS** (07). The **row** stores **nonce + ciphertext + tag — *never* the DEK bytes.** *The DEK is the *only* *plaintext* secret in the whole path, and it's *inside the KMS boundary*." |
| "Walk me through a *rotation* of the top key." | "You'll say 'I re-encrypt everything.'" | "I **don't re-encrypt the *data*.** I generate a **new KEK**, **re-wrap** every **DEK** under it (the DEKs are the *units* of re-wrapping, not the rows), **stage** the old KEK as **decrypt-only** until *all* DEKs are migrated, then **archive** it. *In-flight reads keep working on the *old* KEK for the *duration* of the *migration* window." |
| "128 vs 256?" | "You'll say '256 is more secure, so 256.'" | "**128 is the default** (not 'half as secure'). I go **256** when (a) the data **outlives the decade** (long-lived = a *leaked-key-over-time* threat, not a *today* threat), or (b) I'm under **FIPS 140**, which *historically* approved **AES-192/256 only**. **The choice is a *data-lifetime + compliance* call, not a 'bigger = better' call.**" |
| "How do you *authenticate* the ciphertext?" | "You'll say 'the IV.'" | "The **auth tag** (GCM's 16 bytes), or **Encrypt-then-HMAC** if the cipher isn't AEAD. The **nonce/IV** is *public* — it *provides* nothing on its own. *The tag is the *integrity* proof; *the order* is *Encrypt then MAC** (MAC-then-Encrypt is malleable)." |

> **The meta-skill:** for *any* "is this encrypted *properly*?" — run the **5-part check**: *AEAD (tag?) / nonce policy (random, no reuse, stored?) / *order* (Encrypt-then-MAC?) / *key location* (KMS, not the row?) / *rotation shape* (re-wrap the DEKs, stage the old KEK). If you can't produce all five, you've been saying "encrypted" instead of "authenticated."

---

## Cross-refs (two topics interacting → name the sibling)

- **The GCM tag is a keyed construction** → `01-hashing` (HMAC is the *sibling* MAC primitive; GCM *fuses* the MAC into the cipher).
- **The DEK/KEK envelope** → `07-key-management` (the full KMS/HSM hierarchy + the *drills*).
- **The sensitive field in the capstone** → `08-capstone` (the *decision* + the *runbook command* that builds it).
- **The "never store the key next to the data" rule** → `07-key-management` (its *operational* form: the KMS boundary).
- **In-transit (TLS) vs. at-rest** → `03-asymmetric-encryption` (TLS *establishes* the session key; this doc's GCM is the *at-rest* layer, 03's RSA/ECC is the *handshake* that *agrees* the key).

---

## Exit criteria for this folder

- [ ] You can **sort a "cipher" into: the block function / the *mode* / the *integrity* guarantee** and say which one you're actually choosing.
- [ ] You can **state the GCM nonce rule** out loud: "12 bytes, random, **never reused under a key**, **stored in plaintext** with the ciphertext."
- [ ] You can explain **"encrypted but forgeable"** and name *the integrity primitive that cures it** (the GCM tag / Encrypt-then-HMAC).
- [ ] You can **draw the DEK/KEK envelope** and say which *bytes* live in the DB row and which *never leave the KMS*.
- [ ] You can **rehearse the *KEK* rotation** as **"re-wrap the DEKs, stage the old KEK as decrypt-only, don't re-encrypt the data."**
- [ ] You can call out **the `openssl enc -gcm` tag gotcha** without being prompted.

Next: `03-asymmetric-encryption` — the *other* half: public/private, signing, and the certs that say *who* holds the private key.
