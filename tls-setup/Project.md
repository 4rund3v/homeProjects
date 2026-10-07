# TLS Setup

## What this project exists to solve
Understand TLS/mTLS end to end by operating a local certificate hierarchy, serving over HTTPS, requiring client certificates, and inspecting handshakes. TLS is invisible by design; this project makes it visible.

## Success criteria / completion metrics
- A Go package that generates a local CA and issues server and client certificates with configurable SANs and expiry.
- An HTTPS server built on the shared HTTP service patterns; one client-certificate-required route demonstrated.
- Handshake behavior inspected with `openssl s_client` and curl; failures documented.
- JWT/JWS is learned in `crypto-utils`/`keycloak-setup`, not here — this project is specifically about X.509 and TLS transport.
- Local image builds and local CI format/test/build gates pass.

## Prerequisites and dependencies
- `go-fundamentals`, `go-http-server` (for the server lifecycle).
- `crypto-utils` is useful context for primitive selection; order is flexible.

## Tools, libraries, and runtime
- Go `crypto/x509`, `crypto/tls`, `crypto/rsa` or `crypto/ecdsa`.
- OpenSSL CLI for inspection.
- curl with `--cert`/`--cacert`/`--insecure`.
- Docker for local image build and CI.

## Learning objectives (skills practiced)
- X.509 structure: CN, SANs, key usage, extended key usage, expiry, chain order.
- Trust root: why the CA cert is the trust anchor and how verification fails without it.
- `crypto/tls.Config`: certificates, client auth mode, cipher suites conceptually.
- mTLS handshake: what the client proves, what the server proves.
- Certificate rotation conceptually: expiry, revocation, and why CRLs/OCSP are not handled here.
- Private key permissions and storage discipline.
- Local Jenkins or chosen CI to gate format, vet, tests, and image build.

## Architecture / design note
A small reusable package lives in this project; do not generalize until another project (raft-adv, keycloak-setup) actually imports it:

```
cmd/server/main.go          # HTTPS server with client cert
internal/certs/
  ca.go                     # generate CA
  leaf.go                   # issue server/client certs
  verify.go                 # verify chain
Dockerfile
Jenkinsfile
README.md with setup, trust model, and failure cases.
```

Key design decisions:
- ECDSA vs. RSA: document the choice. ECDSA P-256 is a reasonable default for learning; discuss key size tradeoffs.
- SANs are mandatory in modern TLS. CN-only is deprecated and should fail a test.
- Store private keys with restrictive permissions; document why.

## Test strategy
- Certificate generation tests: CA issues a valid server cert with SANs; issuing without SANs fails a test.
- Server tests: HTTP 200 with valid client cert; 400/401/403 with missing or wrong client cert; 400/500 on bad cert format.
- Negative tests with `openssl s_client` showing verification failures captured in documentation, not just asserts.
- Run tests in CI with a local self-signed setup; no external network.

## Documentation checklist
- Trust model diagram: CA, server cert, client cert, what each party trusts.
- Setup, run, and curl examples for every meaningful case.
- Failure modes documented: expired cert, wrong SAN, untrusted CA, revoked client.
- Key and cert storage assumptions and permissions.

## API contract
One example HTTPS route plus health endpoint. Use the shared service patterns from `go-http-server`; do not duplicate.

## UI / status surfaces
A small HTTPS status page served by the project. This is a reasonable demonstration because the point is to browse the TLS-secured page.

## Security boundaries to think about
- Private keys must not be committed; if a CI job generates them, the job workspace must be protected.
- SANs vs. CN: document that modern TLS ignores CN for hostname verification.
- Cipher suite selection and protocol version: document TLS 1.2 minimum and why TLS 1.3 is preferred.
- Client-cert verification must reject expired, revoked, or mismatched subjects.
- Expose profiling/pprof only on a debug listener, never on the TLS-secured API listener.

## Profiling plan
Profile is not the focus. Capture baseline latency for a certificate-verified request only if it raises a useful question (e.g., ECDSA vs. RSA handshake time).

## How this project fits into the curriculum
Lays the groundwork for `raft-adv` mTLS (optional milestone) and informs `keycloak-setup` HTTPS transport. The cert helper package is reused later; extract it only when a second project actually imports it.

## Suggested milestone walkthrough
1. **CA + leaf.** Generate a CA and a server leaf; inspect with `openssl x509`.
2. **HTTPS server.** Serve with `http.ListenAndServeTLS`; browse via curl with `--cacert`.
3. **Client certificate.** Require client auth; demonstrate success and failure with curl.
4. **Reusable cert package.** Extract helpers; add tests for SAN, expiry, chain verification.
5. **Container + CI.** Local image build; CI pipeline runs gofmt, vet, tests, and image build.
6. **TLS 1.3 and inspection.** Compare TLS versions with `openssl s_client`; document cipher negotiation.

## Reference notes and resources
- Go `crypto/x509` and `crypto/tls` docs.
- `openssl s_client` manual.
- TLS 1.3 RFC and Mozilla SSL config generator.
- OWASP TLS Cheat Sheet.
