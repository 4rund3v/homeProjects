# TLS Setup

**Goal:** Understand local TLS and mutual TLS by building and inspecting a small Go service.

**Scope:** Local CA and leaf certificates, SANs, certificate chains, Go `crypto/tls` and `crypto/x509`, HTTPS, client-certificate verification.

**Out of scope:** Public certificate automation and production PKI operations.

**Learning focus:** Trust roots, hostname verification, key handling, handshake behavior, certificate expiry and rotation.

**Depends on:** `go-fundamentals`, `go-http-server`.

## Milestones
- [ ] Create a local CA and issue a server certificate with SANs.
- [ ] Serve HTTPS and inspect the handshake with standard tools.
- [ ] Require and verify a client certificate.
- [ ] Document key storage and trust assumptions; later apply the concepts in `raft-adv`.
