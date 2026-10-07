# Go HTTP Server

## What this project exists to solve
Learn how a small Go HTTP service is structured, configured, tested, observed, and shut down. It is the first deployable Go service and later provides patterns (not necessarily a shared library) for TLS, network-tracer, and Raft.

## Success criteria / completion metrics
- API endpoints documented with OpenAPI when the API surface is more than a trivial exercise.
- JSON handlers have unit and HTTP integration tests, including invalid input and error responses.
- Validated configuration, structured logs, health/readiness endpoints, and graceful SIGTERM shutdown.
- Local Docker image builds reproducibly; local CI runs formatting, tests, vet, and build on a push.
- Demonstrate one measured request workload with baseline latency/throughput if useful to the service.

## Prerequisites and dependencies
- `go-fundamentals` packages, errors, tests, contexts, and race detector.
- Docker available for container milestone.

## Tools, libraries, and runtime
- Go `net/http`; optional router `chi` only after comparing stdlib routing.
- `slog` for structured logs; YAML/TOML/JSON config with explicit validation.
- OpenAPI generator/spec chosen after API design.
- Docker; local Jenkins or GitHub Actions for CI (first CI pipeline can be a small local runner; no cloud deployment required).

## Learning objectives (skills practiced)
- HTTP request/response lifecycle, status codes, method semantics, timeouts.
- Middleware composition and ordering.
- Dependency injection via constructors rather than globals.
- Graceful shutdown, readiness vs. liveness, signal handling.
- Config precedence and startup validation.
- Container image layering, non-root execution, health checks.
- CI pipeline stages: format → lint/vet → unit tests → build → image build.

## Architecture / design note
Suggested layout:
```
cmd/api/main.go
internal/config/
internal/handler/
internal/middleware/
internal/service/
api/openapi.yaml
Dockerfile
Jenkinsfile
```
Keep handler parsing/response concerns separate from domain behavior. Do not extract `pkg/server` prematurely; later consumers may copy patterns or extract only proven generic code.

## Test strategy
- Unit tests for service/domain packages.
- HTTP handler tests using `httptest`, including malformed JSON, unknown routes, and request cancellation.
- Integration smoke test against the built container.
- Run `go test -race ./...`, `go vet ./...`, and formatter/linter in CI.

## Documentation checklist
- `README.md`: build/run, configuration, curl examples, shutdown behavior.
- OpenAPI contract and generated Swagger UI only if the API merits it.
- Architecture decision notes for router, middleware order, and config approach.
- Docker image build and local run instructions.

## API contract
Start with `GET /healthz`, `GET /readyz`, `GET /api/v1/hello`. Define stable JSON/error response shape. Add OpenAPI when adding more than the basic learning routes; test documented examples against the implementation.

## UI / status surfaces
A small root page can link to API docs and show service/version/status. Do not make a large frontend.

## Security boundaries to think about
- Set request/header/read/write/idle timeouts.
- Avoid logging credentials or entire request bodies by default.
- Validate input at handler boundaries and cap body size.
- Run container as non-root; minimize image contents and secrets.
- Protect pprof if enabled; never expose profiling endpoints on a public listener.

## Profiling plan
Use the `profiling-lab` methodology. Establish a repeatable request workload before tuning; use pprof only on a local/debug listener, compare allocations and latency, and do not optimize based on a single run.

## How this project fits into the curriculum
This is the first web service. `tls-setup`, `network-tracer`, `raft-adv`, and later Homer service links can reuse its operational patterns. Its Docker build and CI provide the first end-to-end push → test → image loop.

## Suggested milestone walkthrough
1. **First endpoint.** Serve JSON with stdlib; test through `httptest`.
2. **Operations.** Add config, logs, middleware, timeouts, health endpoints, and graceful shutdown.
3. **Contract and homepage.** Add OpenAPI and a lightweight root page; verify examples.
4. **Container.** Build and run locally as non-root; inspect logs and health checks.
5. **CI.** Create a Jenkins pipeline that formats, tests, vets, and builds on a local push. Document each stage; do not add deployment automation until these gates work.
6. **Measure.** Define a request workload and profile only if it answers a performance question.

## Reference notes and resources
- Go `net/http`, `httptest`, `slog`, and `context` documentation.
- Twelve-Factor App configuration principles.
- Docker multi-stage build documentation.
- Jenkins Pipeline documentation; local Jenkins container is one option.
