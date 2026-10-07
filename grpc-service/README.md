# gRPC Service

**Goal:** Build a cross-language gRPC service in Go and Python to learn Protocol Buffers, RPC patterns, and the gRPC operational model.

**Scope:** proto3 IDL, protoc code generation, unary and server-streaming RPCs, interceptors (logging, panic recovery, API-key auth), gRPC health checking, cross-language Go↔Python calls.

**Out of scope:** Database integration, bidirectional streaming, TLS (noted as optional future step), production deployment.

**Learning focus:** Proto3 schema design, stub generation with `protoc`, gRPC status codes and error model, interceptor chaining, health check protocol, gRPC vs REST vs message-queue tradeoffs.

**Depends on:** `go-fundamentals`, `go-http-server`.

## Milestones
- [ ] Define a proto3 service, generate Go and Python stubs with `protoc`, implement a unary echo RPC callable from both languages.
- [ ] Add a server-streaming RPC; handle partial failures and mid-stream errors using gRPC status codes.
- [ ] Add server interceptors: structured logging, panic recovery, and API-key header auth; test each independently.
- [ ] Implement the `grpc_health_v1` health check protocol; verify with `grpc_health_probe` or `grpcurl`.
- [ ] Write a comparison note: REST vs gRPC vs message queues — semantics, tradeoffs, and when each fits.

**Environment (Python):** See [`uv-setup.md`](../uv-setup.md).
