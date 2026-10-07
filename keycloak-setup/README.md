# Keycloak Setup

**Goal:** Learn identity and access management by integrating a local Keycloak instance with an API.

**Scope:** Realms, clients, users/roles, OIDC Authorization Code + PKCE, JWT/JWKS validation, token expiry/refresh, API authorization.

**Out of scope:** Social identity federation, SAML, production identity operations.

**Learning focus:** OAuth 2.0 vs. OIDC, client types, redirect URI safety, scopes/roles, local token verification vs. introspection.

**Depends on:** `drf-basics` or `go-http-server`; deploy on `k3s-helm` later. TLS concepts from `tls-setup` are useful.

## Milestones
- [ ] Run Keycloak locally and configure a realm and test client.
- [ ] Complete an OIDC login flow and inspect the resulting tokens.
- [ ] Protect one API route by validating issuer, audience, expiry, and signature.
- [ ] Test role authorization, expired tokens, and invalid signatures.
