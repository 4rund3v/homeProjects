# Go HTTP Server

**Goal:** Build a small, well-tested Go HTTP service and learn its lifecycle and boundaries.

**Scope:** `net/http`, routing, middleware, structured logging, validated configuration, health/readiness endpoints, graceful shutdown.

**Out of scope:** Database and identity-provider integration.

**Learning focus:** Middleware composition, dependency injection, request contexts, operational shutdown, startup validation.

**Depends on:** `go-fundamentals`.

**Reuse:** Server lifecycle and middleware patterns inform `tls-setup`, `network-tracer`, and `raft-adv`; extract shared packages only after a real reuse case appears.

## Milestones
- [ ] Serve one JSON endpoint using the standard library.
- [ ] Add logging and recovery middleware with tests.
- [ ] Add validated configuration and health/readiness endpoints.
- [ ] Handle SIGTERM gracefully and test in-flight request behavior.
