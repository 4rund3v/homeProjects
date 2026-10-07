# PostgreSQL Lab

**Goal:** Understand PostgreSQL behavior through design, instrumentation, and operation on a small dataset.

**Scope:** Schema design, data types, constraints, indexes, transactions, isolation levels, query plans, connection pooling, migrations, backup/restore, and basic operational observability.

**Out of scope:** High availability, sharding, large-scale replication, and OLAP. Those follow once this project's behavior is reliable.

**Learning focus:** Explain why a query is fast or slow, when consistency assumptions are worth the cost, and what operational choices have observability or recovery implications.

**Depends on:** `go-fundamentals`, `python-refresh`, `go-http-server`, `drf-basics` (if an API surface is included).

## Milestones
- [ ] Define a schema with constraints and indexes; document assumptions.
- [ ] Run representative queries, observe plans, and tune indexes deliberately.
- [ ] Demonstrate transaction and isolation behavior with documented tests; include rollback and failure cases.
- [ ] Add migration workflow, backup/restore procedure, and connection-pool configuration.
- [ ] If an API surface is included, expose an HTTP API, document endpoints, add a status page, and profile a documented workload.

## Tools
- PostgreSQL container, `psql`, Python and/or Go drivers, `EXPLAIN (ANALYZE, BUFFERS, VERBOSE)`, migration tooling, optional pprof-based profiling for workload characterization.
