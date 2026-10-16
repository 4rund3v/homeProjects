# TLS 1.3 — The Delta from 1.2

> What changed, why, and what it means in practice. Assumes you've read
> [`how-it-works.md`](how-it-works.md). This is the "I learned 1.2, what do I need to
> know" doc — and a common interview topic.

---

## 1. The headline: fewer round trips

```
  ┌───────────────────────── TLS 1.2 ─────────────────────────┐
  │                                                           │
  │  Client            Server                                 │
  │    │ ── ClientHello ──────► │                             │
  │    │ ◄─ ServerHello ─────── │   (cipher chosen here)      │
  │    │ ◄─ Certificate ─────── │                             │
  │    │ ◄─ ServerKeyExchange ─│                             │
  │    │ ◄─ ServerHelloDone ── │                             │
  │    │ ── ClientKeyExchange ►│                             │
  │    │ ── [ChangeCipherSpec] ►│                             │
  │    │ ── Finished ─────────►│                             │
  │    │ ◄─ [ChangeCipherSpec] │                             │
  │    │ ◄─ Finished ──────────│                             │
  │    │ ═══ application data ═══   2 full RTT before data    │
  └───────────────────────────────────────────────────────────┘

  ┌───────────────────────── TLS 1.3 ─────────────────────────┐
  │                                                           │
  │  Client            Server                                 │
  │    │ ── ClientHello ──────► │                             │
  │    │    (key_share: a guess!)│                            │
  │    │ ◄─ ServerHello ─────── │   (server's key_share)      │
  │    │ ◄─ {EncryptedExtensions,│  ← ENCRYPTED from here on  │
  │    │     Certificate,        │                            │
  │    │     CertificateVerify,  │                            │
  │    │     Finished} ─────────│                            │
  │    │ ── {Finished} ────────►│                             │
  │    │ ═══ application data ═══   1 full RTT before data    │
  └───────────────────────────────────────────────────────────┘

  ┌──────────────────────── TLS 1.3 0-RTT ────────────────────┐
  │                                                           │
  │    │ ── ClientHello + ─────► │                             │
  │    │    {early data}          │   data on the FIRST flight │
  │    │ ◄─ ServerHello + ...    │   ⚠ REPLAYABLE — see §5     │
  └───────────────────────────────────────────────────────────┘
```

**How 1-RTT works:** the client *guesses* a key-exchange group and sends its key share
in the first message (`key_share`). If the server agrees, it can compute the shared
secret immediately and start encrypting. If the guess was wrong, the server sends a
`HelloRetryRequest` and you fall back to 2-RTT — the cost of a bad guess is one extra
round trip, not a broken connection.

**Second connection to the same server:** PSK resumption gives **1-RTT**, and 0-RTT
early data gives **zero** (with the caveat in §5).

---

## 2. What was removed — and why each was dangerous

| Removed | Why it had to go |
|---------|------------------|
| **RSA key transport** | no forward secrecy — one stolen key decrypts all recorded traffic |
| **Static DH** | same problem, plus no PFS |
| **RC4** | broken keystream biases |
| **DES / 3DES** | 64-bit block → Sweet32 birthday attack |
| **MD5, SHA-1** (in the handshake) | collision attacks |
| **CBC-mode ciphers** | MAC-then-encrypt + padding → BEAST, Lucky13, POODLE |
| **Compression** | CRIME / BREACH — compression leaks secrets via length |
| **Renegotiation** | the 2009 renegotiation attack (insecure renegotiation) |
| **AEAD-less suites** | every remaining suite is AEAD |

**The pattern:** 1.3 removed everything that wasn't AEAD + ephemeral-DH. That's a
deliberate simplification — fewer choices means fewer ways to choose wrong. This is a
genuine design lesson: **the protocol got faster by deleting options.**

---

## 3. The new key schedule (HKDF)

1.2 had an ad-hoc PRF. 1.3 formalized everything through **HKDF** (HMAC-based
Extract-and-Expand Key Derivation Function), producing a clean derivation tree:

```
                    ┌───────────────────────────┐
                    │  PSK (resumption)  or     │
                    │  0 (fresh connection)     │
                    └─────────────┬─────────────┘
                                  │  HKDF-Extract (with a salt)
                                  ▼
                    ┌───────────────────────────┐
                    │       EARLY SECRET        │
                    └─────────────┬─────────────┘
                                  │  Derive-Secret(., "ext binder")
                                  ▼
                    ┌───────────────────────────┐
                    │  binder_key  (0-RTT PSK)  │
                    └───────────────────────────┘

   (ECDHE shared secret ──┐)
                         ├─► HKDF-Extract
   (Early Secret ────────┘)
                         ▼
                    ┌───────────────────────────┐
                    │     HANDSHAKE SECRET      │
                    └─────────────┬─────────────┘
                                  │  Derive-Secret(., "c hs traffic")
                                  ▼
                    ┌───────────────────────────┐
                    │  client_hs_traffic        │  ← encrypts the client's
                    │  server_hs_traffic        │    handshake flight & its Finished
                    └─────────────┬─────────────┘
                                  │  HKDF-Extract (again, over 0s)
                                  ▼
                    ┌───────────────────────────┐
                    │      MASTER SECRET        │
                    └─────────────┬─────────────┘
                                  │  Derive-Secret(., "c ap traffic" / "s ap traffic")
                                  ▼
                    ┌───────────────────────────┐
                    │  client_ap_traffic        │  ← encrypts APPLICATION data
                    │  server_ap_traffic        │
                    └───────────────────────────┘
                                  │  Derive-Secret(., "exp master")
                                  ▼
                    ┌───────────────────────────┐
                    │  exporter_master_secret   │  ← for out-of-band channel
                    └───────────────────────────┘    binding (EKM)
```

**Why this matters:**

- **The certificate and handshake are encrypted in 1.3.** In 1.2 the server's cert went
  in cleartext — anyone on the path could see which site you were visiting. In 1.3
  `EncryptedExtensions`, `Certificate`, and `CertificateVerify` are all inside the
  encrypted flight. This is a real privacy gain, and a favorite interview point.
- **Separate secrets per direction and per phase** mean a compromise of one doesn't
  cascade.
- **`KeyUpdate` messages** let either side rotate traffic keys mid-connection without
  a new handshake.
- **Extended Master Secret** (mandatory in 1.3) binds the handshake transcript into the
  master secret, closing the 1.2 "triple handshake" attack class.

---

## 4. Cipher suites: the short list

1.2 had dozens. 1.3 has **five**:

```
  TLS_AES_256_GCM_SHA384
  TLS_CHACHA20_POLY1305_SHA256
  TLS_AES_128_GCM_SHA256
  TLS_AES_128_CCM_8_SHA256
  TLS_AES_128_CCM_SHA256
```

Note the name no longer includes the key exchange — that's negotiated separately via
`supported_groups` (X25519, secp256r1, …) because key exchange is now always ephemeral.
See [`how-it-works.md`](how-it-works.md) §5 for decoding a suite name.

---

## 5. 0-RTT and its replay hazard

0-RTT lets a returning client send **application data in its very first flight**, using
a PSK from the previous session. It's genuinely faster — and genuinely dangerous:

```
  THE HAZARD: 0-RTT data is NOT protected against replay.

  Attacker records your 0-RTT flight:  "POST /expenses {amount: 42.50}"
  Later, replays it to the server 10 times.
  → 10 expenses recorded, if the server isn't careful.

  WHY: the server hasn't yet processed the ClientHello, so it has no
       fresh handshake context to bind the early data to. The anti-replay
       window is inherently limited.
```

**Rules for using 0-RTT safely:**

1. Only for **idempotent, non-state-changing** requests (GETs, or requests with their
   own anti-replay token).
2. Never for anything that mutates (POST/PUT/DELETE) unless the application has its own
  replay protection.
3. Servers may reject 0-RTT at any time — it's opportunistic.

**For this project:** 0-RTT should stay **disabled** for `/api`. An expense POST must
not be replayable. The idempotency key we already have (see
[`../event-flows.md`](../event-flows.md)) would partially mitigate it, but disabling
0-RTT is the correct default.

---

## 6. Resumption: session tickets vs PSK

```
  ┌────────────────────────────────────────────────────────┐
  │  TLS 1.2 session tickets / session IDs                  │
  │    • a server-issued opaque blob the client replays     │
  │    • server keeps (or encrypts) the master secret       │
  │    • resumption = abbreviated handshake                 │
  ├────────────────────────────────────────────────────────┤
  │  TLS 1.3 PSK                                           │
  │    • same idea, formalized through the key schedule     │
  │    • PSK + (optional) 0-RTT early data                  │
  │    • the PSK is derived, not the raw master secret      │
  └────────────────────────────────────────────────────────┘
```

**Operational note:** ticket encryption keys. If the server rotates them, all sessions
resuming against the old key fail. NGINX has `ssl_session_ticket_key` for this; in a
multi-replica setup all replicas must share the key or resumption breaks randomly.
Another reason stateless APIs with short-lived JWTs often just skip resumption tuning.

---

## 7. QUIC / HTTP/3 — what's next, briefly

```
  ┌──────────────────────────────────────────────────────────┐
  │  TCP + TLS:                                              │
  │    TCP handshake (1 RTT) → TLS handshake (1-2 RTT)       │
  │    = 2-3 RTT before any request bytes                    │
  │    One lost packet stalls the whole connection           │
  │    (head-of-line blocking at the transport layer)        │
  ├──────────────────────────────────────────────────────────┤
  │  QUIC over UDP:                                          │
  │    Transport + TLS 1.3 built in, negotiated together     │
  │    = 1 RTT (and 0-RTT possible)                          │
  │    Streams are independent — a loss on one stream         │
  │    doesn't stall the others                              │
  └──────────────────────────────────────────────────────────┘
```

QUIC isn't "TLS over UDP" — it *integrates* TLS 1.3's handshake into the transport, so
they negotiate in a single round trip. The big win is removing TCP's head-of-line
blocking: a single dropped packet no longer freezes every stream on the connection.

**Scope note:** QUIC/HTTP/3 is not in this project. Mention it in an interview as "the
next step, and why it exists" — don't try to deploy it on a single k3s node behind
NGINX.

---

## 8. Interview angle

- **"Why is TLS 1.3 faster?"** — the client guesses the key group and sends its key
  share in the first flight, so the server can derive secrets immediately. Plus 1-RTT
  vs 2-RTT, and optional 0-RTT.
- **"What's the security gain beyond speed?"** — the handshake itself is encrypted
  (no more cleartext certificate leak), and mandatory PFS via ECDHE-only key exchange.
- **"Why remove so many cipher suites?"** — the survivors are exactly AEAD + ephemeral
  DH; everything removed had a known attack. Simpler protocol, fewer footguns.
- **"Is 0-RTT safe?"** — no, it's replayable. Safe only for idempotent requests, and
  servers may refuse it.
- **"How does the key schedule work?"** — HKDF extract-and-expand in layers: early
  secret → handshake secret → master secret → per-direction traffic secrets. Separate
  secrets mean compromise doesn't cascade.

---

## 9. How this shows up here

- NGINX should be configured `ssl_protocols TLSv1.2 TLSv1.3;` — 1.2 retained only for
  old-client compatibility, and it can be dropped once nothing needs it. See
  [`../nginx/security-and-headers.md`](../nginx/security-and-headers.md).
- 0-RTT should be **off** for `/api` (§5) — expense POSTs must not be replayable.
- The encrypted-handshake privacy gain matters less here (the traffic is already inside
  a Tailscale tunnel, so an observer sees only WireGuard), but the mechanism is the same.
- If someone asks "why not just HTTP/3?" — the answer is QUIC needs UDP ingress and a
  different controller path; not worth it for a single-node, single-user system.
