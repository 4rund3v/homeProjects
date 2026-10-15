# How TLS Actually Works

> This is the centerpiece. Read it slowly and you'll be able to explain TLS aloud to a
> peer — handshake, key exchange, cipher suites, records, resumption — without notes.
> Everything is mechanism-first: *what happens, in what order, and why that order.*

---

## 0. The three problems TLS solves

Before any protocol, be precise about the threats. Every TLS design choice traces back
to one of these:

```
   Client ──────────── packets ────────────▶ Server
             (crossing untrusted networks)

  1. EAVESDROPPING  — a router/ISP/host on the path reads the plaintext.
                      → solved by ENCRYPTION (nobody else can read it)

  2. TAMPERING      — an attacker flips bytes in flight ("send $1" → "send $1000").
                      → solved by INTEGRITY (a MAC / auth tag detects any change)

  3. IMPERSONATION  — you think you're talking to api.example.com, but it's an attacker
                      running a fake server (DNS spoof, rogue Wi-Fi, BGP hijack).
                      → solved by AUTHENTICATION (certificates prove the server owns
                        the name, because a CA vouched for it)
```

Encryption without authentication is worse than useless — you can have a perfectly
private conversation with the wrong person. **This is why the certificate exists** and
why the very first hard problem in TLS is "how do I know who I'm talking to," not "how
do I scramble bytes."

Two more goals fall out of a real design:

```
  4. FORWARD SECRECY — if the server's long-term private key is stolen LATER, past
                       recorded sessions must stay unreadable.
                       → solved by EPHEMERAL key exchange (the single most important
                         modern property; §3 explains it in depth).

  5. PERFORMANCE     — a handshake before every request would be too slow.
                       → solved by RESUMING sessions (§6).
```

Keep these five in your head. When you later wonder "why does TLS do X?", the answer is
almost always one of them.

---

## 1. The 30-second mental model

TLS has **two protocols stacked**:

```
  ┌─────────────────────────────────────────────┐
  │  APPLICATION DATA  (your HTTP bytes)        │   ← what you care about
  ├─────────────────────────────────────────────┤
  │  RECORD PROTOCOL                            │   ← frames + encrypts + integrity
  │  (splits data into records, encrypts each)  │
  ├─────────────────────────────────────────────┤
  │  HANDSHAKE PROTOCOL                         │   ← runs ONCE, sets up the keys
  │  (agree version, cipher, keys, identity)    │
  └─────────────────────────────────────────────┘
```

- The **handshake** runs first and produces shared secret keys. It's expensive (round
  trips, crypto) but happens rarely.
- The **record protocol** then carries every subsequent byte, encrypted and integrity-
  protected with those keys. It's cheap and runs constantly.

Think of the handshake as "agreeing on a shared lock code once," and the record protocol
as "using that code to seal every envelope afterward."

---

## 2. Why asymmetric crypto, then symmetric

Here's the core trade every TLS explanation must land:

| | Asymmetric (RSA, ECDH) | Symmetric (AES, ChaCha20) |
|---|---|---|
| Key pair | public + private | one shared secret |
| Speed | ~100–1000× slower | fast (hardware-accelerated) |
| Good for | establishing identity + a shared secret over a hostile channel | encrypting bulk data |

Asymmetric crypto is *too slow* to encrypt your whole HTTP session. But symmetric crypto
needs both sides to already share a key — and you can't just send that key in the clear
over the untrusted network (eavesdropper reads it, game over).

**The resolution:** use asymmetric crypto *once* to agree on a symmetric key, then use
symmetric crypto for everything else. TLS is essentially a machine for doing exactly
this.

The analogy that lands in interviews:

> Asymmetric crypto is like a **padlocked drop box**: anyone can drop a message in
> (they know the public lock), but only the holder of the private key can open it. It's
> great for a single handoff but clunky for a long conversation.
>
> Symmetric crypto is like a **shared codebook**: once you both have it, talking is
> fast — but you needed a secure way to agree on the codebook in the first place.
>
> TLS uses the drop box to securely deliver the codebook, then you switch to the
> codebook.

---

## 3. The TLS 1.3 handshake, packet by packet

TLS 1.3 is what modern servers and clients negotiate in 2026. Learn this version; treat
1.2 as legacy (§[`tls-1.3.md`](tls-1.3.md) covers the delta).

### 3.1 The ASCII timeline

```
 Client                                                    Server
   │                                                          │
   │  ┌──────────────┐ ClientHello                            │
   │  │ version:1.3  │ random, key_share (client ECDHE pub)   │
   │  │ cipher suites│ SNI, ALPN, supported_groups            │
   │  └──────────────┘                                        │
   │─────────────────────────────────────────────────────────▶│
   │                                                          │
   │   ServerHello                                            │
   │   ┌──────────────┐  chosen suite, random,                 │
   │   │ key_share    │  server ECDHE pub                      │
   │   │ (server pub) │                                        │
   │   └──────────────┘                                        │
   │◀─────────────────────────────────────────────────────────┤
   │        {EncryptedExtensions}                              │
   │        {Certificate}         ─┐                           │
   │        {CertificateVerify}    │ all encrypted              │
   │        {Finished}             │ with handshake keys        │
   │◀─────────────────────────────────────────────────────────┤
   │                                                          │
   │  {Finished}                                              │
   │─────────────────────────────────────────────────────────▶│
   │                                                          │
   │  ═══════ Application Data (encrypted) ═══════════════════│
   │◀────────────────────────────────────────────────────────▶│
```

Notice: **one round trip** before application data. TLS 1.2 needed two. That's the
headline improvement of 1.3.

### 3.2 ClientHello

The client opens by saying "here's what I can do":

- **`legacy_version` / supported_versions** — it offers TLS 1.3 (and possibly lower).
- **`random`** — 32 bytes of client randomness. This is *mixed into the key derivation*
  so every session is unique, and it prevents replay of a recorded handshake.
- **`key_share`** — the client generates a **fresh ephemeral ECDH keypair** and sends the
  *public* half here. This is the crucial 1.3 optimization: it guesses which key-exchange
  group the server likes and sends its public key immediately, saving a round trip. (If
  the server disagrees, it sends a `HelloRetryRequest` and the client resends — rare.)
- **`cipher_suites`** — an ordered list of AEAD suites it supports (e.g.
  `TLS_AES_256_GCM_SHA384`, `TLS_CHACHA20_POLY1305_SHA256`).
- **`supported_groups`** — which elliptic curves it can do (`x25519`, `secp256r1`, …).
- **`server_name` (SNI)** — the hostname it *thinks* it's connecting to
  (`api.example.com`). Needed because one IP/port hosts many TLS sites, each with its own
  cert. SNI is sent in the clear (see privacy note in §8).
- **`ALPN`** — Application-Layer Protocol Negotiation: "I speak `h2` and `http/1.1`, which
  do you want?" This is how HTTP/2 gets selected over the same TLS connection.
- **signature_algorithms** — which signature schemes it accepts for the certificate.

### 3.3 ServerHello

The server commits to choices:

- **`supported_versions` = 1.3** (or a `HelloRetryRequest` if it needs a different group).
- **`random`** — 32 bytes of server randomness, also mixed into key derivation.
- **`key_share`** — the server's ephemeral ECDH public key.
- **chosen `cipher_suite`** — one of what the client offered.

At this instant, **both sides can compute the shared secret** (see §4) and derive the
handshake keys. But they haven't *authenticated* each other yet — that comes next.

### 3.4 The encrypted flight: EncryptedExtensions → Certificate → CertificateVerify → Finished

The server now sends four messages, **all encrypted** under the freshly derived handshake
keys (in TLS 1.2, the certificate was in the clear — this was a privacy leak 1.3 fixed):

- **`EncryptedExtensions`** — negotiated extensions that aren't part of the handshake
  crypto (e.g. ALPN result).
- **`Certificate`** — the server's certificate chain (end-entity + intermediates; roots
  are assumed known by the client). See [`certificates-and-pki.md`](certificates-and-pki.md).
- **`CertificateVerify`** — a **digital signature** by the server's private key over a
  transcript of the handshake so far. This is the proof of possession: "I hold the private
  key matching the public key in that certificate." Without this step, someone could
  replay a certificate they don't own.
- **`Finished`** — a MAC over the entire handshake transcript, keyed by the handshake
  secret. This is the tamper-detection seal: if any handshake byte was modified in flight
  (a downgrade attack trying to force a weaker suite), the `Finished` won't verify and the
  client aborts.

**Where encryption begins:** the moment the server derives handshake keys, everything
after `ServerHello` is encrypted. So the server's identity (its certificate) is *already*
private to an eavesdropper in TLS 1.3 — a big deal, because in 1.2 you could see which
site someone visited even without decrypting anything.

### 3.5 The client's Finished, then application data

The client verifies the whole flight:

1. **Certificate chain** — does it chain to a root it trusts? Is it in date? Does the
   `SAN` match the SNI it asked for? (§[`certificates-and-pki.md`](certificates-and-pki.md))
2. **CertificateVerify signature** — does the server actually hold the private key?
3. **Server Finished** — is the transcript intact (no tampering/downgrade)?

If all pass, the client derives its own keys and sends its **`Finished`**. Now both sides
hold:

- **handshake traffic keys** (used for the handshake messages themselves),
- **application traffic keys** (used for the actual data), and
- **resumption secrets** (to come back faster next time, §6).

Application data flows, encrypted under the application keys, in **records**.

If verification *fails*, the client sends a TLS **alert** (`bad_certificate`,
`unknown_ca`, `certificate_unknown`, …) and closes — see §7 for alerts vs. failures.

---

## 4. Key exchange: ECDHE and Perfect Forward Secrecy

This is the part most people hand-wave. Don't. It's the single most important security
property of modern TLS.

### 4.1 ECDHE in plain language

**ECDHE = Elliptic Curve Diffie-Hellman Ephemeral.** Two parties compute a shared secret
over a public channel without ever sending that secret. The elliptic-curve trick:

```
 Client                              Server
   │                                    │
   │ has private a, public A = a·G       │      G = a fixed public base point
   │ has private b, public B = b·G       │
   │                                    │
   │ ────── send A ────────────────────▶ │
   │ ◀────── send B ──────────────────── │
   │                                    │
   │ computes S = a·B = a·b·G            │
   │                          S = b·A = b·a·G   ← SAME VALUE
   │                                    │
   └── both now hold the SAME secret S ──┘
      (an eavesdropper saw only A and B,
       and cannot compute a·b·G from them)
```

The **ephemeral** part is the key word: `a` and `b` are generated fresh **for this one
handshake** and **thrown away** afterward. They never touch a disk, never get reused.

### 4.2 Why ephemeral ⇒ Perfect Forward Secrecy (PFS)

Contrast the two worlds:

```
 RSA KEY TRANSPORT (old, TLS 1.2, NO forward secrecy):
   • Client generates the session secret, encrypts it with the SERVER'S LONG-TERM
     PUBLIC KEY (from the certificate), sends it.
   • Server decrypts with its long-term PRIVATE KEY.
   • PROBLEM: an attacker who RECORDS today's traffic and later STEALS the server's
     private key can go back and decrypt everything recorded. One key compromise
     unwinds the entire past.

 ECDHE (modern, TLS 1.3, forward secrecy):
   • The session secret depends on EPHEMERAL keys a and b, which are discarded.
   • The server's long-term private key is used ONLY to SIGN the handshake
     (CertificateVerify) — to prove identity — NOT to encrypt the session.
   • So even if the long-term private key is stolen later, the attacker CANNOT recompute
     a·b·G, because a and b are gone. Recorded past traffic stays unreadable forever.
```

**The interview sentence:** *"With ECDHE, compromising the server's long-term private key
in the future doesn't let you decrypt sessions you recorded in the past, because the
session keys were derived from ephemeral secrets that were discarded. That's perfect
forward secrecy."*

This is why TLS 1.3 **removed RSA key transport entirely** and mandates an ephemeral
key exchange. There is no non-PFS mode left. It is not optional.

### 4.3 The key schedule: from the shared secret to actual keys

The ECDHE shared secret `S` is not used directly. It goes through a **key derivation
function** (HKDF in TLS 1.3) that mixes in the transcript and the two randoms:

```
   S (ECDHE secret)
     │
     ▼  HKDF-Extract(with a salt derived from early handshake)
   Early Secret
     │
     ▼  Derive-Secret(... transcript hash ...)
   Handshake Secret ──────▶ handshake traffic keys (client & server)
     │
     ▼  Derive-Secret(... full transcript ...)
   Master Secret ─────────▶ application traffic keys (client & server)
                            resumption master secret
                            exporter master secret
```

Why this matters:
- **Separation** — handshake traffic and application traffic use *different* keys. A flaw
  in one doesn't expose the other.
- **Transcript binding** — because the transcript hash feeds every derivation, you cannot
  mix-and-match bytes from two different sessions. The keys are cryptographically tied to
  *this exact conversation*.
- **Direction separation** — client→server and server→client use distinct keys derived
  from the same secret, so a reflected replay doesn't decrypt.

You don't implement HKDF; you just need to know *why* a derivation function sits between
"a shared secret" and "the AES keys."

---

## 5. Cipher suites, decoded

A TLS 1.3 cipher suite is a short string packing three choices. Take
`TLS_AES_128_GCM_SHA256`:

```
  TLS  _  AES_128  _  GCM  _  SHA256
   │        │         │        │
 fixed   bulk     AEAD mode  hash for
         cipher              key derivation
         (AES,              (in HKDF)
          128-bit key)
```

- **Bulk cipher** — `AES_128` (or `AES_256`, or `CHACHA20`). This encrypts the actual data.
  128-bit AES is already beyond brute force; 256 is for the paranoid / compliance regimes.
- **AEAD mode** — `GCM` (or `CHACHA20_POLY1305`). AEAD = **Authenticated Encryption with
  Associated Data**: it provides confidentiality *and* integrity in one primitive. The
  "associated data" lets you authenticate headers (like the record's sequence number)
  without encrypting them.
- **Hash** — `SHA256` (or `SHA384`). Used inside HKDF for key derivation, not for the data
  MAC (GCM does its own integrity).

### 5.1 AEAD vs the old MAC-then-encrypt

This is a great interview tangent. Old TLS (≤1.2, CBC suites) did:

```
  plaintext ──▶ [HMAC the plaintext] ──▶ [AES-CBC encrypt (plaintext + MAC)]
```

This **MAC-then-encrypt** construction, combined with CBC's padding, opened the door to
**padding oracle attacks** (Lucky13, POODLE, BEAST): the receiver's error messages ("bad
padding" vs "bad MAC") leaked information, letting an attacker decrypt data byte by byte.

Modern TLS uses **AEAD** (GCM or ChaCha20-Poly1305):

```
  plaintext ──▶ [AES-GCM: encrypt + compute auth tag in one step]
```

One primitive, no padding, no oracle. The tag is verified *before* any decryption is
trusted. This is why TLS 1.3 **only allows AEAD suites** — every non-AEAD, CBC, RC4, and
stream cipher was deleted. The safest fix to a whole class of attacks is to delete the
class.

### 5.2 What to reject and why

- **TLS 1.0 / 1.1** — BEAST, Lucky13, no modern AEAD requirement, weak PRF. PCI-DSS has
  forbidden them for years; browsers removed them in 2020. Reject.
- **RSA key exchange** — no forward secrecy. Removed in 1.3.
- **CBC, RC4, 3DES, EXPORT ciphers, NULL ciphers, MD5, SHA1** — all removed in 1.3.
  `NULL` means "no encryption" (used to exist for debugging — a footgun).

---

## 6. The record protocol: how a byte becomes a TLS record

Once keys exist, application data travels in **records**:

```
  TLS Record:
  ┌──────────┬───────────┬──────────────┬──────────────────────────┐
  │  Type    │  Version  │   Length     │   Protected payload       │
  │ (1 byte) │ (2 bytes) │  (2 bytes)   │  (ciphertext + AEAD tag)  │
  └──────────┴───────────┴──────────────┴──────────────────────────┘
      │          │              │                    │
   app data   legacy 1.2    up to 2^14          AES-GCM ciphertext
   / handshake version for  bytes               + 16-byte tag
   / alert     compat      (~16 KB)             + content type is
                                                 ALSO encrypted in 1.3
```

Two things that surprise beginners:

1. **The content type is encrypted too** in TLS 1.3. In 1.2, an observer could tell a
   handshake record from an application-data record; in 1.3 the type byte is inside the
   AEAD, so a middlebox can't fingerprint record types. (This occasionally annoys
   corporate proxies — a real deployment consideration.)
2. **The sequence number is authenticated but not sent.** Each record has an implicit
   counter; it's fed into the AEAD as associated data. This defeats **record replay and
   reordering**: an attacker can't capture record #5 and re-send it later, because the
   sequence number won't match and the tag won't verify. This is TLS's defense against
   tampering at the record level.

---

## 7. Alerts vs. handshake failures

TLS communicates errors with a dedicated **alert** record (type 21):

```
  Alert:  struct { AlertLevel level; AlertDescription description; }
          level: warning(1) | fatal(2)
```

- A **`warning`** says "something's off but I'll keep going if you agree" (rare; e.g.
  `close_notify` is technically a warning-level alert used for a clean shutdown).
- A **`fatal`** says "I'm aborting the connection now." Examples you'll actually see:
  - `handshake_failure` (42) — no common cipher/version; a misconfiguration.
  - `bad_certificate` (42) — the cert was malformed.
  - `certificate_expired` (45) — the obvious one; see
    [`operational.md`](operational.md).
  - `unknown_ca` (48) — the client doesn't trust the signer (missing intermediate!).
  - `decrypt_error` — the Finished MAC didn't verify (tampering or key mismatch).

**Handshake failure vs. alert:** a handshake "failure" is just the *event* of the
handshake ending unsuccessfully; an *alert* is the *mechanism* TLS uses to signal it. The
client may also just **drop the TCP connection** without an alert (many do, to avoid
giving an attacker an oracle). So "no alert received" doesn't mean "no error" — it often
means "the peer considered the error security-sensitive and stayed quiet."

---

## 8. SNI, privacy, and what leaks

**SNI (Server Name Indication)** — the hostname you're connecting to — is sent **in the
clear** in ClientHello, even in TLS 1.3. So an eavesdropper on the network path learns
*which site* you visited, just not *what you did there*. Mitigations:

- **Encrypted Client Hello (ECH, the successor to Encrypted SNI)** — encrypts the SNI
  inside a public-key envelope. Rolling out slowly; requires DNS/client support.
- Until then, treat SNI as metadata that leaks. For high-privacy contexts, this matters;
  for most apps, it's an accepted leak.

This is worth knowing for interviews: "what does TLS *not* hide?" — the fact of a
connection, its timing, its approximate size, and (currently) the SNI.

---

## 9. Worked example: first request vs. resumed request

### 9.1 First request (cold, full handshake)

```
You type https://api.example.com/expenses and hit enter.

 1. TCP connect to api.example.com:443 (3-way handshake, unencrypted — it's just
    transport).
 2. ClientHello (1 RTT out) → ServerHello + {EncryptedExtensions, Certificate,
    CertificateVerify, Finished} (1 RTT back).
    ── 1 round trip total so far.
 3. Client verifies cert chain + signature + Finished, sends its Finished.
    ── application keys ready.
 4. Client encrypts the HTTP request (GET /expenses) as application records.
 5. Server decrypts, processes, encrypts the response.
 6. Server also issues a NEW SESSION TICKET (an opaque blob containing resumption
    secrets) — the client stores it.

 Cost: 1 RTT of latency before the first app byte (TLS 1.2 needed 2).
```

### 9.2 Second request (resumed, same server, later)

```
 1. TCP connect again.
 2. ClientHello INCLUDING the session ticket + a PSK extension ("I have a resumption
    ticket, and a fresh key_share").
 3. Server recognizes the ticket, and — critically — can send application data
    IMMEDIATELY, in the same flight as its Finished.

    With 0-RTT early data: the client can send its encrypted request in its FIRST
    flight, before the server has even responded. Zero round trips before data.
    ⚠ 0-RTT data is REPLAYABLE — an attacker can capture that first request and
      re-send it. So 0-RTT is only safe for IDEMPOTENT requests (GET). Never use it for
      POST /expenses. Most servers disable 0-RTT by default for exactly this reason.
    Without 0-RTT (the default): 1-RTT resumption — still faster than the full handshake
    because the expensive certificate + signature step is skipped.

 Cost: 0–1 RTT. No certificate exchange, no signature verification.
```

The difference between the two is exactly what session resumption buys you: **skip the
authentication ceremony when you already authenticated recently.** The trade-off is that
resumption secrets have a lifetime (ticket lifetime), and PFS still holds — the resumed
session still does an ECDHE exchange for its application keys, so a stolen ticket doesn't
retroactively decrypt the old session.

---

## 10. The five-minute verbal walkthrough (memorize the shape)

If someone asks "explain TLS," this is the spine:

1. **Why:** three attacks — eavesdrop, tamper, impersonate. Encryption handles the first
   two, certificates handle the third. Bonus goals: forward secrecy and speed.
2. **Asymmetric → symmetric:** asymmetric is too slow for bulk data, so we use it once to
   agree on a symmetric key, then switch.
3. **Handshake:** ClientHello (offers suites, sends ephemeral public key, SNI) →
   ServerHello (picks suite, sends ephemeral public key) → server proves identity with a
   **certificate + signature** → both derive keys via HKDF → Finished messages seal the
   transcript against tampering.
4. **Forward secrecy:** the session keys come from **ephemeral** ECDHE secrets that are
   discarded, so a later theft of the server's long-term key can't decrypt past sessions.
5. **Records:** every subsequent byte is an AEAD-encrypted, sequence-numbered record —
   integrity and confidentiality for all application data.
6. **Resumption:** a session ticket lets you skip the expensive handshake next time
   (optionally 0-RTT, with a replay caveat).

If you can say that, you understand TLS better than most working engineers.

---

## Checkpoint: can you answer these?

1. Which attack does encryption alone *not* solve, and why is that dangerous?
2. Why is asymmetric crypto used at all if it's 100× slower? Why not just use symmetric
   and pre-share a key?
3. What does "ephemeral" buy you, precisely? Explain forward secrecy to someone who's
   never heard of it.
4. Why did TLS 1.3 encrypt the *certificate* (which 1.2 left in the clear)?
5. What is a `Finished` message protecting against?
6. Decode `TLS_CHACHA20_POLY1305_SHA256`. Why might a mobile client prefer ChaCha20 over
   AES-GCM?
7. Why is 0-RTT early data restricted to idempotent requests?
8. What leaks even with TLS fully working? (Name at least two things.)
9. A client reports `unknown_ca`. What's the single most common cause?
10. Why does the AEAD authenticate a sequence number that is never transmitted?

---

## Decisions to record in `design.md`

- TLS version floor (e.g. "TLS 1.2 minimum, 1.3 preferred" or "1.3 only").
- Cipher suite policy (which suites you allow / forbid, and why).
- Whether 0-RTT is enabled (default: no).
- Where TLS terminates (see [`this-project-topology.md`](this-project-topology.md)).
- The certificate source and renewal mechanism (see
  [`certificates-and-pki.md`](certificates-and-pki.md)).
