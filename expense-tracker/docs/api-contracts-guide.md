# API Contracts Guide — OpenAPI / Swagger

This guide teaches you to **design, generate, review, and maintain** API contracts.
It deliberately includes no OpenAPI YAML, endpoint list, or generated spec. You will
create those as part of the API phases.

---

## 1. Choose one source of truth

With DRF, two contract workflows are common:

### Recommended: code-first generation

Your DRF serializers, views, and explicit schema annotations are the source of truth;
a schema generator produces the OpenAPI document. For a modern DRF project, evaluate
**drf-spectacular** (OpenAPI 3.0/3.1 support, schema customization, typed extensions).
Expose the generated document as JSON/YAML and a Swagger UI/ReDoc viewer in dev.

**Pros:** no duplicate endpoint definitions; schema stays close to implementation.
**Cons:** introspection cannot infer all semantics; you must annotate edge cases and
review the output carefully. Generated does not mean correct.

### Contract-first: hand-maintained OpenAPI

You define the OpenAPI document first; implementation and generated client follow it.

**Pros:** API is reviewed before implementation; useful for teams working in parallel.
**Cons:** easy to drift; requires CI conformance checks and disciplined change control.

For this solo learning project, begin code-first, but treat the generated YAML as a
**versioned, reviewable artifact**. If you later switch contract-first, do so
intentionally rather than maintaining two competing truths.

---

## 2. Define the contract boundary

The public contract describes what an API client can rely on — not the internal
Django model or serializer implementation. Keep it stable even when the persistence
model changes.

For every operation, explicitly decide:

- **Method and path:** resource-oriented naming; plural nouns for collections; avoid
  action verbs except where the operation is truly a command.
- **Request shape:** required/optional fields, types, formats, constraints, examples.
- **Response shape:** success status and body; stable error shape for failures.
- **Authentication/authorization:** which security scheme is required and what
  roles/scopes are allowed.
- **Pagination, filtering, sorting:** define one consistent convention for lists.
- **Idempotency:** which create/payment-like operations accept an idempotency key.
- **Concurrency:** what happens if two updates race (e.g. loan balance changes).
- **Date/time and money:** ISO 8601 with timezone; money as decimal string or
  integer minor units with an explicit currency — never binary floating point.
- **Nullability:** distinguish absent, null, and empty values deliberately.

Avoid exposing database IDs or model fields just because they exist. Do not let the
schema generator silently decide public semantics.

---

## 3. Naming and versioning

- Use stable, descriptive `operationId` values; clients and generated SDKs rely on
  them. Name an operation for its action and resource (e.g. "list expenses"), not
  its Python function.
- Add summaries/descriptions for non-obvious behavior, especially side effects and
  async processing. Keep descriptions useful rather than repeating the name.
- Use reusable components for shared concepts (errors, pagination, security), but
  don't over-generalize schemas that only look similar today.
- Prefer additive, backward-compatible changes: new optional request fields, new
  response fields, new endpoints. Removing or changing types/meaning is breaking.
- Don't version every release. Add `/v2` only when a genuine incompatible public
  contract change is necessary; define deprecation and sunset policy first.
- Keep the OpenAPI document's own `info.version` meaningful and aligned with your
  release/versioning policy.

---

## 4. JWT and OAuth2 in OpenAPI

Document bearer JWT with an HTTP bearer security scheme. OAuth2 authorization-code
flow is appropriate when the API delegates login to an identity provider; don't
mislabel a locally-issued JWT login endpoint as an OAuth2 authorization server.

Document which operations are public, user-authenticated, or admin-only. OpenAPI
security is per-operation; don't mark the entire API authenticated if health checks
or login/token acquisition are public. Never put real tokens, client secrets, or
personal data in examples. Use obviously fake values.

Keep authentication concerns separate from authorization semantics: a valid token
does not imply access to another user's expense. Every resource lookup must enforce
ownership/tenant scope server-side.

---

## 5. Errors, pagination, and asynchronous work

**Errors:** establish a consistent error response envelope, with machine-readable
code, human-readable message, field errors where relevant, and a request/trace ID.
Don't leak stack traces or internal database details. Document common HTTP statuses
and the cases that produce them.

**Pagination:** choose offset/limit or cursor pagination. Offset is simple; cursor is
more stable as the collection changes and scales better. Use the same shape for every
list endpoint, define maximum page size, and document ordering guarantees.

**Async expense processing:** the POST that accepts an expense can return success
once the expense is durably recorded and its event is durably enqueued. It must not
claim the loan balance is already updated. Decide whether the response includes a
processing status, whether clients poll a resource, or whether they use a separate
status endpoint. Document the eventual-consistency window and retry behavior.

---

## 6. Validation workflow

Run this cycle every time the API changes:

1. Generate the OpenAPI document from the current DRF code.
2. Validate it with the schema generator's validation command and an independent
   OpenAPI validator in CI.
3. Review the diff as a public API change: path, type, requiredness, nullable, status,
   auth, examples, and descriptions.
4. Run a breaking-change check against the last released schema. Block incompatible
   changes unless an explicit version/deprecation decision is approved.
5. Generate the React TypeScript client/types from the validated schema. Do not hand
   copy API types into the UI.
6. Run client type checks and contract tests against the API implementation.
7. Publish the schema artifact alongside the application release; associate it with
   the same commit/image version.

A schema snapshot test can detect unreviewed changes, but update snapshots only after
reviewing the actual contract diff. Never blindly regenerate and accept.

---

## 7. Testing contract conformance

Use complementary layers:

- **Schema validation:** document is valid OpenAPI.
- **Implementation conformance:** responses/statuses match the schema; test with a
  request/response validator where practical.
- **Endpoint tests:** auth, permissions, validation, pagination, errors, and ownership.
- **Consumer tests:** generated UI client compiles and exercises real API behavior.
- **Compatibility checks:** released clients still work with additive API changes.

The schema generator can produce a plausible but incomplete contract. Explicitly test
manual annotations, polymorphic fields, error responses, and auth on each operation.

---

## 8. Security and privacy review

Before publishing or generating a client, check that the schema does not expose:

- Internal admin/debug endpoints or fields.
- Secrets, token material, internal hostnames, or real personal financial examples.
- Endpoints missing ownership/tenant authorization.
- Overly detailed errors that reveal whether another user's resource exists.

Treat the schema as public documentation even if the API itself is private. Keep
examples synthetic and keep private deployment URLs out of the published contract.

---

## 9. Where to keep the contract and how to review it

As you build your own repo layout, choose one canonical location for the generated
schema and document that decision. Ensure there is exactly one source of truth and
that CI can regenerate and compare it deterministically. Check in the YAML if you
want human-readable API review and stable client generation; otherwise publish it as
a build artifact. Don't keep a hand-written YAML, generated YAML, and separate
frontend type definitions all independently editable.

Every contract change should answer in its pull request/commit review:

- Is it backward compatible?
- Does the implementation match the schema?
- Does generated UI client code still compile?
- Are auth and ownership rules correct?
- Is async behavior described honestly?
- Are examples synthetic and safe?

---

## 10. Decisions to record in `design.md`

- Code-first or contract-first, and why.
- Schema generator and OpenAPI version.
- Whether schema YAML is checked in or published as a build artifact.
- How API versions and deprecations are handled.
- Pagination and error response conventions.
- JWT/OAuth2 model and per-operation security policy.
- How clients are generated and breaking changes detected.
