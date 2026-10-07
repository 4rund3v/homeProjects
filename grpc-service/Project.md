# gRPC Service

## What this project exists to solve
REST and Kafka are already taught; gRPC is the missing transport for typed, contract-first, high-throughput internal APIs. This project fills that gap by having the learner own the full cycle: define a `.proto` contract, generate stubs for two different languages, run a real server, and call it from a client in each language. It also sharpens the mental model for when gRPC is the right choice and when it is not.

## Success criteria / completion metrics
- A `.proto` file defines at least one unary RPC and one server-streaming RPC; generated Go and Python stubs are committed alongside the source.
- A Go gRPC server satisfies both RPC types and is runnable via Docker.
- A Python client (using `grpcio`) successfully calls both RPCs against the running Go server; a Go client calls the same server.
- Three interceptors (logging, panic recovery, API-key auth) are wired in order and individually tested.
- The server passes `grpc_health_v1` health checks verified by `grpc_health_probe` or `grpcurl`.
- A written comparison note (markdown) covers REST, gRPC, and message queues with concrete tradeoff statements.

## Prerequisites and dependencies
- `go-fundamentals`: Go modules, interfaces, error wrapping, contexts, goroutines.
- `go-http-server`: middleware composition patterns and operational readiness — interceptors here map directly to that middleware experience.
- `protoc` and plugins (`protoc-gen-go`, `protoc-gen-go-grpc`) installed locally or via a codegen container.
- Docker available for server container; Python `uv` environment for Python client work.

## Tools, libraries, and runtime
- Go: `google.golang.org/grpc`, `google.golang.org/protobuf`, `google.golang.org/grpc/health`.
- Python: `grpcio`, `grpcio-tools`, `grpcio-status`, `grpcio-reflection`; environment via `uv`.
- `protoc` (Protocol Buffers compiler); `protoc-gen-go`; `protoc-gen-go-grpc`.
- `grpcurl` for ad-hoc RPC invocation and reflection inspection.
- `grpc_health_probe` for health check verification.
- Docker for packaging and running the Go server.

## Learning objectives (skills practiced)
- Authoring proto3: message types, field numbers, `repeated` fields, service and RPC definitions.
- Running `protoc` with multiple plugins; understanding where generated files land and why.
- Distinguishing unary, server-streaming, client-streaming, and bidirectional RPC shapes (implement the first two; understand all four).
- Using gRPC status codes (`codes.NotFound`, `codes.InvalidArgument`, etc.) instead of ad-hoc errors.
- Writing and ordering server-side interceptors; understanding the interceptor chain contract.
- Implementing the `grpc_health_v1` protocol and what health probes actually check.
- Using gRPC server reflection to introspect a live server without a `.proto` file.
- Articulating REST vs gRPC vs Kafka tradeoffs with reference to real project experience.

## Architecture / design note
Suggested layout:
```
proto/
  echo/v1/echo.proto
gen/
  go/echo/v1/          ← generated Go stubs (committed)
  python/echo/v1/      ← generated Python stubs (committed)
server/
  cmd/main.go
  internal/handler/
  internal/interceptor/
client/
  go/main.go
  python/client.py
Dockerfile
Makefile               ← codegen, build, and run targets
docs/
  comparison.md        ← REST vs gRPC vs message queues
```
Commit generated stubs so the project is self-contained without requiring `protoc` at build time. Use a `Makefile` target for regeneration. Define the proto package namespace carefully — changing it later is painful.

## Test strategy
- Unit tests for each interceptor in isolation using a fake `grpc.UnaryHandler`.
- Integration test: start the server in-process using `bufconn` (in-memory gRPC connection), call both RPCs from a Go test, assert on status codes and response payloads.
- Streaming test: consume all messages from the server-streaming RPC and assert on the sequence; inject a mid-stream error and verify the client receives the correct status code.
- Health check test: call the health service via the `bufconn` connection; assert `SERVING` status.
- Run `go test -race ./...` in CI.

## Documentation checklist
- `README.md`: proto-to-stub codegen command, Docker build and run, curl/grpcurl examples for each RPC, health probe invocation.
- `docs/comparison.md`: REST vs gRPC vs message queues tradeoff note (the Milestone 5 deliverable).
- Inline proto comments on every message and RPC field (these become API documentation).
- `Makefile` targets documented with `##` comments for `make help`.

## API contract
gRPC service defined in `proto/echo/v1/echo.proto`:
- `EchoService.Echo (EchoRequest) returns (EchoResponse)` — unary.
- `EchoService.EchoStream (EchoRequest) returns (stream EchoResponse)` — server streaming.
- `grpc.health.v1.Health.Check` — standard health protocol.
No HTTP REST endpoints; use `grpcurl` or the generated clients for all calls.

## UI / status surfaces
None. CLI output only — `grpcurl` and `grpc_health_probe` are the primary interaction surfaces.

## Security boundaries to think about
- API-key interceptor: extract key from `authorization` metadata header; reject with `codes.Unauthenticated` on missing or wrong key. Do not log the key value.
- Input validation: validate proto fields in handler code (non-empty message, bounded length); return `codes.InvalidArgument` with a descriptive status message — do not panic.
- TLS: document the steps to add server TLS via `grpc.Creds`; leave it as an optional follow-on after the core milestones pass.
- Docker: run the server container as non-root; do not bake secrets into the image.
- Reflection: disable server reflection in a production build note; it exposes the full schema to unauthenticated callers.

## Profiling plan
Profile only if a performance question arises. If benchmarking gRPC vs REST, use `ghz` for gRPC load generation and compare with an equivalent `wrk` or `hey` HTTP run at the same concurrency. Measure allocations with `go test -bench -memprofile` only after establishing a stable baseline.

## How this project fits into the curriculum
This is Phase 2.5 (project 21), sitting between the Web & Persistence cluster and the Security cluster. It depends on `go-fundamentals` and `go-http-server` for Go idioms and middleware patterns. It unlocks informed transport choice in every subsequent service project — learners can now consciously choose REST, gRPC, or Kafka rather than defaulting to HTTP. The interceptor experience also directly prepares for the authentication and authorization concerns in the Security phase.

## Suggested milestone walkthrough
1. **Proto and stubs.** Write `echo.proto` with a single unary `Echo` RPC. Run `protoc` to generate Go and Python stubs. Commit the generated files. Implement the handler in Go; call it from both a Go client and a Python client. Confirm round-trip works.
2. **Streaming.** Add `EchoStream` server-streaming RPC. Stream N response messages then close. Inject a deliberate mid-stream error on a specific input; verify the client receives the error status code without crashing.
3. **Interceptors.** Implement logging (log method, duration, status code), panic recovery (convert panics to `codes.Internal`), and API-key auth interceptors. Wire them in the correct order. Test each with `bufconn` by triggering the relevant condition.
4. **Health checking.** Register `grpc_health_v1` on the server. Set service status to `SERVING` after startup. Verify with `grpc_health_probe -addr=:50051`. Add a liveness pattern: flip status to `NOT_SERVING` on a deliberate shutdown signal and observe probe failure.
5. **Comparison note.** Write `docs/comparison.md` covering: request/response semantics, schema enforcement, streaming support, observability, client coupling, and operational complexity — for REST, gRPC, and Kafka. Anchor each claim to something observed in this project or a prior one.

## Reference notes and resources
- [Protocol Buffers Language Guide (proto3)](https://protobuf.dev/programming-guides/proto3/)
- [gRPC Go quickstart and core concepts](https://grpc.io/docs/languages/go/)
- [gRPC Python quickstart](https://grpc.io/docs/languages/python/)
- [gRPC health checking protocol](https://grpc.io/docs/guides/health-checking/)
- [`grpcurl` README](https://github.com/fullstorydev/grpcurl) — ad-hoc gRPC calls and reflection
- [`ghz`](https://ghz.sh/) — gRPC benchmarking tool
- [gRPC status codes reference](https://grpc.github.io/grpc/core/md_doc_statuscodes.html)
- `bufconn` package docs for in-process gRPC testing
