# Shared Python setup with uv

All Python projects in this workspace use `uv` as the default project and environment manager.

## Standard workflow

From a Python project directory:

```bash
uv init --python 3.12
uv add <runtime-dependency>
uv add --dev pytest ruff mypy
uv sync
uv run pytest
uv run ruff check .
uv run mypy .
```

Use the project's existing `pyproject.toml` if it already exists; do not run `uv init` over an initialized project. Commit `pyproject.toml` and `uv.lock`. Do not commit `.venv/`, caches, generated profiles, credentials, or local databases.

For Django/DRF projects, runtime dependencies will normally include Django, Django REST Framework, a PostgreSQL driver, and an OpenAPI package. Add only what the current milestone requires:

```bash
uv add django djangorestframework psycopg[binary] drf-spectacular
uv add --dev pytest pytest-django ruff mypy
uv run python manage.py migrate
uv run pytest
```

The exact dependency set belongs in each project's `pyproject.toml`; this guide is the shared workflow, not a universal package list.

## Why uv is part of the curriculum

- `pyproject.toml` declares project metadata and dependencies.
- `uv.lock` records a reproducible resolution and belongs in version control.
- `uv run` ensures commands use the project environment instead of an accidental global interpreter.
- `uv sync` makes a clean environment reproducible.
- Separate runtime and development dependencies expose what production actually needs.

## Rules

1. Use `uv run ...` in documentation and CI commands.
2. Use `uv add` / `uv remove`; do not hand-edit resolved lock data.
3. Pin the supported Python range in `pyproject.toml` after selecting it deliberately.
4. Run tests and static checks before changing dependencies.
5. Never put secrets in `pyproject.toml`, `.env` files, notebooks, or lock files.
6. When a dependency is introduced, record why it is needed in the project README or a decision note.

## Python project completion checks

At minimum, each Python project should provide reproducible commands for:

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy .
```

Not every small exercise needs strict mypy or every tool on day one. The project milestone should state which checks are active and why.
