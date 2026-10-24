# TLS — The Complete Guide for This Project

> How TLS actually works, how certificates establish trust, and how it all composes on
> a k3s node reachable only through Tailscale. Written for **L5/L6 interview prep** and
> as the project's operational reference.

> **Start here:** [`how-it-works.md`](how-it-works.md) is the centerpiece — the full TLS
> 1.3 handshake packet by packet, ECDHE, PFS, cipher suites, and the record protocol.
> If you read one file, read that one.

## The docs

| File | What it covers | Read when |
|------|----------------|-----------|
| [`mtls-and-cert-generation.md`](mtls-and-cert-generation.md) | **Hands-on lab first**: build a root/intermediate/leaf chain with `openssl`, do mTLS, then the whole thing in Go — `x509`, `crypto/tls`, `CreateCertificate` | Before `certificates-and-pki.md` if you want the hands; after it if you'd rather theory-first |
| [`how-it-works.md`](how-it-works.md) | The three problems TLS solves; asymmetric-then-symmetric; full TLS 1.3 handshake; ECDHE & PFS; HKDF key schedule; cipher suites decoded; AEAD; the record protocol | Before everything else. The interview answer. |
| [`certificates-and-pki.md`](certificates-and-pki.md) | What a cert is, SAN vs CN, the chain of trust, X.509, self-signed vs CA-signed, ACME (HTTP-01 vs DNS-01), key types, where private keys live | When you need to *get* or *inspect* a cert |
| [`verification-and-testing.md`](verification-and-testing.md) | `openssl s_client`, reading cert output, checking expiry, enumerating suites (`sslscan`/`testssl.sh`), a reviewer checklist | Before sign-off / when something's broken |
| [`tls-1.3.md`](tls-1.3.md) | The 1.2→1.3 delta: 1-RTT, mandatory PFS, what was removed, the new key schedule, PSK/resumption, 0-RTT risk; QUIC/HTTP3 as "what's next" | When someone says "TLS 1.3" |
| [`this-project-topology.md`](this-project-topology.md) | The two encryption layers (Tailscale/WireGuard vs TLS), where to terminate, which cert strategy to use, what to record in `design.md` | When deploying or reviewing the edge |
| [`operational.md`](operational.md) | Cert nearing expiry, renewal, chain ordering, key rotation, ACME rate limits, why TLS even on a private network | When running it in anger |
| [`mtls-and-cert-generation.md`](mtls-and-cert-generation.md) | **Hands-on lab**: build a CA + leaf with openssl, verify chains, do mTLS, then the same end-to-end in Go (`x509`, `crypto/tls`, `CreateCertificate`) | When you want to generate/verify certs and speak Go |

## Suggested reading order

**If you have an interview tomorrow:** `how-it-works` → `certificates-and-pki` (the
chain of trust) → `tls-1.3` (the deltas). Those three cover the questions that get
asked.

**If you are building this feature:** `this-project-topology` (the decision) →
`certificates-and-pki` (how to get the cert) → `verification-and-testing` (prove it
works) → `operational` (keep it working).

**Reference-as-needed:** the rest.

## The one-paragraph mental model

TLS turns an untrusted network into a pipe that can't be **read** (encryption), can't
be **tampered** with (AEAD integrity), and can't be **impersonated** (certificates).
It bootstraps with asymmetric crypto — expensive, used only to agree on a session key —
then switches to symmetric crypto for everything after. **Ephemeral** key exchange
(ECDHE) means stealing the server's private key *today* cannot decrypt *yesterday's*
recorded traffic (Perfect Forward Secrecy). Certificates solve the "who am I talking
to" problem: a chain of signatures from your server's cert up to a root your client
already trusts. Every doc below is one of those sentences expanded.

## Scope honesty

This project terminates TLS at the NGINX ingress and speaks plain HTTP inside the k3s
pod network. That's a deliberate, documented choice — see
[`this-project-topology.md`](this-project-topology.md). Service mesh / mTLS everywhere
is discussed as an option but marked "not here, for scale."
