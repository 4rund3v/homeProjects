# Caching and Gzip

> When to cache at the edge, how to cache static UI assets safely, why caching an API
> response is almost always a bug, and how to configure compression correctly.

---

## 1. The big rule for this project

```
  ┌─────────────────────────────────────────────────────────────┐
  │                                                               │
  │   UI static assets (JS/CSS/font/image):  AGGRESSIVELY cache  │
  │   API responses (JSON with user data):   NEVER cache         │
  │                                                               │
  │   The distinction is NOT about content type. It's about       │
  │   whether two DIFFERENT users can ever see the same bytes.    │
  │                                                               │
  └─────────────────────────────────────────────────────────────┘
```

An API response for user A is user-A-specific; caching it by URL alone serves it to
user B. The `Vary: Authorization` header is the guard, and it's the header most
implementations get wrong (§4).

---

## 2. `proxy_cache` — the mechanics

```nginx
http {
    proxy_cache_path /var/cache/nginx
                     levels=1:2
                     keys_zone=ui_cache:10m
                     max_size=500m
                     inactive=7d;

    server {
        location /ui/ {
            proxy_pass http://ui-backend;
            proxy_cache ui_cache;
            proxy_cache_key "$scheme$request_method$host$request_uri";
            proxy_cache_valid  200 10m;
            proxy_cache_bypass $http_authorization;   # ★ see below
            proxy_no_cache     $http_authorization;
        }
    }
}
```

| Directive | Meaning |
|-----------|---------|
| `proxy_cache_path` | where the cache lives, with sizing |
| `proxy_cache_key` | the cache key — **must encode everything that affects the response** |
| `proxy_cache_valid` | TTL per status code |
| `proxy_cache_bypass` | **if this is set, DON'T use the cache** (read-through bypass) |
| `proxy_no_cache` | if this is set, DON'T STORE the response |

### The cache key

The key is the identity of the response. Omit a varying input from the key and you'll
serve user A's response to user B:

```
  WRONG (serves authenticated responses across users):
    proxy_cache_key "$scheme$host$request_uri";

  RIGHT (includes the auth header, so different users get different keys):
    proxy_cache_key "$scheme$host$request_uri$http_authorization";

  BETTER (don't cache auth'd responses at all — see §4):
    proxy_cache_bypass $http_authorization;
    proxy_no_cache     $http_authorization;
```

---

## 3. `Cache-Control` and `Vary` — the HTTP headers

### `Cache-Control`

```
  Cache-Control: public, max-age=300
  • public:     any cache (browser, nginx) may store it
  • private:    only the browser may store it (not shared caches)
  • max-age=N:  fresh for N seconds from now
  • no-store:   never cache at all
  • no-cache:   cache allowed, but must REVALIDATE before reuse
  • s-maxage=N: like max-age but only for SHARED caches (nginx)
  • immutable:  the URL's content never changes while valid (aggressive)
```

### `Vary`

Tells caches: "if the *input value* differs, treat as a different cache entry."

```
  Vary: Accept-Encoding, Authorization
  • two requests differing only in Authorization header are DIFFERENT entries
  • without this, a cache can serve one user's bytes to another user
```

### The `Vary: Authorization` trap

```
  ┌────────────────────────────────────────────────────────────────┐
  │  Request A:  GET /api/expenses  Authorization: token-for-USER-A │
  │    Response: cached under key "GET /api/expenses"  ← WRONG      │
  │                                                                   │
  │  Request B:  GET /api/expenses  Authorization: token-for-USER-B │
  │    Response: cache HIT → served USER-A's expenses to USER-B      │
  │                                                                   │
  │  FIX: either                                                      │
  │    (a) send `Vary: Authorization` AND include it in the key,      │
  │        or                                                         │
  │    (b) send `Cache-Control: private, no-store` and don't cache.  │
  │                                                                   │
  │  For authenticated APIs: (b) is almost always right.             │
  └────────────────────────────────────────────────────────────────┘
```

**Rule of thumb:** authenticated API endpoints should send
`Cache-Control: private, no-store` from the *application* and nginx should bypass the
cache for anything with an `Authorization` header. Do not try to make caching
authenticated API responses "work" by clever keying — you'll miss one varying input and
leak data across users.

---

## 4. Stale-while-revalidate and stale-if-error

```
  Cache-Control: max-age=60, stale-while-revalidate=300, stale-if-error=86400

  t=0s        cache MISS → fetch upstream, cache for 60s
  t=61s       STALE, but within stale-while-revalidate
              → return cached response, KICK OFF a background refresh
              → the NEXT request gets the fresh response
  t=300s      within stale-if-error
              → return cached even if upstream is DOWN
  t=86400s    hard expired → 5xx
```

**When it helps:** a page where stale-for-a-minute is fine but stale-during-an-outage
is much better than a 503. Good for UI static assets, bad for a financial number.

---

## 5. Invalidation and cache busting

```
  Problem: the app redeploys with a new bundle. Old users hold the old
           hash in their URL, but the new bundle is served. Broken.

  Solutions:
  ┌────────────────────────────────────────────────────────────────┐
  │  1. Content-hash in the filename                                │
  │     index.9a3f1b.js   ← browser cache key is inherently unique │
  │     → cache safely with very long max-age                       │
  │                                                                 │
  │  2. Query-string versioning (fragile)                           │
  │     index.js?v=2026-10-17                                       │
  │     → works, but pollutes your URL and can break ETags          │
  │                                                                 │
  │  3. Explicit purge (needs a purge mechanism)                    │
  │     nginx.openresty.org has built-in purge; OSS doesn't         │
  └────────────────────────────────────────────────────────────────┘

  1 is the modern answer and what the LLM-generated UI should produce.
```

---

## 6. Serving the React SPA — the `try_files` gotcha

The React UI is an SPA: all routes are client-side, so any path that doesn't match a
static asset must serve `index.html`.

```nginx
location /ui/ {
    alias /var/www/ui/;

    # serve if the file exists, else fall back to index.html for the SPA router
    try_files $uri $uri/ /ui/index.html;
}
```

**The gotcha:** if the SPA is served at `/` and the API at `/api`, a misconfigured
`try_files` can swallow `/api/foo` and return `index.html` for it.

```
  BAD:
    location / { try_files $uri /index.html; }
    → GET /api/foo (with no matching backend) → returns index.html (404 as HTML)
    → the API client gets HTML where it expects JSON. Total confusion.

  GOOD (explicit ordering):
    location /api/  { proxy_pass http://api; }   ← more specific wins
    location /ui/   { alias /var/www/ui; try_files ... /ui/index.html; }
    location /      { try_files $uri /ui/index.html; }
```

---

## 7. Gzip and Brotli

```nginx
gzip on;
gzip_vary on;                # add Vary: Accept-Encoding automatically
gzip_proxied any;            # compress even proxied/cached responses
gzip_min_length 1024;        # skip tiny responses (compression overhead)
gzip_types
    text/css
    text/javascript
    application/javascript
    application/json
    application/xml
    image/svg+xml
    text/plain;

# NEVER: image/jpeg, image/png, image/webp  ← already compressed
# NEVER: text/event-stream                  ← breaks streaming
```

**Why `gzip_vary` matters:** different clients accept different encodings. Without
`Vary: Accept-Encoding`, a cached gzip response can be served to a client that asked
for `identity` — corrupt bytes. `gzip_vary on` fixes this automatically.

**Compression levels (in `gzip_comp_level`, default 6):**
- Low levels: fast, weaker compression. Fine for API JSON on the hot path.
- High levels: slower, better compression. Fine for static assets served at low rate.

**Double compression is wasteful:** if the *application* already gzips (some ASGI
stacks do), nginx compresses twice. Pick one layer.

**Brotli** compresses ~20% better than gzip for text but is slower to encode. Worth it
for static assets with long caches; not worth it for streaming APIs.

---

## 8. Interview angle

- **"When do you cache an API response?"** — never for authenticated per-user responses.
  Send `Cache-Control: private, no-store` and bypass at the proxy.
- **"What does `Vary: Authorization` do, and why is it a trap?"** — it makes auth
  headers part of the cache key, but it's easy to forget; a missing `Vary` can leak
  user A's data to user B.
- **"How do you bust caches on a deploy?"** — content-hashed filenames (immutable
  assets + a short-cached index.html).
- **"What does `gzip_vary` prevent?"** — serving gzip bytes to a client that didn't
  ask for gzip.
- **"Stale-while-revalidate?"** — return stale, refresh in background; good for assets,
  bad for anything that must be exactly right.

---

## 9. How this shows up here

- The React UI is served as static files with a long `max-age` and content-hashed
  names; the SPA fallback uses `try_files`.
- The API never goes through `proxy_cache` — endpoints return
  `Cache-Control: private, no-store` from DRF.
- Gzip for text/* and application/json; never compress images.
- The SPA-vs-API ordering rule (`/api` before the SPA catch-all) is the specific bug to
  avoid when wiring the ingress.
