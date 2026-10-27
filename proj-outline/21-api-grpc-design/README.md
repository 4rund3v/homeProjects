# 21 — API and gRPC Design

**Folder:** `21-api-grpc-design/`

---

## Teach first: an API is a *contract*, not an interface

The most common API mistake is designing it *from inside out* — "I have this data structure, here's an endpoint that exposes it." An L6 designs it **from the outside in**: *what does the consumer need, what's the smallest stable contract that serves them, and what will we regret in a year if we get it wrong?*

The two properties that matter more than anything:

- **Stability** — consumers rely on the contract. Breaking it is a *coordination cost* across teams, not a one-file edit.
- **Evolvability** — you *will* add fields, change behavior, deprecate things. The design must let you do that *without breaking consumers.*

> **The L6 frame — the API is the *surface area* you're committing to for years.** Every field, every error code, every default is a promise. Design it like you're *signing a contract with a stranger* because *you will* be, eventually, signing one with another team.

---

## HTTP/REST vs. gRPC — when each is right

| | **REST/JSON** | **gRPC/protobuf** |
|---|---|---|
| Transport | HTTP/1.1, JSON | HTTP/2, protobuf binary |
| Schema | *Implicit* (no contract file) | **Explicit** (`.proto` = the contract) |
| Streaming | Awkward (SSE/WebSocket) | **First-class** (server/client/bidi) |
| Tooling | Anything | Generated clients in 10+ languages |
| Use | Browser-facing, public, interop | Service-to-service, internal, high-perf |

> **The honest tradeoff for this project:** Outline's *public* API (the API Outline exposes to users/other apps) should stay **REST/JSON** — it's what external consumers expect, it's browser-friendly, and it's *documented* for humans. But *your own service-to-service calls* (if you ever split Outline's pieces, add a search microservice, etc.) are **gRPC** territory — explicit contracts, streaming for search, per-language clients.
>
> **The L6 signal is knowing *which one* and *why* for *each* edge.** Defaulting to "gRPC for everything" or "REST for everything" is both wrong. The edge between *a human/browser* and *your internal services* is where you'd switch.

### Why the `.proto` file is the actual artifact

gRPC's whole value is that the `.proto` *is* the contract — versioned, diff-able, *testable in isolation*. A REST API's "contract" is a docs page that drifts; a gRPC contract is a file in Git that CI validates. **An API you can *test without the server* (compile the contract, run a fake) is an API that won't silently break.** That's the L6 difference between "we have an API" and "we have a *versioned, contract-tested* API."

---

## The design rules that separate L5 from L6

### 1. Idempotency (the #1 source of distributed bugs)

- **Idempotent** — same request N times = same result (GET, PUT, DELETE-with-key). Safe to retry.
- **Non-idempotent** — same request N times = N effects (POST that creates a doc). **Retrying it double-creates.**

> **The L6 rule — every mutating operation you'll retry *must* be idempotent**, either by nature or by an **idempotency key** the client supplies. The client sends `Idempotency-Key: <uuid>`; the server dedupes on it. This is *the* mechanism that makes retries safe (doc 18's mesh retries, doc 22's chaos tests). **A non-idempotent POST with a network retry in the mesh = duplicate documents.** Design for the retry from day one.

### 2. Versioning

- **URI versioning** (`/v1/`, `/v2/`) — REST classic. Simple, but *every* new major is a new parallel surface you must maintain.
- **Non-breaking change** — *the actual discipline*: add fields (consumers ignore unknowns), never *remove/rename* fields, never change a field's *meaning.* **This is 90% of what "API versioning" should be: *avoid* the need to version.**
- **gRPC: one service per version** (`ServiceV1`, `ServiceV2`), or add fields in-place (protobuf is *additive*-safe by design — new fields just don't exist on old clients).

> **Threshold — when you *must* version (not just add fields).** Only when you'd have to *change a field's meaning or type*, or *remove* one. Field additions never require a version. The L6 reflex: *"Can I do this additively?"* If yes, no version bump; consumers are unaffected. If no, you *have* a major version + a deprecation window.

### 3. Errors: a stable, machine-readable scheme

- **Don't leak internals** (`"DB error: connection refused to postgres:5432"`). Say *"upstream temporarily unavailable"* — the *consumer* can't fix your DB.
- **Stable codes** — a set of codes consumers *branch on* (`NOT_FOUND`, `PERMISSION_DENIED`, `INVALID_ARGUMENT`, `UNAVAILABLE` in gRPC / 404, 403, 400, 503 in REST). **Adding/removing codes is a breaking change** — it's part of the contract.
- **gRPC error model**: status code + *trailing metadata* for the details. Every error is a `status`, so a consumer can *react* to it deterministically (retry `UNAVAILABLE`, don't retry `INVALID_ARGUMENT`).

> **The L6 detail — error codes are *behavior* contract.** A consumer that retries on `503`/`UNAVAILABLE` but not on `400` is a *correct* consumer. If you "helpfully" change your `503` to a `500`, their retry logic silently stops working. **Treat every status code as part of the API you're committing to.**

### 4. Pagination, not unbounded lists

`GET /docs` with no limit is a *landmine*: page 1 today, 50k docs tomorrow. **Default + cap + cursor.**

- **Cursor-based** (a token the client passes back) > offset-based (`?page=42`) — offset breaks when items shift; a cursor is stable.
- **Server caps the page size** (e.g., max 100). No consumer can accidentally request 1M rows.

> **Threshold — cap every list endpoint.** An unbounded list is a DoS vector (your own consumer can crash you with `?limit=10000000`). The L6 instinct: **no list endpoint has no default and no cap.**

### 5. Field discipline — optional/required + defaults

- **Every field: is it required, optional, and what's the default?** State it explicitly.
- **Additive fields must be *optional* and *default-safe*** — an old client that doesn't know the field gets the default, not an error.
- **`omitempty` / presence semantics matter** in protobuf: `0` vs. "absent" are different, and you must pick.

---

## A concrete L6 design: Outline's "create document" API

```
POST /v1/documents
{
  "idempotency_key": "9f2c…",       # dedupe retry (rule 1)
  "workspace_id": "ws_123",
  "title": "Q4 plan",
  "body": "…",
  "tags": ["q4"]
}

201 Created
Location: /v1/documents/doc_789
{
  "document_id": "doc_789",
  "created_at": "…",
  "etag": "…",                      # for conditional updates (If-Match)
  "version": 1                       # optimistic concurrency
}
```

The L6 touches here:
- **Idempotency key** (rule 1) — retry-safe.
- **`version` + `etags`** — optimistic concurrency for *updates* (`PATCH` with `If-Match: etag`). Two users editing the same doc → one's write is *rejected* with 409, not silently lost.
- **`201` + `Location`** — correct REST semantics for "created."
- **`409 Conflict`** — a *stable code* consumers can branch on (retry after re-fetching).

---

## gRPC: the shape (conceptual, not a build)

```
service Documents {
  rpc CreateDoc(CreateDocRequest) returns (CreateDocResponse);
  rpc GetDoc( GetDocRequest)   returns (Doc);
  rpc Search(SearchRequest)    returns (stream SearchResult);   # server-streaming
}

message CreateDocRequest {
  string workspace_id = 1;
  string idempotency_key = 2;   // the dedupe key
  string title  = 3;
  string body   = 4;
  repeated string tags = 5;     // repeated fields are additive-safe
}
```

> **The L6 protobuf rules:**
> - **Field numbers are permanent.** You *never* reuse or renumber a field number (it's the wire identifier). New field = a new, *higher* number.
> - **`stream`** for the search endpoint (rule: server-streaming = the common "many results over time" case, avoids a giant one-shot response).
> - **Errors** are the `status` code + metadata (rule 3) — consumers branch on `UNAVAILABLE` (retry) vs. `INVALID_ARGUMENT` (don't).

---

## The workflow you'll live in

```
# Contract-first (gRPC): the .proto *is* the source of truth
protoc --go_out=. --go-grpc_out=. api/docs.proto     # generate clients + server stubs
# CI runs a *compatibility check*: does this .proto break the *last released* consumers?
buf breaking                                            # google/buf: the tool that catches "you just broke the contract"

# REST: a OpenAPI spec is your contract; CI validates the server against it
openapi-diff breaking old_spec.yaml new_spec.yaml
```

> **The L6 tool to name-drop:** **`buf`** (for protobuf) and **OpenAPI diffing** (for REST) — *contract compatibility checks in CI.* The moment a PR that changes an API fails a `buf breaking` / `openapi-diff` check, the contract is the gate, not a review comment. **APIs are tested like code — the contract is the test.**

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| REST vs. gRPC | Human/browser-facing → REST. Internal S2S → gRPC. Name the *edge* |
| Idempotency | Every retried mutating op is idempotent via a client-supplied key |
| Versioning | Additive changes = no version. Meaning/removal = major + deprecation window |
| Errors | Stable code set; no internal leaks; consumers *branch* on the codes |
| Pagination | Cursor + default + server cap on *every* list |
| Concurrency | etags / version on updates; 409 Conflict is a *feature* |
| Protobuf | field numbers permanent; new = higher; `stream` for many-results |
| Testing | Contract-in-CI (`buf breaking`, OpenAPI diff) — the contract *is* the test |

---

## Failure modes you must deliberately cause

1. **Retrying a non-idempotent POST** (no idempotency key) → observe duplicate documents. Then add the key; watch duplicates stop. This *is* the lesson.
2. **Removing a field / changing its type** → `buf breaking` (or OpenAPI diff) catches it *in CI*; feel why the contract is a gate.
3. **Two concurrent doc edits** (no etag) → last-write-wins, one user's work silently lost. Add `If-Match`; the loser gets 409.
4. **An unbounded list** (`?limit=` uncapped) → a consumer requests 1M rows; you OOM. Add the cap; feel the DoS surface you just closed.
5. **Change a `503` to a `500`** → a downstream retrier silently stops retrying. Revert; feel why status codes are *contract*.
6. **Protobuf field-number reuse** → old clients mis-read the new field as the old one. Keep numbers permanent; add new ones.

---

## The L5/L6 lens: what this signals

| Probe | L6 answer |
|---|---|
| "REST or gRPC here?" | "Outline's public API stays REST — it's browser-facing and consumers expect it. My *internal* service-to-service calls (if I split it) are gRPC: explicit contract, streaming search, per-language clients. The edge is *a human/browser* vs. *an internal service*." |
| "How do you keep the API stable?" | "90% is *not needing a version* — additive field additions only. A version bump is reserved for the *rare* meaning-change/removal, with a deprecation window. My consumers are my contract; I don't break it casually." |
| "How do you make retries safe?" | "Idempotency key on every mutating op, deduped server-side. Concurrency via etags + 409. No *silent* data loss, no *duplicate* writes." |
| "How do you test the API?" | "The contract is in Git (`.proto`/OpenAPI) and CI runs a *breaking-change* gate (`buf breaking` / OpenAPI diff). The API is tested like code — the contract is the test." |
| "What's your most common bug source?" | "Non-idempotent operations being retried in a distributed system. I design the *dedupe key* in before I build the endpoint, because the mesh retries for me whether I want it to or not." |

---

## Exit criteria

- [ ] You can state, per edge, REST-vs-gRPC and *why* (the edge, not a religion)
- [ ] A mutating endpoint with a client idempotency key; a duplicate-write you caused and then closed
- [ ] Concurrency via etag + 409; the two-edit conflict demo
- [ ] Every list endpoint paged (cursor + cap)
- [ ] A stable error-code set consumers branch on; `buf`/OpenAPI-diff *breaking* gate in CI
- [ ] A protobuf service you *reason* through (not built): field numbers permanent, streaming search, gRPC status errors

Next: `22-testing` — the strategy that decides whether any of this ships safely.
