# DRF + JWT + OAuth2 Hands-On Guide

> Teaches you to build and secure DRF endpoints with JWT and OAuth2, and — more
> importantly — to *reason* about what each layer is doing. No code; concepts,
> decisions, and a hands-on exercise sequence.

---

## 1. The request lifecycle (know this cold)

Every request through DRF passes through a fixed pipeline. Understanding it is what
separates "I copied a tutorial" from "I can debug auth":

```
HTTP request
  → Middleware            (sessions, CORS, request logging)
  → URL routing           (which view?)
  → Authentication        (who is this? → request.user)     ← JWT/OAuth lives here
  → Permissions           (may they do this? → 401/403)
  → Throttling            (rate limits)
  → View / ViewSet        (your logic: validate → service → serialize)
  → Serializer validation (input shape, then service-level rules)
  → Response rendering     (JSON via the serializer)
  → Middleware (response)
```

**The two questions auth answers, in order:**
1. **Authentication** — *who are you?* Produces `request.user` (or `AnonymousUser`).
2. **Authorization** — *may you do this?* Produces allow/deny per object and per action.

Confusing the two is the most common DRF mistake. A valid token proves identity; it
never by itself grants access to a resource. Ownership checks are authorization and
must happen per request.

---

## 2. DRF building blocks you'll actually use

- **Serializers** — define the API shape, validate input, and shape output. They are
  your contract surface (see [`api-contracts-guide.md`](api-contracts-guide.md)).
- **ViewSets + Routers** — map REST verbs (`list/create/retrieve/update/destroy`) to
  methods with almost no boilerplate. Prefer these over function views for resources.
- **GenericAPIView / mixins** — when you need a subset of the standard behavior.
- **Permissions** — classes like `IsAuthenticated`, plus your own `IsOwner`.
- **Authentication classes** — where JWT plugs in.
- **Filtering / pagination** — one consistent scheme across all list endpoints.
- **Throttling** — per-user and anon rate limits at the DRF layer (complements NGINX).

**The thin-view discipline:** a view validates input via its serializer, calls a
service, and returns serialized output. Business rules live in the service/entity
layer (see [`domain-decomposition.md`](domain-decomposition.md)). If your view has an
`if` about loan balances, it's in the wrong place.

---

## 3. Authentication: three approaches, when to use each

DRF ships with several authentication classes. For this project you'll use two,
possibly three:

### a) SessionAuthentication (built-in)
Cookie/session based. Great for the Django admin and browser flows that stay
same-origin. Not ideal for a decoupled React SPA talking to an API.

### b) TokenAuthentication (built-in, simple)
One long-lived token per user stored in the DB. Simple but weak: no expiry, no
scopes, revoked only by deletion. Fine for a toy; learn why JWT improves on it.

### c) JWT (the one you want) — `djangorestframework-simplejwt` or `dj-rest-auth`
Stateless tokens signed by the server. The standard choice for SPA + API.

**Why JWT for this project:** the React UI is a separate origin; JWT lets the API be
stateless (no session store), which matters once you run multiple API replicas behind
NGINX in k3s.

**The JWT trade-off you must understand:** stateless means the server doesn't check a
database to validate a token — so **you cannot instantly revoke it**. Mitigate with:
short-lived access tokens + longer-lived refresh tokens, and a denylist/rotation for
refresh tokens. Decide your lifetimes deliberately and write them in
[`design.md`](design.md).

### d) OAuth2 / social login
Two distinct things get conflated. Separate them:

- **"Login with Google/GitHub"** — you delegate identity to a provider. Your app
  receives a provider token, verifies it, then issues *your own* JWT to the SPA.
  This is **OIDC/social login**, and it's almost certainly what you want.
- **OAuth2 as your own authorization server** — you expose `authorize`/`token`
  endpoints so *other apps* can access your API on a user's behalf. This is what
  `django-oauth-toolkit` provides. Overkill for a personal tracker; learn it, don't
  build it yet.

**Recommended shape for this project:** social login via a provider (or email/password
as the baseline), exchanging verified identity for **your own JWT**. Document the
flow in [`design.md`](design.md).

---

## 4. The JWT flow, concretely

```
1. User logs in (email/password, or "Login with <provider>")
2. Server verifies credentials / provider token
3. Server issues:
     - access token   (short-lived, e.g. 5–15 min, carries user id + claims)
     - refresh token  (long-lived, e.g. days, stored server-side for revocation)
4. SPA stores tokens and sends:  Authorization: Bearer <access token>
5. API middleware/authentication class verifies signature + expiry → request.user
6. Access token expires → SPA calls /token/refresh with the refresh token
7. Refresh token rotates; old one is invalidated (rotation)
```

**Claims to know:**
- `sub` — subject (the user id)
- `exp` — expiry
- `iat` — issued-at
- `jti` — token id (enables denylisting)
- custom claims — sparingly; don't stuff permissions in the token if they change often

**Where tokens live in the SPA (decide deliberately):**
- `localStorage` — easy, but readable by any XSS. Common, not best.
- `httpOnly` cookie — not readable by JS, but needs CSRF protection and same-site
  handling. More secure, more setup.
Pick one, document it, and understand the XSS/CSRF trade-off you're accepting. This
belongs in [`design.md`](design.md).

---

## 5. Authorization: the part people skip

Authentication gets the tutorials. Authorization is where the security bugs live.

**Every resource endpoint must answer: "whose data is this?"**

```text
GET /expenses/            → only the current user's expenses
GET /expenses/<id>/       → 404 (not 403!) if it belongs to someone else
POST /expenses/           → force user_id = request.user, ignore client input
```

**Rules:**
- **Never trust a client-supplied `user_id`.** Derive the owner from `request.user`
  in the view (`perform_create`), never from the request body.
- **Return 404, not 403**, for "exists but not yours" — don't leak existence.
- **Object-level permissions** (`IsOwner`, or `get_queryset` filtered by user) are
  mandatory, not optional. A global `IsAuthenticated` is not enough.
- **Admin vs user** is a separate axis; model it explicitly if you need it.

---

## 6. Securing the endpoints in this project

| Endpoint (concept) | Auth | Authorization |
|--------------------|------|---------------|
| Login / token / refresh / social callback | Public | none |
| Health / readiness / metrics | Public (or internal-only) | none |
| `POST /expenses/` | JWT | owner = request.user |
| `GET /expenses/` | JWT | queryset filtered to request.user |
| `GET /expenses/<id>/` | JWT | object must belong to request.user |
| `GET /loans/`, balance endpoints | JWT | owner-scoped |
| Reporting / summaries | JWT | owner-scoped |
| Admin / debug | JWT + admin role | role check |

Note the **throttling** row you'll add: login endpoints get strict throttles
(brute-force protection); authenticated endpoints get per-user limits. This
complements NGINX rate limiting ([`infrastructure.md`](infrastructure.md)) — DRF
throttling is per-user and semantic; NGINX is per-IP and coarse. Use both.

---

## 7. OpenAPI security (tie-in)

Your auth decisions must show up in the contract:
- Declare the `bearerAuth` (HTTP bearer JWT) security scheme.
- Mark login/token endpoints public; mark everything else as requiring the scheme.
- Use **synthetic** examples only — never a real token.
- Document the 401 vs 403 distinction and the refresh flow.

See [`api-contracts-guide.md`](api-contracts-guide.md) §4 for the details.

---

## 8. Hands-on exercise sequence (Phases 3–4)

Do these in order, each building on the last. Build the smallest version that
teaches the lesson.

1. **Baseline:** stand up DRF with a single `IsAuthenticated` endpoint. Confirm 401
   without a token, 200 with one. *Lesson: the auth/permission pipeline.*
2. **Add JWT:** wire in `simplejwt` (or your chosen lib). Implement login → token
   pair, and a `Bearer` call. Decode your own token at jwt.io and read the claims.
   *Lesson: stateless auth and claims.*
3. **Refresh + rotation:** implement `/token/refresh`. Expire an access token
   deliberately (set a 30s lifetime) and watch the refresh flow work. *Lesson: token
   lifecycle and revocation trade-offs.*
4. **Ownership:** create two users. Prove that user A gets 404 for user B's expense.
   Force `user_id` from `request.user` in `perform_create` and try to spoof it via
   the request body. *Lesson: authorization ≠ authentication.*
5. **Social login (OAuth2/OIDC):** add "login with one provider." Exchange the
   provider token, verify it, mint your own JWT. *Lesson: delegated identity vs.
   being an OAuth server.*
6. **Throttling:** add a strict throttle on login, a per-user throttle on the API.
   Hammer it and watch 429s. *Lesson: rate limiting at the app layer.*
7. **Contract:** generate the OpenAPI doc and confirm the security scheme and
   per-operation auth appear correctly. *Lesson: auth is part of the contract.*

Each exercise has a matching checkpoint in [`checkpoints.md`](checkpoints.md).

---

## 9. Best-practices checklist

- [ ] Auth (identity) and authz (permission) are separate, both enforced.
- [ ] `user_id` is always derived from `request.user`, never from request input.
- [ ] Cross-user access returns 404, not 403.
- [ ] Access tokens short-lived; refresh tokens rotated and revocable.
- [ ] Token storage decision (cookie vs localStorage) documented with its trade-off.
- [ ] Social login issues *your* JWT; you're not running an OAuth2 server (yet).
- [ ] Login endpoints strictly throttled; per-user throttles on the API.
- [ ] Secrets/keys come from the environment, never committed.
- [ ] Security scheme + per-operation auth correct in the OpenAPI contract.
- [ ] Every view is thin; business rules live in services/entities.

---

## 10. Decisions to record in `design.md`

- Auth library (`simplejwt` vs `dj-rest-auth` vs other) and why.
- Access/refresh token lifetimes.
- Refresh token storage & rotation policy.
- SPA token storage (cookie vs localStorage) and the accepted trade-off.
- Social provider(s) and the exact login→JWT flow.
- Throttle rates for login vs authenticated endpoints.
- How object-level ownership is enforced (mixin, permission class, queryset filter).
