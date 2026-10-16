# Certificates and PKI

> What a certificate actually is, how trust is chained from your server to a root the
> client already believes, and the three practical ways to get one. Mechanism first,
> then this project's choice in [`this-project-topology.md`](this-project-topology.md).

---

## 1. The problem certificates solve

The handshake (in [`how-it-works.md`](how-it-works.md)) gives you an encrypted channel
with **whoever you reached**. The unsolved question is *who did I reach?*

```
Without certificates:
  You ── "connect me to api.example.com" ──► ??? ──► [encrypted channel]

  An attacker who controls the network path answers instead.
  The channel is encrypted. To the attacker. You just sent your JWT
  and your expenses to a stranger. This is an active MITM.
```

Certificates fix this by making a server **prove** it owns the identity `api.example.com`
using cryptography a third party vouched for. That voucher is the certificate.

**The core idea in one sentence:** a trusted third party (a CA) signs a document that
says *"the public key below belongs to api.example.com"*, and your client already trusts
that CA.

---

## 2. What a certificate actually is

An X.509 certificate is a structured document with a **public key**, a list of
**identities**, a **validity period**, and a **signature** from an issuer.

Read one aloud:

```
Certificate:
    Data:
        Version: 3 (0x2)
        Serial Number:
            04:1a:2b:3c:...                          ← unique id from this CA
        Signature Algorithm: sha256WithRSAEncryption  ← how it was signed
        Issuer: C = US, O = Let's Encrypt, CN = R11   ← WHO signed it
        Validity
            Not Before: Oct 10 00:00:00 2025 GMT      ← valid from
            Not After : Jan  8 00:00:00 2026 GMT      ← valid until  (90 days!)
        Subject: CN = api.example.com                 ← WHO this cert is for
        Subject Public Key Info:
            Public Key Algorithm: rsaEncryption       ← or id-ecPublicKey
            RSA Public-Key: (2048 bit)
            ...
        X509v3 extensions:
            X509v3 Subject Alternative Name:          ← ★ THE FIELD THAT MATTERS
                DNS:api.example.com, DNS:example.com
            X509v3 Key Usage: critical
                Digital Signature, Key Encipherment
            X509v3 Extended Key Usage:
                TLS Web Server Authentication
            X509v3 Basic Constraints:
                CA:FALSE                              ← this is NOT a CA cert
    Signature Algorithm: sha256WithRSAEncryption      ← the actual signature
        3f:a2:11:...                                  ← over everything above
```

### The fields that matter, and why

| Field | Why you care |
|-------|--------------|
| **Subject / SAN** | the hostname(s) this cert is valid for. **SAN is the only field modern clients check.** |
| **Issuer** | who signed it. Not necessarily a root — usually an intermediate. |
| **Serial** | unique per issuer; used for revocation (CRL/OCSP) lookups. |
| **Validity** | Not Before / Not After. Expiry is the #1 cause of outages. |
| **Public key** | what the server will prove it owns during the handshake. |
| **Signature** | the issuer's cryptographic promise over all the above. |
| **Basic Constraints** | `CA:TRUE` = may sign others; `CA:FALSE` = leaf only. |
| **Key/Extended Key Usage** | what the key may be used for (`serverAuth` vs `clientAuth`). |

### SAN vs CN — the rule that broke the web

Historically, the hostname lived in **`Subject: CN`** (Common Name). Modern clients
(Chrome since 58, everything current) **ignore CN entirely** and match only the
**Subject Alternative Name** extension.

```
✗ OLD (deprecated, will fail):        ✓ CORRECT:
  Subject: CN = api.example.com         Subject: CN = api.example.com
  (no SAN at all)                       X509v3 Subject Alternative Name:
                                           DNS:api.example.com
```

**Practical consequence:** if you generate a self-signed cert with only `CN` set and
wonder why the browser says `ERR_CERT_COMMON_NAME_INVALID` — that's why. Always set
`-addext "subjectAltName=DNS:..."`.

---

## 3. The chain of trust

Your client doesn't know "Let's Encrypt R11." It knows a set of **root CAs** that ship
with the OS/browser (the *root store*). The chain connects them:

```
   ┌─────────────────────────────────────────┐
   │  ROOT CA      (self-signed, in your     │  ← ships in the OS root store
   │                trust store)             │     (e.g. "ISRG Root X1")
   │                CA:TRUE                  │
   └──────────────────┬──────────────────────┘
                      │ signed
                      ▼
   ┌─────────────────────────────────────────┐
   │  INTERMEDIATE  ("R11")                  │  ← NOT in your store. Must be
   │                CA:TRUE                  │     SENT BY THE SERVER.
   └──────────────────┬──────────────────────┘
                      │ signed
                      ▼
   ┌─────────────────────────────────────────┐
   │  LEAF          ("api.example.com")      │  ← your server's cert. Also sent
   │                CA:FALSE                 │     by the server.
   └─────────────────────────────────────────┘
```

### How the client walks the chain

```
  server sends:   [leaf]  [intermediate]        ← usually NOT the root

  client checks:
    1. Is leaf's SAN == the hostname I asked for?     no  → NAME MISMATCH error
    2. Is leaf signed by intermediate?                no  → chain error
    3. Is intermediate signed by something I trust?   ──► recurse
    4. Do I reach a cert in MY ROOT STORE?            no  → UNKNOWN ISSUER error
    5. Is today within every cert's validity?         no  → EXPIRED error
    6. Has any cert been revoked (CRL/OCSP)?          yes → REVOKED error

  all pass → "Verify return code: 0 (ok)" → the connection proceeds
```

**The two failure modes you'll actually hit:**

1. **Missing intermediate** — server sends only the leaf. Some clients can *fetch* the
   intermediate (AIA chasing); many can't. Symptom: works in your browser, fails in
   `curl`, Python `requests`, or an older client. **Fix: configure the full chain
   (`fullchain.pem`, not `cert.pem`) on the server.**
2. **Self-signed presented where a CA cert is expected** — client walks up, finds no
   root, fails. Works only if you've manually added that cert to the client's trust
   store (legitimate for local dev and mTLS).

---

## 4. X.509 essentials

You don't need the full ASN.1 spec. You need:

- **X.509** is the certificate *format* standard (v1 → v2 → **v3**, which added
  extensions — everything modern uses v3).
- The **signature** covers all the fields; tamper with one and verification fails.
- **Serial numbers must be unique per issuer** — that's how revocation lists identify
  certs.
- **Key Usage / Extended Key Usage** constraints exist to stop a web-server cert from
  being used to sign other certs (`CA:FALSE` + `keyUsage` does this).

---

## 5. Getting a certificate — three routes

### 5.1 Self-signed

```
  You generate a keypair. You sign your own cert. There is no third party.
```

```
  ┌──────────────┐                    ┌──────────────┐
  │  your cert   │──── signed by ────►│  your cert  │  ← a loop. No external
  └──────────────┘   (yourself)       └──────────────┘     trust anchor.
```

- **Why it fails in a browser:** the client walks the chain, reaches your self-signed
  cert, and asks "do I trust this?" It isn't in the root store → error. No amount of
  good crypto fixes a *trust* problem.
- **Where it IS legitimate:**
  - **Local development** (`localhost`, `*.local`).
  - **mTLS / internal service auth** — where you control *both* ends and can pin the
    CA explicitly (see below).
  - **On a private network you fully control** — e.g. this project on Tailscale, if
    you add the cert (or its CA) to your own device's trust store. That's a manual,
    one-machine action — fine for one user, doesn't scale.
- **Cheap to make:** `openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem
  -out cert.pem -days 365 -subj "/CN=api.example.com" -addext "subjectAltName=DNS:api.example.com"`
  (note the `-addext` SAN — the CN-only trap from §2).

### 5.2 CA-signed (the internet default)

A Certificate Authority verifies you control the domain, then signs your cert.

**Let's Encrypt and the ACME protocol** — the modern automation:

```
  ┌────────┐                          ┌───────────┐
  │  your  │  1. "I want a cert for   │  Let's    │
  │  server│      api.example.com"     │  Encrypt  │
  └───┬────┘                          └─────┬─────┘
      │ 2. "prove it — satisfy a challenge" │
      │◄─────────────────────────────────────┘
      │
      ▼
  ┌──────────────────────────────────────────────────┐
  │ CHALLENGE TYPES                                   │
  │                                                   │
  │  HTTP-01:  serve a token at                        │
  │            http://api.example.com/.well-known/     │
  │            acme-challenge/<token>                  │
  │            → needs PORT 80 reachable from internet │
  │                                                   │
  │  DNS-01:   publish a TXT record                    │
  │            _acme-challenge.api.example.com = <tok> │
  │            → needs DNS API creds; NO public port   │
  │            → supports WILDCARD (*.example.com)      │
  └──────────────────────────────────────────────────┘
      │ 3. challenge satisfied
      ▼
  ┌────────┐   4. signed cert     ┌───────────┐
  │  your  │◄──────────────────────│  Let's    │
  │  server│   (90-day validity)   │  Encrypt  │
  └────────┘                       └───────────┘
```

**HTTP-01 vs DNS-01 — the choice that matters for this project:**

| | HTTP-01 | DNS-01 |
|---|---|---|
| Needs public port 80? | **Yes** | **No** |
| Works on Tailscale/private net? | ✗ | **✓** |
| Wildcard certs? | ✗ | ✓ |
| Needs DNS API credentials? | ✗ | ✓ (a real cost) |
| Best for | public web servers | **this project**, internal services |

**This is the crux for us:** this project has **no public ingress** — it's reachable
only over Tailscale. Let's Encrypt's servers can't reach it to run HTTP-01. So the
only ACME route that works is **DNS-01**, via a DNS provider with an API
(cert-manager + a `ClusterIssuer` using your DNS provider's webhook/credentials).

**90-day validity** is deliberate — it forces automation. Manual renewal is the outage
you're scheduling for later. Use cert-manager (see [`operational.md`](operational.md)).

### 5.3 Enterprise / private CA

- An internal CA (HashiCorp Vault PKI, step-ca, Smallstep) issuing short-lived certs to
  your services. Clients must trust *that* CA — distributed via MDM/config management.
- Real-world use: corporate networks, service mesh (every pod gets an identity), mTLS
  everywhere. **Marked "for scale"** — not needed for a single-user expense tracker,
  but it's the answer to "how do internal services authenticate each other."

---

## 6. Keys — generation, types, and where they live

### Key generation and the CSR

```
  ┌─────────────────────────────────────────────────────────┐
  │ 1. Generate a PRIVATE KEY (never leaves your machine)   │
  │      openssl genrsa -out key.pem 2048                   │
  │      openssl ecparam -name prime256v1 -genkey -noout   │
  │        -out key.pem                                     │
  │                                                         │
  │ 2. Build a CSR (Certificate Signing Request) — this is  │
  │    the PUBLIC key + your identity + proof you hold the  │
  │    private key. The CA signs THIS.                      │
  │      openssl req -new -key key.pem -out csr.pem         │
  │        -subj "/CN=api.example.com"                      │
  │        -addext "subjectAltName=DNS:api.example.com"     │
  │                                                         │
  │ 3. Send the CSR to the CA (or ACME does it for you).    │
  │    The PRIVATE KEY never goes to the CA.                │
  └─────────────────────────────────────────────────────────┘
```

### RSA vs ECDSA

| | RSA | ECDSA (P-256) |
|---|---|---|
| Comparable security | 2048-bit | 256-bit |
| Cert/key size | larger | **much smaller** |
| Handshake speed | slower | faster |
| Ubiquity | universal | universal in TLS 1.3 |
| Quantum-vulnerable | yes | yes (both are) |

ECDSA P-256 gives equivalent security in a fraction of the bytes. Fine default for TLS
1.3; RSA 2048 remains the most compatible option if you must support ancient clients.

### Where the private key lives

```
  ┌───────────────────────────────────────────────────────────┐
  │  THE RULE: the private key's blast radius = its storage.  │
  │                                                           │
  │  Dev / single user:                                       │
  │     a file on disk, chmod 600, in a k8s Secret. Acceptable│
  │     if the node is yours.                                 │
  │                                                           │
  │  Real infrastructure:                                     │
  │     a KMS (AWS KMS, GCP KMS) or Vault. The key material   │
  │     never leaves the HSM; you ask it to sign. A leaked     │
  │     filesystem backup leaks nothing.                       │
  │                                                           │
  │  Never:                                                   │
  │     in a container image, in a git repo, in a log line,   │
  │     in an environment variable that gets echoed.           │
  └─────────────────────────────────────────────────────────┘
```

---

## 7. Interview angle

- **"How does a browser know a cert is legit?"** — chain of trust: walks leaf →
  intermediate → root, checking each signature and that the root is in its bundled
  trust store. Then name/SAN match, validity, revocation.
- **"Why do we need intermediates if we have roots?"** — the root private key stays
  **offline** in an HSM; intermediates do the day-to-day signing, so a compromised
  intermediate can be revoked without rotating the root that's baked into a billion
  devices.
- **"Self-signed cert — insecure?"** — the *crypto* is identical; the *trust* is absent.
  Fine for local dev and mTLS where you pin the trust anchor; broken for the public web.
- **"Certificate pinning?"** — the client accepts only a specific cert/key instead of
  any CA-issued one. Defeats a rogue CA. **The trap:** pinning means you control
  rotation across every client simultaneously — one wrong rotation bricks every client
  with no escape hatch. Key-rotation is a distributed-systems problem disguised as a
  security feature. Use HPKP-style pinning only where you also own the client and its
  update path (mobile apps, internal mesh); avoid on the open web.
- **"How would you get a cert on a machine with no public IP?"** — DNS-01 (that's this
  project), or a private CA, or Tailscale's own certs. Naming HTTP-01 as the default and
  then catching its incompatibility is the discriminator.

---

## 8. How this shows up here

- The choice between **self-signed** and **cert-manager + Let's Encrypt via DNS-01** is
  worked through in [`this-project-topology.md`](this-project-topology.md).
- The private-key storage question maps to: k8s Secret for now, Vault/KMS as the
  documented "for scale" answer.
- The SAN-vs-CN rule and the missing-intermediate failure are the two things most
  likely to bite during first deployment — see
  [`verification-and-testing.md`](verification-and-testing.md).
- `design.md` should record: cert provider, chain strategy, key type, and renewal
  mechanism (see [`operational.md`](operational.md)).
