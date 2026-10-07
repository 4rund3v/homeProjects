# PostgreSQL Lab

## What this project exists to solve
Learn PostgreSQL as an application dependency: model data safely, understand transactions and plans, and practice backups, migrations, and connection management with local workloads.

## Success criteria / completion metrics
- Schema with constraints and migration history that can create a fresh database.
- Reproducible tests showing transaction rollback and selected isolation behavior.
- Query plans captured before/after a deliberate index or query change, with measured execution evidence.
- Backup and restore walkthrough verified against a disposable local database.
- Optional API exercise has documented contract and health page; local image and CI pipeline are added when it becomes an application.

## Prerequisites and dependencies
- Basic SQL familiarity; `go-fundamentals` and/or `python-refresh` for clients.
- Docker for local PostgreSQL.

## Tools, libraries, and runtime
- PostgreSQL container and `psql`.
- Migration tool selected during implementation (e.g. golang-migrate or Django migrations).
- Go `database/sql` and a driver; Python `psycopg` / Django ORM for comparison.
- `EXPLAIN (ANALYZE, BUFFERS)` and `pg_stat_statements` when enabled.

## Learning objectives (skills practiced)
- Relational modeling, constraints, indexes, normalization and denormalization tradeoffs.
- ACID properties and transaction boundaries.
- MVCC, isolation levels, locks, deadlocks, and retries.
- Query planning, index selection, connection pools.
- Migration safety and backup/restore.

## Architecture / design note
Keep database experiments in versioned migrations and seed fixtures. Run Postgres locally in Docker with a named volume only when persistence is intentional; otherwise use disposable data. Separate application-level tests from direct SQL exploration so query behavior is easy to isolate.

## Test strategy
- Migration test: empty database → latest schema.
- Integration tests against real PostgreSQL for SQL semantics; SQLite is not a substitute for Postgres isolation/planner behavior.
- Transaction and constraint tests with cleanup and deterministic fixtures.
- Restore test on a fresh disposable database.

## Documentation checklist
- Schema diagram and table/constraint explanation.
- Commands for startup, migration, reset, backup, restore.
- Query-plan notes with data volume and environment details.
- Record assumptions and operational limitations.

## API contract
No API is required. If an HTTP API is added, define OpenAPI, errors, pagination, and health/readiness semantics; do not turn the DB lab into a framework exercise by default.

## UI / status surfaces
No UI required. A local database status page is only appropriate if introduced as an API exercise.

## Security boundaries to think about
- Use parameterized queries; never interpolate untrusted SQL.
- Keep credentials outside source control; understand that Terraform state and logs can contain secrets.
- Apply least-privilege database roles; distinguish migration owner from runtime role.
- Avoid exposing Postgres on all host interfaces by default.

## Profiling plan
Use query plans and `pg_stat_statements` to reason about database workload. Define dataset size, query mix, and cache conditions; do not present `EXPLAIN ANALYZE` timings as universal. Compare one change at a time.

## How this project fits into the curriculum
Prepares for PostgreSQL-backed DRF and telemetry. Its migration, test, and query analysis patterns inform later Helm deployments and operational recovery exercises.

## Suggested milestone walkthrough
1. **Schema.** Model a small domain; add constraints and explain each.
2. **Transactions.** Demonstrate rollback, isolation, and one conflict scenario.
3. **Query plans.** Add realistic fixture volume, inspect a slow query, form an index hypothesis, compare plans.
4. **Operations.** Add repeatable migration and backup/restore steps; verify restore.
5. **Client/API (optional).** Connect from Go or Python and document the API if one is created.

## Reference notes and resources
- PostgreSQL official documentation: SQL, indexes, transactions, `EXPLAIN`.
- Use a local Docker image pinned to a major version.
- `psql` command reference and migration-tool documentation.
