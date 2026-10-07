# Telemetry Hub

**Goal:** Trace one request across a Python API, PostgreSQL, and a Go-based telemetry pipeline.

**Scope:** Python web API, PostgreSQL, structured logs, OpenTelemetry instrumentation, OTLP collection/export, and a local log sink such as syslog.

**Out of scope:** Production retention, alerting, and a full frontend product.

**Learning focus:** Logs vs. metrics vs. traces, context propagation, service boundaries, database instrumentation, operational configuration.

**Depends on:** `drf-basics`, `go-http-server`, `go-fundamentals`.

## Milestones
- [ ] Serve a small API and persist a request to PostgreSQL.
- [ ] Emit structured logs and trace a request through the database call.
- [ ] Configure a Go collector to receive and export telemetry locally.
- [ ] Verify the end-to-end trace and document what is and is not captured.
