# Django REST Framework Basics

## What this project exists to solve
Refresh Python in a realistic backend framework: build a small, well-tested REST API, persist its data in PostgreSQL, and understand how Django/DRF abstractions relate to HTTP, SQL, and Python objects.

## Success criteria / completion metrics
- CRUD API with validation and error semantics documented in OpenAPI/Swagger.
- Unit/API tests for success, invalid input, not-found, unauthenticated, and unauthorized cases.
- Migrations reproducibly create a fresh PostgreSQL database.
- Authentication is explicit and authorization is tested at the API boundary.
- `uv sync` and documented `uv run` commands work from a clean checkout.
- Docker image and a local CI pipeline run once the core API behavior is stable.

## Prerequisites and dependencies
- `python-refresh`; PostgreSQL fundamentals from `postgres-lab` are useful.
- `uv` environment workflow: [`../uv-setup.md`](../uv-setup.md).

## Tools, libraries, and runtime
- Python (pin supported version in `pyproject.toml`), `uv`.
- Django, Django REST Framework, psycopg, drf-spectacular.
- pytest, pytest-django, ruff, mypy as appropriate.
- PostgreSQL in Docker; Docker for the application container milestone.
- Jenkins local pipeline or another chosen CI runner after tests are understood.

## Learning objectives (skills practiced)
- Django app/project structure and settings.
- Models, migrations, ORM query behavior, and raw SQL comparison.
- Serializers as validation/representation boundaries.
- Viewsets, routers, permissions, authentication.
- API versioning, pagination, errors, OpenAPI contract.
- Python test fixtures, integration boundaries, and DB transaction behavior.
- Python dependency/environment management with `uv`.

## Architecture / design note
Keep Django's framework structure, but separate domain decisions from serializers and views where that clarifies behavior. Do not introduce a large service/repository abstraction just to mimic Go. Use explicit settings for local/test configuration and a PostgreSQL service in Docker Compose for integration tests.

## Test strategy
- Unit tests for model invariants and domain logic.
- API tests with DRF's test client for request/response behavior.
- Integration tests run against PostgreSQL, not only SQLite, for migration/constraint behavior.
- OpenAPI schema generation is checked in CI for accidental drift (review diffs rather than blindly updating).

## Documentation checklist
- API setup and local development with `uv`.
- OpenAPI/Swagger docs and representative curl examples.
- Data model and migration notes.
- Authentication and permission matrix.
- Docker build/run instructions and environment variable reference.

## API contract
OpenAPI via drf-spectacular. Document request/response schemas, status codes, pagination, authentication, and stable error shape. Swagger UI is useful for exploration; tests remain the contract verification.

## UI / status surfaces
Django admin/browsable API is the initial human-facing surface. A separate frontend is out of scope. Add a health endpoint for local container/orchestration checks.

## Security boundaries to think about
- Validate all request data through serializers; enforce object-level permissions.
- CSRF and session auth semantics; do not assume CORS is authorization.
- Keep `SECRET_KEY`, DB passwords, and OAuth secrets out of source control and logs.
- Set secure cookie and host settings deliberately when moving beyond localhost.

## Profiling plan
Profile only after the API has a repeatable request workload. Examine query count and N+1 behavior with Django query logging; use a Python profiler for CPU/allocations if needed. Compare before/after query optimization with same fixtures.

## How this project fits into the curriculum
This is the main Python web project. It becomes a protected resource for Keycloak and can later provide a realistic endpoint for Redis caching and telemetry instrumentation.

## Suggested milestone walkthrough
1. **Resource model and API.** Build one resource with serializer and viewset; test CRUD.
2. **PostgreSQL.** Add migrations and run integration tests against a real local Postgres.
3. **Authentication/permissions.** Add one auth method, then test role/object authorization.
4. **API docs.** Generate schema, review it, and exercise examples through Swagger/curl.
5. **Container + CI.** Build image; pipeline runs uv sync, lint/type checks, tests, and image build on local push.
6. **Profile (optional).** Investigate query count and latency using a fixed dataset and workload.

## Reference notes and resources
- Django and Django REST Framework official tutorials/docs.
- drf-spectacular documentation.
- `uv-setup.md` for shared project/environment commands.
- PostgreSQL docs and `postgres-lab` notes.
