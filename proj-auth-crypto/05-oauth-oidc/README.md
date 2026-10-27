# 05 — OAuth 2.0 & OIDC: The Four Flows, Roles, and Redirect URIs

**Folder:** `05-oauth-oidc/`

**OAuth** is an *authorization* protocol: "the user said *yes* to *this scope* for *this app.*" **OIDC (OpenID Connect)** is an *identity* layer on top of OAuth: "and here's *exactly who the user is*, as a *signed ID token* (a JWT, 04)." Conflating them — or wiring a *flow* that has *no consent leg* (00's failure #5) — is the #1 OAuth mistake. The four flows are the same four *security properties* asked in four *deployment shapes*; pick the wrong one and you've built the *attack*.

---

## Teach first: the *roles* (00's dance, *named precisely)

| Role | What it *is* | What it *does* |
|---|---|---|
| **Resource Owner (RO)** | *the human* (or a *machine, in *the client-creds *flow) | *Owns* the resource; grants a scope; is *the consent leg. |
| **Client (C)** | *the app the user is *using* | *Wants* a token *for the RO's *data; *holds a client *secret (if *confidential). |
| **Authorization Server (AS) / IdP** | *the party that *knows who the RO is* (Keycloak, *this *project's IdP) | *Authn* *the RO; *issues* the tokens; *is* *the trust anchor. |
| **Resource Server (RS)** | *the API that *holds the data* | *Verifies* the AS's token (JWKS, 04), *enforces* the *scope (authz). |

> **The load-bearing split (the *two "secret"-flavored *values a panel will make you *disambiguate):**
> - ***Client secret** — *shared* between the Client *and the IdP; *proves* *the Client is *who it says it is* *when it exchanges the *code for tokens. *A **server-to-server credential**, *lives in a Secret (07). **Confidential clients *only.**
> - ***Refresh token** — *held in the *Client's session; *proves* *the session is *who it is. ***Revocable + rotating (04).
> **Confusing these is a classic mistake:** *the client secret authenticates the *client; the refresh token authenticates the *session. They're *different credentials with *different owners.

---

## The four flows, and *why each exists

### 1. **Authorization Code (with PKCE) — *the user-facing flow (the default for *any *public or *confidential *browser/native client)**

```
User ──1──► Client ──redirect──► IdP (auth endpoint, *with a `state` + a *`nonce`)
User authenticates + *consents to the scope
IdP ──3──► Client: a *short-lived, *single-use authorization code
Client ──4──► IdP (token endpoint): *the code + (a client secret, if *confidential) + PKCE verifier
IdP ──5──► Client: an access JWT + *a refresh token + (OIDC: *an ID token, *below)
```

**Why it exists:** the user's credentials *never touch the Client*; *the IdP is the only one who sees them. *The *authorization code* is a *bearer* token that's *short-lived + single-use, *so a *leaked code is nearly worthless. **PKCE** (Proof Key for Code Exchange, below) is *what makes *this* flow *safe for a *public* client (one with *no secret, like a SPA / mobile app).

### 2. **Client Credentials — *machine-to-machine (the service-account *sibling, 06)**

```
Service A ──1──► IdP (token endpoint): *the client_id + *a client_secret (a *confidential client, *no user)
IdP ──2──► Service A: an *access token (a *JWT, `sub` = *the *client, *a scope claim)
Service A ──3──► Service B: *the *token, *B verifies via JWKS + checks the scope
```

**Why it exists:** a machine has *no user; *it authenticates as *itself via *its credentials. *This is the *same shape* as a *k8s service account's *token (06) — *the "workload *issues a token for *itself, *aud set to *the target." *This is *the "apps use service accounts, *not user creds" (06) *mechanism at the *OAuth layer.**

### 3. **PKCE (Proof Key for Code Exchange) — *not a separate flow, a *hardening on *the auth-code flow*

**The problem it solves:** a public client (a SPA / a mobile app) *can't hold a *client secret (it's *shipped to the user). *The old *insecure trick was to *put the *code in the *redirect URI** (*a "hybrid" *flow that let an *attacker intercept it. **PKCE** fixes this *without a secret:
- *At *start, the Client computes a *random **code verifier** (a 43–128-char string) + its **code challenge** = `base64url(SHA256(verifier))`.
- *It sends the *challenge (not the verifier) *in step 2; *it sends the *verifier *in step 4 (the token *request).
- *The IdP *checks* the verifier hashes to the challenge → *it's *the same client that started it (an *attacker who *stole the code *doesn't have the verifier).

**Why it matters (the *panel* *question):** *PKCE is *what lets *a public* client (a SPA, *a mobile app) *use the *safe auth-code flow *without a secret. *For a *confidential* client, PKCE is *still* *recommended (defense-in-depth: *it kills *the "code intercepted *in the redirect" *attack even if a *secret exists. **The threshold: always *add PKCE, *never skip it, *even for *confidential clients.

### 4. **Refresh — the session-continuation flow (the *rotation *is in 04)**

```
Client ──► IdP (token endpoint): *the old refresh token (grant_type=refresh_token)
IdP ──► Client: a *new access token + a *new refresh token, *and invalidates the *old refresh (rotation, *04)
```

**Why it exists:** *a *short access token (04) *means the user re-auths every 5 min — *hostile UX. *The *refresh token* *gives a *new access token *without re-auth, *and its *rotation is the *theft detector (04). *This is *the "refresh *token: *rotate on use, *max age 24h, *invalidate the family on replay" *threshold from 04, *wired as a *flow.**

> **The one-line that *sorts the four (a panel's "which flow *and why?):**
> - ***Human in the loop, *browser** → **auth code (+ *PKCE).
> - ***Machine, *no user, *S2S** → **client credentials.
> - ***Public client (SPA / mobile)** → **auth code *with *PKCE, *no secret.
> - ***Session continuation** → **refresh grant** (*rotating).

---

## OIDC on top: *the ID token, and *why "OAuth *isn't identity"

*OAuth says* "the user let this app do X." *OIDC adds* "and the user *is Bob, *here's their identity." *The *ID token* (a *signed JWT, 04) is *the OIDC addition: it carries **`sub`, `iss`, `aud`, `exp`**, *and standard claims (`email`, `profile`, *etc. via *scopes).

**The *three tokens in an OIDC response (the *names a panel will use):**
| Token | *What it *is* | *What it *carries* | *Audience |
|---|---|---|---|
| **Access token** | *the OAuth *authorization* (the *RS's credential) | *the scope + *any RS-specific *claims | *the RS |
| **ID token** | *the OIDC *identity (a *signed assertion that *the RO is X) | *the standard claims (`sub`, `email`, *profile) | *the Client |
| **Refresh token** | *the *session continuation (an *opaque `jti`, 04) | *nothing (just *the ID) | *the IdP |

**Why it matters (the real-world consequence):* an OAuth-only app *knows "the user *allowed *scope X" *but *doesn't know *who the user *is (no `sub`). **OIDC *gives it the `sub`* (the *stable user ID), *which is *what 00's "identity" *row needs. *This is *why a login that *only* does "OAuth *authorization" *still *needs OIDC *to *actually know who logged in.

---

## Scopes vs. *claims vs. *roles — the *three "what can it *do" *concepts a panel will make you *distinguish

| Concept | *What it *is* | *Where it lives* | *The decision it *drives |
|---|---|---|---|
| **Scope** | *a *coarse grant (e.g. `read:docs`, `write:docs`, `profile`) | *on the *token (the access token's *`scope` claim, *the *`aud`-bound grant) | *"what *category of *access, *checked by the *RS *against the *token's scope |
| **Claim** | *a *fact about the subject (email, role, tenant) | *on the token (a *key-value) | *"what *data the RS *can consult locally *to decide* |
| **Role / RBAC *role** | *a *named set of *permissions on a *resource (a k8s *Role, 06) | *on the *resource side (a *policy, *not the token) | *"what *specific actions are *allowed, *enforced by the *resource (a policy decision, *00's *authz *row) |

> **The distinction a panel will *press:** a scope is *the grant the *IdP *stamps on the token; a *claim* is *the data the RS *reads; a *role* is *the policy the RS *enforces. **You do *not* "put a role *on the token *and be done"** — *the role is a *resource-side policy that *consults the token's claims.* *The token is *the evidence; the *policy is the decision* (00's *"claim is data, policy is decision").

> **The *threshold on *aud (the *binding, 04's *failure):** *the `aud` *claim is *what stops a token for `outline` *being used against `other-app`. *A *missing `aud` check = *cross-app credential leakage. This is *the *binding, and it's the *last claim a junior *checks.

---

## Redirect URIs, state, and nonce — the *three params that *prevent *the *three *classic attacks

| Param | *What it *is* | *What it *prevents |
|---|---|---|
| **`redirect_uri`** | *where the IdP *sends the user back *after consent* (a *registered, *exact match) | ***Authorization-code injection (an attacker *registers a *malicious *redirect, *steals the code). *The IdP *only* *redirects to *URIs *registered for that client. **A *wildcard or *a *loose match = *the code goes to the *attacker. |
| **`state`** | *a *random value the Client *puts in the *auth request *and *expects back in the *redirect* | ***CSRF on the *auth flow (an attacker *forwards a *victim to *a *malicious *auth URL, *then *substitutes *their own code). *A *unverifiable redirect = *no *binding to the *original request. |
| **`nonce`** | *a *random value, *echoed into the ID *token* (OIDC) | ***Replay of an *ID *token (an attacker *captures an old ID token, *replays it). *The `nonce` binds the *token to the *specific auth *request. |

> *The mechanism* (the *three that *always go *together): `state` *binds the *redirect to the *request (anti-CSRF), `nonce` *binds the *ID *token to the *request (anti-replay), *and the *registered `redirect_uri` *stops the *code from *going *anywhere but the *client. *A *login flow *with any one missing is *a different (weaker) *flow.

---

## Fit-to-project: where OAuth/OIDC *is* the *system in *this* project

1. ***The login flow (08) *is* **auth code + PKCE** for *a user-facing client (a SPA) *and **client credentials** for *a machine (a service). **The *IdP *is the Keycloak/OpenID *endpoint in *the capstone; *the resource server *is *the API that *verifies the tokens via JWKS.**
2. ***The scope = the authz *data on the *access token** (04's claim). *The RS *checks `scope` *before acting; *the role/RBAC *policy (06) *consults the *claims to *decide.*
3. ***The ID *token (OIDC) *gives the `sub`* — *the stable user ID *that 00's identity *row needs. *An OAuth-only *login (no OIDC) *gives a scope *but *no identity.
4. ***The *redirect URIs + state + nonce* are *the *three *class of *attack* *the *flow must *defeat (code injection, CSRF, replay.
5. ***Client credentials *as the S2S *flow** is *the OAuth *version of *06's service-account *flow: *the "workload *issues a token for *itself, *aud = *the target service."

> **The *threshold on *this* project:** *the capstone (08) *wires **auth code + PKCE** for *the user login (a *confidential web client *with a secret, *PKCE *always), **client credentials** for *service-to-service *calls (a *confidential client, *the S2S identity), *and **refresh** for *the session (rotating). **A public client (a SPA) *is the *auth-code + PKCE, *no-secret* *variant.

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| *The user-facing flow | **Auth code + PKCE.** *PKCE *always, *even for confidential. |
| *The S2S / *machine flow | **Client credentials.** *No user, *the client *authenticates as itself (06). |
| *A public client (SPA/mobile) | **Auth code + PKCE, *no client secret.** *The PKCE *is the *protection. |
| *The session | **Refresh grant, *rotating (04), *family-kill on replay.** |
| `redirect_uri` | ***Registered, *exact match, *no wildcards. *Prevents code injection. |
| `state` | ***Random, *per-request, *verified on redirect. *Anti-CSRF. |
| `nonce` | ***Random, *echoed into the ID *token. *Anti-replay. |
| *Scopes vs roles | ***Scope = the *grant on the token; *role = the *resource-side policy. *The token *is the evidence, *the policy is the decision. |

---

## Failure modes you must deliberately cause

1. ***A missing `state` (CSRF on the *auth flow):** *force a *login *without `state`; *an attacker *forwards a *victim to a *malicious auth URL *and the *code *bounces to the *attacker.** *The fix: *a per-request `state`, *verified on the *redirect.
2. ***A loose `redirect_uri` (code injection):** *register `redirect_uri` *as a wildcard / *a *prefix; *an attacker *substitutes *their URI *and captures the code.* **The fix: *an exact-match, *per-client registered list.
3. ***A missing `nonce` (ID-token *replay):** *capture an old ID *token; *replay it *to the client. *Without `nonce`, *the client can't tell it's *a *stale token.** *The fix: *a per-request `nonce`, *echoed into the *ID *token.
4. ***PKCE *omitted on a public client (the insecure hybrid):* *a public client *without PKCE; *an attacker *intercepts the code in the redirect.** *The fix: *PKCE (the verifier/challenge *pair, *the code *bound to the *request.
5. ***The refresh *replay (theft detection, 04):** *obtain *a refresh token, *use it → get a new one, *the old is revoked. **Re-send the old one** → *the `refresh_token_reuse` *fires, *the *family is *killed, *re-login forced.* *This is the *deliberate *drill *that proves the *rotation works.
6. ***OAuth-only (no OIDC, *the "no identity" failure):** *do the OAuth *code exchange, *get an access *token, *but *the token has *no `sub`** (OIDC's ID *token is *what gives the `sub`). *The client *knows "the user *allowed scope X" *but not *who the user is.** *The fix: *the OIDC layer (the ID *token with `sub`).

---

## The L5/L6 lens: what panels probe

| Panel probe | The refute they're hunting | The artifact that *stops* it |
|---|---|---|
| "***Which flow, and why?**" | "You'll say 'auth code.' *No the *four / no *the machine case." | ***Human + browser → *auth code (+PKCE).** ***Public (SPA/mobile) → *auth code + PKCE, *no secret.** ***Machine S2S → *client credentials.** ***Session → *refresh (rotating).** *I pick by *whether there's a *user + *whether the client *can hold a secret.** *PKCE is *always, *even for a *confidential client (defense-in-depth). |
| "***What's *the difference between a *scope and a *role?**" | "You'll say 'they're *the same.' *No the *three." | ***Scope = the *grant the IdP stamps on the token (a *category, *`read:docs`).** ***Claim = the *data the RS reads (email, *tenant).** ***Role = the *resource-side policy that *consults the claims to *decide.* **The token is *evidence, the policy is the decision** — *I don't put the whole permission model on the token and call it done." |
| "***Why PKCE? What *does it actually *protect?**" | "You'll say 'it's a *challenge.' *No mechanism." | ***A public client *can't hold a secret. *PKCE *binds the code to the request: *the client *computes a code verifier + its *SHA256 challenge *up front, *sends the challenge *in the auth request, *the verifier *in the token *request. *An attacker who steals *the code *doesn't have the verifier → *the IdP *rejects the *exchange. *It's *what makes the safe auth-code flow *available to a *public client." |
| "***`state`, `nonce`, `redirect_uri` — *why all three?**" | "You'll name two. *No the *three-attack mapping." | "***`state` → *anti-CSRF *on the flow (binds the redirect to the request).** ***`nonce` → *anti-replay of the ID *token (binds the token to the request).** ***`redirect_uri` → *anti-code-injection (only registered URIs). *Each defeats *a different attack; *missing any one is *a weaker flow. This is the *three-params *the *panel will list *for you to complete." |

> **The meta-skill:** for *any* "is this flow safe?" — run the **5-part check**: *which flow (and *why)? / *is PKCE *on? / *are the three params (`state`/`nonce`/`redirect_uri`) *present + verified? / *is the scope-vs-role *split understood (the token is *evidence, the policy is the decision)? / *is the refresh rotating + family-kill on replay? **If you can't produce all five, you've been "doing OAuth" instead of "wiring a *specific, *defeatable flow."**

---

## Cross-refs (two topics interacting → name the sibling)

- **The ID token is a JWT** → `04-jwt` (the *claims, the signature, the `kid`).
- **Client credentials / S2S** → `06-service-accounts` (the *OAuth *version of *a machine tokening as itself; *the k8s *SA *is the *k8s *version of the *same shape).
- **The `aud` binding + refresh rotation** → `04` (the *two *thresholds this *flow wires).
- **PKCE + mTLS** → `06` (the *machine identity: *PKCE binds the *public client's code; *mTLS binds the *workload's cert — *the two "prove it's *the right party" *mechanisms, *one for *a browser client, *one for a *workload).
- **The token the RS verifies** → `04` (JWKS) *and `07` (the *signing key lives in *the KMS).

---

## Exit criteria for this folder

- [ ] You can ***name the four roles** (RO / Client / IdP / RS) *and say *which one *holds the client *secret vs the *refresh token.
- [ ] You can ***pick a flow for a scenario** (human-browser / public-SPA / machine-S2S / *session) *and say *why.
- [ ] You can ***explain PKCE's mechanism** (verifier + *challenge, *the IdP checks the hash, *an attacker without the verifier *can't exchange the code).
- [ ] You can ***map `state`/`nonce`/`redirect_uri` to *the three attacks** they *defeat (CSRF / *replay / *code-injection.
- [ ] You can ***distinguish scope vs claim vs role** and say *where each *lives (token / *token / *resource-side policy).
- [ ] You can ***explain why OIDC is needed** *on top of *OAuth (the *ID token gives *the `sub`; OAuth-only *gives a scope but *no identity.

Next: `06-service-accounts` — the *machine* version of *all of this: *a workload *authenticating as itself, *with its own token/cert, *no human, *no user cred.
