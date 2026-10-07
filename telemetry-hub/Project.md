# Telemetry Hub

## What this project exists to solve
Learn structured observability by instrumenting a real Python API, collecting telemetry with a Go collector, and flowing logs, metrics, and traces to a local destination. The focus is on what each signal type is for, how context propagates across process boundaries, and what it means operationally.

## Success criteria / completion metrics
- Python web API with structured logs and instrumented request/DB trace flow using OpenTelemetry.
- A Go collector/pipe that receives telemetry and emits to a local destination (for example syslog) or a local observability backend.
- End-to-end trace demonstrated from an HTTP request through API and database to the local sink; the trace is inspectable and explained.
- API contract documented in OpenAPI; a health/status endpoint is present.
- A defined workload is measured with `profiling-lab`-style methodology; profiling artifacts are saved and interpreted.
- Local image builds and local CI pipeline gate formatting, tests, and image builds.

## Prerequisites and dependencies
- `drf-basics`, `go-http-server`, `go-fundamentals`, `postgres-lab`.
- `profiling-lab` methodology before any performance optimization.
- `uv` environment workflow for Python (see `../uv-setup.md`).

## Tools, libraries, and runtime
- Python: OpenTelemetry SDK, a web framework (FastAPI or Django), PostgreSQL driver, `uv`, pytest, ruff, mypy.
- Go: OTel SDK/collector components, structured logging, OTLP export.
- Local log destination (syslog or similar).
- Docker Compose for API, database, collector, and destination.
- Optional: Prometheus metrics exposition and Grafana dashboard if the backend is local.
- Jenkins or another chosen local CI runner.

## Learning objectives (skills practiced)
- Logs, metrics, and traces: what each captures, how they relate, when to choose one over another.
- OpenTelemetry data model, semantic conventions, and protocol (OTLP/gRPC or OTLP/HTTP).
- Context propagation across Go and Python boundaries.
- Structured logging vs. printf logging.
- Database instrumentation and span attributes.
- Local telemetry pipeline architecture and operational configuration.

## Architecture / design note
Separate concerns so each component has a clear boundary:

```
api/                        # Python service
  app/
    main.py
    routes.py
    models.py
    telemetry.py            # OTel instrumentation
  tests/
  pyproject.toml
  Dockerfile
collector/                  # Go collector
  cmd/collector/main.go
  internal/
    otlp.go
    exporter.go
    config.go
  Dockerfile
docker-compose.yaml
```

API and collector communicate via OTLP; both send logs/traces to the local destination. The database is local Postgres. Keep the architecture minimal; add metrics and dashboards only if they clarify a signal.

## Test strategy
- API tests for successful request, invalid input, not found, and unauthenticated cases.
- Telemetry tests verify that a request produces a trace with expected attributes.
- Collector tests verify it receives and forwards events; use a mock or local sink.
- End-to-end test in Docker Compose verifies a request → API → DB → collector → sink chain.
- CI runs Python tests via `uv`, Go tests via `go test`, container builds, and an optional smoke test.

## Documentation checklist
- Architecture diagram: API, DB, collector, destination, and how they communicate.
- Local run and Docker Compose instructions with environment variables.
- Telemetry flow explanation with example traces and log entries.
- Profiling notes with workload definition, baseline, and interpretation.
- API contract with OpenAPI and curl examples.

## API contract
OpenAPI for the Python API. Document request/response, errors, auth, and health endpoints.

## UI / status surfaces
A small health/status page for the API and optionally the collector. Do not build a full observability UI; the destination is a local sink.

## Security boundaries to think about
- Do not send PII in traces or logs by default; document what is and is not captured.
- OTel receivers and exporters should be authenticated or local-only by default.
- Keep secrets out of configuration files in source control.
- Protect local debug endpoints and pprof.

## Profiling plan
Define a fixed request workload (for example, 100 sequential requests). Profile the API and collector separately; identify hot paths and compare against a pre-change baseline using the methodology from `profiling-lab`.

## How this project fits into the curriculum
First cross-language integration project. Its patterns (structured logs, traces, local destination) inform later `keycloak-setup` observability and `k3s-helm` deployment.

## Suggested milestone walkthrough
1. **Python API with structured logs.** Implement the API with structured log output; run locally.
2. **OTel instrumentation.** Instrument the API; export traces to stdout; verify spans for a request.
3. **Go collector.** Receive OTLP and emit to a local sink; verify end-to-end flow.
4. **Workload and profile.** Define a request workload; profile and interpret.
5. **Container + CI.** Compose the services; CI runs format, tests, and builds.

## Reference notes and resources
- OpenTelemetry documentation and semantic conventions.
- Python OTel SDK docs.
- Go OTel SDK/collector docs.
- OTLP protocol reference.
