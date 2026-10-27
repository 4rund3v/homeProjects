# 09 — OIDC, Identity, and JWT: Authentication That Actually Works

**Folder:** `09-oidc-auth-jwt/`
**Milestone:** M4 (identity)

---

## Teach first: what authentication actually is

Authentication answers one question: **"Who are you?"** Authorization (permissions) is a separate question ("Can you do that?"). This project mostly cares about authentication, but the two are inseparable in practice because the *proof* of identity (a token) is what carries authorization claims.

### The three-legged OAuth 2.0 / OIDC dance

- **Resource Owner (RO)** — the human user.
- **Client (C)** — the app the user is using (Outline).
- **Authorization Server (AS)** — the identity provider (Keycloak).
- **Resource Server (RS)** — the API Outline calls to fetch resources (often Outline itself, or a third-party API).

The **OpenID Connect (OIDC)** protocol layers an *identity* standard on top of OAuth 2.0's *authorization* standard. OAuth says "the user let this app do X"; OIDC says "and the user is Bob, here's their ID token."

For self-hosted apps like Outline, the pattern is:

```
User → Outline → Keycloak (authorize) → User authenticates → Keycloak issues tokens → Outline validates tokens
```

Outline is the **client** in this flow; Keycloak is the **AS**.

### Why not just usernames and passwords?

Because the app would then have to:

- Store password hashes (attack surface for a breach).
- Implement password reset flows.
- Handle MFA.
- Handle account lockout, session invalidation, password rotation.
- Do all that *and* let other apps reuse the same credentials (federated identity).

**Delegate authentication to a purpose-built IdP.** The app trusts the IdP's token; the app never sees the password. This is a huge surface reduction.

> **Senior lens** — the reason this matters is not tech purity. Every password field in your own app is another credential store another engineer has to think about, another breach vector, another UX surface to build. Handing it to Keycloak/Okta/Authentik is *the single highest-leverage architecture decision* for a homelab.

---

## JWTs: the wire format

OIDC issues identity as a **JSON Web Token (JWT)**. It's a base64url-encoded JSON object with three parts separated by dots:

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiYWRtaW4iOnRydWV9.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
│                                    │                                       │
header                               payload                                   signature
```

### Header — how it was signed

```json
{ "alg": "RS256", "typ": "JWT", "kid": "key-2024-01-01" }
```

`alg` is the signature algorithm. `kid` (Key ID) tells the resource server *which key* to use to verify.

### Payload — the claims

```json
{
  "sub": "user-12345",
  "iss": "https://keycloak.lab.example/realms/lab",
  "aud": "outline",
  "exp": 1705320000,
  "iat": 1705316400,
  "email": "alice@example.com",
  "realm_access": { "roles": ["outline:admin", "member"] }
}
```

Claims you must understand:

| Claim | Meaning | Senior detail |
|---|---|---|
| `sub` | Subject — unique user ID | Should be stable across sessions |
| `iss` | Issuer — which IdP made this | Resource server must verify this matches expected IdP |
| `aud` | Audience — who this token is for | Prevents a token for app A being used against app B |
| `exp` | Expiry timestamp | **Must be short-lived** for access tokens (5-15 min) |
| `iat` | Issued-at | For replay detection |
| `nbf` | Not-before | Delayed activation (rare) |
| `jti` | JWT ID | Unique per token; enables revocation by ID |

### Signature — the guarantee

The header and payload are base64url-encoded and signed with a private key. The recipient verifies the signature with the public key. **Anyone without the private key cannot forge a token.**

> **Failure mode — algorithm confusion.** Some libraries, when told to verify an RS256 token, would accept an `alg: none` header or switch to a symmetric HS256 using the *public* key as the secret. This is the infamous **JWT alg confusion vulnerability**. Modern libraries have fixed this, but always (a) restrict accepted algorithms to a specific set and (b) reject `alg: none`. **Never trust the `alg` claim in the header.**

> **Threshold — token lifetimes.**
> - **Access token:** short-lived, 5-15 minutes. It's the credential for making API calls; short means revocation via expiry is automatic.
> - **Refresh token:** long-lived (hours to days), used to obtain new access tokens without re-authenticating. It *must* be revocable and rotated.
>
> A 24-hour access token is not "a slightly long expiry" — it's a credential that survives password resets and lockouts. **Access tokens short, refresh tokens revocable, rotation on use.**

> **How refresh-token rotation actually works — and why it's a *theft detector* (the mechanism the term hides):** on a refresh, the client POSTs the *old* refresh token; Keycloak **issues a new refresh token and invalidates the old one in the same step** — a *rotation*, not a re-issue. Each refresh token is usable exactly once; holding a stale one is worthless. Here's why that's a security control, not just hygiene: if an attacker *stole* a refresh token and replays it *after* the legitimate client already rotated it, Keycloak sees **two different requests presenting the same (now-invalid) token** — that's the replay signal. **Senior response: treat a replayed/stale refresh token as a credential-compromise event — invalidate the *entire* refresh chain for that user (all outstanding refresh tokens), not just the one token.** That's "rotation as detection": the rotation guarantee is what makes the replay *visible*, and the response is to kill the family. Without rotation you can't distinguish "user's second device" from "attacker's copy" — the tokens are indistinguishable. **The concrete sequence:** (1) login → get refresh_token A; (2) use A → get refresh_token B, A revoked; (3) A is presented again (stolen/replayed) → Keycloak's `refresh_token_reuse_detected` → revoke B and the whole session, force re-login. A cold reader who's only got "rotate on use" as a slogan can't run steps 3–4; this is the L6 detail.

---

## Key rotation — the thing nobody tests

JWTs are signed with a private key. If that key leaks, every token signed with it — past, present, and future — is compromised.

The solution is **key rotation**: periodically issue a new keypair, sign new tokens with the new key, keep the old key to verify tokens still in flight, retire the old key after the max token lifetime.

The `kid` header is how the resource server picks the right public key. Keycloak rotates automatically (with a key rollover schedule) but you should test this explicitly:

- Does the resource server accept a token signed with the *previous* key?
- After retirement, does it reject that same token?
- What's the window during which both are accepted?

> **Senior lens** — JWT verification is asymmetric: signing needs the private key, verification only needs the public key. Keycloak exposes its public keys at `/.well-known/jwks.json`. Outline (or whatever consumes tokens) fetches that JWKS and caches it. If you rotate keys in Keycloak, the JWKS changes; Outline must refresh its cache (usually within seconds). This is where key rotation breaks at scale — JWKS caches that outlive the old key's validity window.

---

## Setting up Keycloak

**Keycloak** is the open-source IdP built on Quarkus (Java). It speaks OIDC, SAML, and more. Keycloak has two major versions with a big architectural difference:

- **Keycloak 17 and earlier** — standalone Quarkus app, single binary, simpler to deploy.
- **Keycloak 18+ (Quarkus-based)** — split into `keycloak` (server) + `http-adapter` (proxy) for Kubernetes. More moving parts, but scalable.

Both speak OIDC. For this project, use whatever the current chart ships; understand the split if you go Quarkus-based.

### Keycloak concepts

| Concept | Meaning |
|---|---|
| **Realm** | An isolated tenant / identity domain (like a corporate directory) |
| **Client** | An application registered to talk to Keycloak (Outline is a client) |
| **User** | A human (or service account) in the realm |
| **Role** | A permission; can be realm-level or client-level |
| **Group** | A container for users and roles |
| **Credential** | A password, or an API token |
| **Protocol Mapper** | Controls what claims go into the token |

You'll create one **realm** (`lab`) and one **client** (`outline`) as Outline's identity anchor.

### Registering Outline as a client

Outline speaks OIDC. In Keycloak, you configure a client with:

- `Client ID` — Outline's name (e.g. `outline`).
- `Redirect URIs` — where Keycloak sends users after login (`https://outline.lab.example/auth/*`).
- `Protocol` — `openid-connect`.
- `Access type` — `confidential` (Outline needs to receive tokens; public clients are for SPAs/mobile).
- **A client secret** — Outline stores this server-side (in a Secret, of course).

Outline then gets these values via env vars:

```
GOOGLE_CLIENT_ID        # or KEYCLOAK_CLIENT_ID
GOOGLE_CLIENT_SECRET    # or KEYCLOAK_CLIENT_SECRET
GOOGLE_DISCOVERY_URI    # e.g. https://keycloak.lab.example/realms/lab/.well-known/openid-configuration
```

Outline is OIDC-native but many setups still use `GOOGLE_*` variable names for historical reasons — a small gotcha when reading docs.

---

## The token flow, end to end

```
1. User visits https://outline.lab.example
2. Outline redirects to https://keycloak.lab.example/realms/lab/protocol/openid-connect/auth?client_id=outline&redirect_uri=...&state=xyz&nonce=abc
3. Keycloak shows the login page; user authenticates
4. Keycloak issues an authorization code, redirects back to Outline with ?code=...
5. Outline exchanges the code with its client secret: POST https://keycloak.lab.example/realms/lab/protocol/openid-connect/token { grant_type: authorization_code, code, client_secret }
6. Keycloak returns an access token (JWT) + refresh token
7. Outline stores the refresh token in a session cookie (httpOnly, secure, sameSite)
8. Outline sends the access token in the Authorization header for API calls: Bearer <token>
9. When the access token expires, Outline uses the refresh token to get a new one
10. When the user logs out, Outline invalidates the session and Keycloak (via the revocation endpoint) invalidates the refresh token
```

Every step is a network call you can observe with `tcpdump` or a proxy. **Walking through it manually with curl before you trust Outline's flow is invaluable.**

### The two "secret"-flavored values

- **Client secret** — shared between Outline and Keycloak, used to prove Outline is who it says it is when exchanging the code for tokens. Server-to-server credential; lives in a Secret.
- **Refresh token** — held in Outline's session store, used to get new access tokens. Revocable by the user (logout) and by admin.

Confusing these two is a classic mistake. The client secret authenticates the *client*; the refresh token authenticates the *session*.

---

## JWT security checklist (what seniors check)

1. **Verify `iss`, `aud`, `exp`, `nbf`** — every claim that defines the token's contract.
2. **Restrict accepted algorithms** — don't let the header's `alg` field dictate. Reject `none`.
3. **Use pinned JWKS cache** — don't accept arbitrary JWKs; cache and refresh on a bounded interval.
4. **Rotate signing keys** — schedule it; test the transition window.
5. **Short-lived access tokens** — 5-15 minutes; a leak is short-lived by design.
6. **Refresh tokens revocable** — server-side revocation, not just expiry.
7. **Bind to the client** — tokens issued to `outline` must not be accepted by `other-app`.
8. **Sign in production only** — no `alg: none` in test either.
9. **Log `sub` on interesting events** — you need to trace users across services without logging their emails.

---

## The Outline integration

Outline ships with several authentication providers. Configure for OIDC:

```
# values.yaml (configMap.extra)
AUTHENTICATION_DISABLED: "true"         # disable local email/password
GOOGLE_ENABLED: "true"                  # actually any OIDC provider
GOOGLE_CLIENT_ID: "outline"
GOOGLE_DISCOVERY_URI: "https://keycloak.lab.example/realms/lab/.well-known/openid-configuration"
GOOGLE_ALLOWED_DOMAINS: "example.com"
```

```yaml
# Secrets (Pattern B from doc 03)
secrets:
  existingSecret: outline-secrets
  # contains: GOOGLE_CLIENT_SECRET
```

Now Outline redirects logins to Keycloak, and users authenticate against the realm. **Users don't live in Outline; they live in Keycloak.** Outline trusts Keycloak.

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| IdP | Keycloak for open-source control; Auth0/Okta for managed |
| Access token lifetime | 5-15 minutes |
| Refresh token | Rotatable, revocable, short-ish TTL |
| Algorithms | RS256 or EdDSA; never accept `none` |
| Key rotation | Schedule automatically; test the transition |
| JWKS cache | Bounded TTL (seconds to a few minutes) |
| Client auth | Confidential clients only for server-side apps |
| Local auth in app | Disable — let the IdP be the only auth surface |

---

## Failure modes you must deliberately cause

1. **Rotate the signing key** → verify tokens signed with the old key still work during the overlap; old ones fail after retirement.
2. **Issue a token for `other-app`** → attempt to use it in Outline; observe `aud` rejection.
3. **Expire an access token mid-session** → observe automatic refresh; when that also fails, the user re-authenticates.
4. **Set `alg: none`** → verify your resource server rejects the token.
5. **Revoke a user in Keycloak** → verify Outline stops accepting their tokens within JWKS cache TTL.

---

## Exit criteria for M4

- [ ] Keycloak running with a `lab` realm
- [ ] Outline registered as a client with a stored client secret
- [ ] Local auth disabled in Outline; only OIDC login works
- [ ] Users can log in via Keycloak, are tracked by `sub`, and get short-lived access tokens
- [ ] You can trace a login by decoding a JWT and reading its claims
- [ ] Key rotation has been tested and produces no unexpected failures

Next: `10-outline-app` — the actual application you're deploying.
