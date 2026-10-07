# Python Refresh

## What this project exists to solve
Refresh modern Python idioms and OOP design judgment. The goal is not to build a product — it is to unlearn bad habits and practice design choices explicitly so later projects (DRF, telemetry, tests) feel intentional.

## Success criteria / completion metrics
- A small set of standalone Python modules (not a single script) demonstrating modern patterns.
- Every module has tests with at least one happy path, one failure path, and one property-based test.
- `uv run mypy --strict` passes for all modules with no `# type: ignore` exceptions.
- A reflection document answering: when would you choose an ABC vs. a Protocol, and why does that distinction matter in a large codebase?

## Prerequisites and dependencies
- Python 3.11+ (selected deliberately; document the choice).
- `uv` installed (see [`../uv-setup.md`](../uv-setup.md)).

## Tools, libraries, and runtime
- `uv` for project, venv, and dependency management.
- Runtime (examples): `pydantic` for settings, `tenacity` or a hand-rolled `@retry` for decorator practice.
- Dev: `pytest`, `pytest-cov`, `mypy --strict`, `ruff`, `hypothesis`.
- No web framework here — that's `drf-basics`.

## Learning objectives (skills practiced)
- Decorators: with/without arguments, class decorators, stateful decorators, and the surprising edge cases (functools.wraps, attribute shadowing, mutable default args).
- Context managers: `__enter__`/`__exit__`, `@contextmanager`, `@contextlib.asynccontextmanager` (read-only understanding if not writing async yet).
- ABCs and protocols: when inheritance helps, when structural subtyping is sufficient, and why `typing.Protocol` exists.
- Dataclasses and Pydantic settings: field defaults, validators, `__post_init__`, immutability.
- Generators: `yield`, generator expressions, `itertools`, laziness vs. eager evaluation.
- Type hints: mypy strict mode, generics, overloads, TypedDict, NewType.
- pytest: fixtures, `tmp_path`, `monkeypatch`, parametrize, markers.
- Hypothesis: stateful testing, shrinking, invariants.

## Architecture / design note
Organize as a single package with multiple modules, not one file:

```
src/
  decorators.py
  context_managers.py
  config.py
  retry.py
tests/
  test_decorators.py
  ...
pyproject.toml
```

Each module has one clear responsibility and is independently importable. Tests mirror the package layout.

## Test strategy
- Pytest with `tests/` directory.
- `pytest-cov` for coverage reporting, but coverage is a signal, not a target — do not chase 100%.
- Hypothesis for invariants that should hold across a range of inputs.
- `mypy --strict` as a non-negotiable gate before committing.

## Documentation checklist
- `README.md` explaining the project's learning purpose and how to run tests.
- Docstrings on public functions with parameter and return types matching annotations.
- A reflection `NOTES.md` on ABC vs. Protocol decisions.

## API contract
No HTTP API. Each module exposes Python functions/classes; the "contract" is the public API of each module.

## UI / status surfaces
CLI only. No web UI.

## Security boundaries to think about
- Decorators that mutate state can hide side effects — test that explicitly.
- `__reduce__` / pickling is a security boundary if any module serializes objects.
- Pydantic settings should validate that secrets are not logged or printed.

## Profiling plan
- Profile a generator-heavy data-processing function with `pyinstrument` to see where laziness wins.
- Profile a decorated function chain with `cProfile`; explain overhead of wrapper calls.

## How this project fits into the curriculum
This is the Python foundation. `sudoku-solver` reuses the testing and typing habits. `drf-basics` reuses decorators, dataclasses, and OOP design. Revisit this project when a later task exposes a gap.

## Suggested milestone walkthrough
1. **Decorators + context managers.** Implement a typed `@retry` decorator (with policy: attempts, backoff, exceptions to catch) and a context-managed connection pool (simulated). Write tests covering happy path, exhaustion, and cancellation.
2. **Settings model.** Build a layered settings model using Pydantic: defaults → YAML file → environment variables → CLI overrides. Each layer wins. Validate invariants (e.g., port is int, timeout > 0).
3. **ABCs vs. Protocols.** Take a small procedural module and refactor into an ABC hierarchy. Then refactor the same module using a Protocol. Compare: which is more testable? Which is more flexible? Document the tradeoff in `NOTES.md`.
4. **Property-based tests.** Use Hypothesis to test a small graph function (e.g., `is_bipartite` or `shortest_path` invariant). Run with `--max-examples=1000` and inspect any counterexamples Hypothesis finds.

## Reference notes and resources
- Pydantic v2 documentation.
- Python's `typing` module documentation ( Protocols, NewType, TypedDict, overload).
- `hypothesis` docs on stateful testing.
- PEP 318 (decorators), PEP 343 (with statement), PEP 3119 (ABCs), PEP 544 (Protocols).
