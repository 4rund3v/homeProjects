# Avro Schema Guide — Design, Evolve, Govern

> Avro `.avsc` schemas are the contract between your Kafka producer and consumer.
> This guide teaches you to **design, version, evolve, validate, and govern** them.
> No schema files — the method and the decisions.

---

## 1. Why Avro (and not JSON on the wire)

You *could* put JSON in Kafka. Avro buys you:

- **A enforced schema** — the producer can't emit a malformed event; it's validated
  against the schema at serialization time.
- **Compact binary encoding** — smaller payloads, faster over the wire.
- **Schema evolution rules** — a defined compatibility contract so producers and
  consumers can version independently.
- **A schema registry** — the single place schemas live, versioned, with
  compatibility checks enforced on registration.

For a financial event stream, "the producer cannot emit an event the consumer can't
read" is worth the setup cost. That's the whole reason Avro is here.

---

## 2. The pieces

- **Schema (`.avsc`)** — a JSON document describing a record: its name, namespace,
  fields, and types.
- **Schema Registry** — stores schemas under a **subject**, versions them, and
  enforces **compatibility** when a new version is registered.
- **Subject naming strategy** — usually `TopicNameStrategy`: subject = topic name,
  so a topic's value schema versions under `<topic>-value`.
- **Serializer/Deserializer** — producer serializes against a registered schema
  (embedding a schema id in the payload); consumer looks the id up in the registry.

**The rule this enforces:** you never hand-write bytes. Both sides go through the
registry, so the contract is checked, not hoped for.

---

## 3. Designing an Avro record

Follow the same discipline as [`domain-decomposition.md`](domain-decomposition.md),
but for messages.

**Every field decision:**
- **Type precisely.** Use Avro logical types for money and time: `bytes`/`string`
  with `logicalType: decimal` for money (never float), `long` with
  `logicalType: timestamp-millis` for time. This mirrors the Postgres rules in
  [`postgres-guide.md`](postgres-guide.md) §2 — same discipline, wire and storage.
- **Give every field a default** if it's optional. Fields without defaults are
  required; adding a required field is a breaking change (see §5).
- **Names matter and are part of the contract.** Renaming a field is breaking unless
  you use aliases. Treat field names as public API.
- **Include an event identity.** An `event_id` (uuid/string) is your idempotency key
  ([`kafka-guide.md`](kafka-guide.md) §3) and your dedup handle. Don't omit it.
- **Include envelope metadata** you'll want for observability and debugging:
  `event_id`, `event_type`, `occurred_at`, `produced_at`, maybe `schema_version`,
  and a correlation/trace id. Decide deliberately what's in the envelope vs the
  payload.
- **Model the payload as a domain event, not a DB row.** The event says "an expense
  was recorded with these facts" — it is not a serialized ORM object. Don't leak
  internal columns into the event.

**Design questions to answer per event (record in [`design.md`](design.md)):**
- What *happened* (past tense — events are facts, not commands)?
- What's the **key** and what ordering does it protect? (`loan_id`, per
  [`kafka-guide.md`](kafka-guide.md) §2.)
- What's the minimal payload the consumer needs to act — and no more?
- What's the idempotency key?
- Is this event a *fact* (immutable, "ExpenseRecorded") or an *intent* ("please
  update balance")? Prefer facts; the consumer decides what to do.

---

## 4. The events you'll need (concepts, not files)

Reason about these as *roles*, then name them yourself:

- **Expense recorded** — emitted when an expense is saved (via the outbox). Carries
  the expense facts + the key (`loan_id` when credit-paid). Consumed to update loan
  balance.
- **Loan balance updated** — emitted *after* the consumer applies the change. Useful
  as an audit trail and for downstream projections. (Is it needed? Decide — it's a
  legitimate design question, not a requirement.)
- Possibly a **reconciliation/repair** event if you build the rebuild-from-stream
  path ([`data-lifecycle.md`](data-lifecycle.md)).

Each is its own subject/version. Don't overload one topic with unrelated event types.

---

## 5. Compatibility — the rules that let you evolve

This is the heart of Avro governance. The registry enforces a **compatibility mode**
per subject. Know these rules:

**BACKWARD compatible** (new schema can read old data) — allows:
- **Adding a field with a default.** (Old data lacks it; new readers use the default.)
- **Deleting a field** (only if it had a default — old readers of new data need it).

**FORWARD compatible** (old schema can read new data) — allows:
- **Deleting a field.**
- **Adding a field** (old readers ignore fields they don't know — only safe if they
  truly ignore unknowns).

**FULL** = backward + forward. This is the usual production choice.

**Breaking changes (avoid, or version the topic):**
- **Renaming a field** without an alias.
- **Changing a field's type** incompatibly (e.g. `int` → `string`, `float` → decimal
  without care).
- **Adding a field without a default** (breaks backward).
- **Removing a field that had no default.**
- **Changing the key** type or meaning.

**The workflow:** you register v2 of a schema; the registry checks it against v1 under
the configured mode; if incompatible, registration is **rejected**. This is your
safety net — it's why you use a registry rather than loose `.avsc` files.

**The evolutionary recipe (memorize):**
1. Need a new field? **Add it with a default.** Ship it. Non-breaking.
2. Need to change a type or meaning? **Add a new field** (new name), backfill, switch
   consumers, then deprecate the old one. Never mutate in place.
3. Need to restructure badly? **New topic version** (`...v2`) and run both during
   migration.

---

## 6. Where schemas live and how they're governed

Decide and document (in [`design.md`](design.md)):

- **Source of truth:** the `.avsc` files live in the repo, versioned with the code
  that produces/consumes them. The registry is the *runtime* authority; the repo is
  the *source* authority. CI registers schemas and checks compatibility.
- **One file per event type**, named to match the subject/topic.
- **Compatibility mode** set per subject (recommend FULL for event streams).
- **Registration is a CI gate:** a schema change that fails compatibility fails the
  build — same spirit as the OpenAPI breaking-change check in
  [`api-contracts-guide.md`](api-contracts-guide.md) §6.

**Ownership rule:** the producer team owns the schema, but **consumers must be able
to read N-1 versions** (the previous version) during a rollout. Design for a
deploy window where old and new consumers coexist — which is exactly why FULL
compatibility matters.

---

## 7. Validation workflow

1. Author the `.avsc` (in the repo).
2. Validate syntax and logical types locally before committing.
3. Register against the local/dev registry; confirm compatibility mode accepts it.
4. **Test round-trip:** produce a real message, consume it, assert the consumer reads
   every field correctly. A schema that validates but deserializes wrong is a bug.
5. **Test the evolution path:** register the next version, confirm old consumers still
   read new messages and new consumers still read old messages. This is the test most
   people skip — don't.
6. Gate all of the above in CI.

---

## 8. Exercises (Phase 6)

1. **Design one event** (expense recorded): choose fields, types, logical types,
   defaults, key, and idempotency key. Defend each choice in one sentence.
2. **Round-trip it:** register, produce, consume, assert. *Lesson: the registry
   contract.*
3. **Add a field with a default** → confirm compatibility passes and old consumers
   cope. *Lesson: backward-compatible evolution.*
4. **Try a breaking change** (rename a field) → watch the registry reject it. *Lesson:
   the safety net.*
5. **Do the type-change dance:** add a new field, migrate, deprecate the old — without
   downtime. *Lesson: the non-breaking refactor.*

Checkpoints in [`checkpoints.md`](checkpoints.md).

---

## 9. Best-practices checklist

- [ ] Money uses Avro decimal logical type; time uses timestamp logical type.
- [ ] Every event has an `event_id` (idempotency key) and a clear key field.
- [ ] Events are facts (past tense), not commands or serialized ORM rows.
- [ ] Every optional field has a default; required fields are deliberate.
- [ ] Field names are treated as public API; renames use aliases or new fields.
- [ ] Compatibility mode is set (recommend FULL) and enforced by the registry.
- [ ] Schema registration + compatibility check runs in CI.
- [ ] Round-trip and evolution tests exist and pass.
- [ ] Consumers can read N-1 schema versions during rollout.
- [ ] Breaking changes go to a new topic version, not an in-place mutation.

---

## 10. Decisions to record in `design.md`

- Registry choice and where it runs (local, k3s, or managed).
- Subject naming strategy (TopicNameStrategy) and topic/version naming.
- Compatibility mode per subject (FULL recommended).
- The event envelope: which metadata fields are standard on every event.
- The idempotency key (`event_id`) and where uniqueness is enforced.
- Where `.avsc` files live in the repo and how CI registers/validates them.
- The N-1 consumer-read policy during rollouts.
