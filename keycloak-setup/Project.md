# Keycloak Setup

## What this project exists to solve
Learn identity and access management by running a local Keycloak, completing real OIDC flows, and protecting API resources. The goal is to understand what OAuth/OIDC buys and where it ends, so later work treats identity as a first-class design concern.

## Success criteria / completion metrics
- Local Keycloak instance with a realm, client, test user, and role configuration.
- OIDC Authorization Code flow with PKCE demonstrated from a Go CLI or browser.
- One API route protected by local JWT validation (signature, issuer, audience, expiry); invalid tokens return documented errors.
- Role-based authorization demonstrated; expired and tampered tokens are rejected.
- Token validation is performed locally with JWKS or equivalent, not by accepting whatever Keycloak returns.
- Documentation explains what Keycloak manages, what the resource server enforces, and what the client must do.
- Local CI tests auth behavior; container builds are reproducible.

## Prerequisites and dependencies
- `go-fundamentals`, `python-refresh`; `drf-basics` or `go-http-server` for a protected resource.
- `crypto-utils` for primitive understanding (signatures, randomness).
- `tls-setup` for HTTPS transport context.
- `uv` for Python (see `../uv-setup.md`).

## Tools, libraries, and runtime
- Keycloak container.
- Go `crypto/rsa` or `crypto/ecdsa` for JWT/JWKS validation.
- Python `python-jose` or `cryptography` if a Python resource server is used.
- curl and a browser for flow observation.
- Docker Compose for Keycloak and the protected resource.
- Local CI.

## Learning objectives (skills practiced)
- OAuth 2.0 vs. OIDC: what each defines and what is delegated to Keycloak.
- Authorization Code flow with PKCE: why PKCE exists, what the client proves, and what the authorization server returns.
- JWT structure, JWKS, and local signature verification without a network round-trip.
- RBAC roles/scopes vs. API permissions; why they must be explicitly mapped.
- Token refresh, expiry, and logout semantics.
- API security schemes in OpenAPI.

## Architecture / design note
A minimal local setup:

```
keycloak/                    # realm export, client config
api/                         # protected resource (Go or Python)
  ...
docker-compose.yaml
NOTES.md
```

Separate Keycloak configuration (realm, client, roles) from application code. The application should treat Keycloak as an external identity provider; do not embed identity logic in business handlers.

## Test strategy
- Unit tests for local JWT validation: valid token, expired token, wrong issuer, wrong audience, tampered signature.
- Integration tests against local Keycloak in Docker for token issuance and refresh flow.
- Auth tests: authenticated/authorized request succeeds; unauthenticated returns 401; unauthorized returns 403.
- CI runs Keycloak in Docker, starts the protected API, and executes auth tests.

## Documentation checklist
- `README.md` with setup, Keycloak realm configuration steps, flow diagrams for Authorization Code + PKCE.
- `NOTES.md` explaining which responsibilities belong to Keycloak, the client, and the resource server.
- OpenAPI security scheme documentation for the protected API.
- Token validation rules and failure behavior documented explicitly.

## API contract
Protected route documented in OpenAPI with Bearer/JWT security scheme. Document errors for missing, expired, invalid, and unauthorized tokens.

## UI / status surfaces
Simple protected homepage served by the resource server confirming identity and roles; useful for manual verification.

## Security boundaries to think about
- JWKS endpoint should be pinned or cached with refresh; accepting arbitrary issuers is unsafe.
- PKCE is required for public clients; confidential clients need client secret handling.
- Role mappings must reflect API scopes, not UI roles; document the mapping explicitly.
- Token storage in browsers and CLI must follow platform best practices; this project observes the flows, not the full client hardening.
- Redirect URIs must be validated; open redirects are an attack surface.

## Profiling plan
Profile is not the focus. A small latency comparison between local validation and introspection is acceptable if it raises a useful question about token-validation architecture.

## How this project fits into the curriculum
Makes identity real. TLS/crypto foundations inform transport and token handling. `raft-adv` can optionally demonstrate how identity does not replace consensus. `k3s-helm` can deploy Keycloak as a first-class service.

## Suggested milestone walkthrough
1. **Keycloak locally.** Run Keycloak; create a realm, client, user, and role.
2. **OIDC flow.** Complete Authorization Code + PKCE from a Go CLI; inspect tokens.
3. **Local validation.** Verify JWT locally with JWKS; reject expired, wrong issuer, and tampered tokens.
4. **Protected API.** Enforce roles at API boundaries; test authorized and unauthorized requests.
5. **Container + CI.** Docker Compose with Keycloak and API; CI tests auth flows.

## Reference notes and resources
- Keycloak documentation (realm, client, roles).
- OAuth 2.0 RFC 6749; OIDC Core 1.0.
- JWT RFC 7519; JWK RFC 7517.
- OWASP OAuth Security Cheat Sheet.
