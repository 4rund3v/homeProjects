.PHONY: help up down migrate lint lint-fix format test test-cov \
        trace serve worker frontend dev clean proto \
        seed-vendors verify check

help:
	@echo "Device Manager — available targets:"
	@echo "  make up          — start Postgres, Kafka, Redis (docker compose)"
	@echo "  make down        — stop containers"
	@echo "  make migrate     — run alembic migrations"
	@echo "  make lint        — ruff check src/ tests/"
	@echo "  make lint-fix    — ruff check --fix src/ tests/"
	@echo "  make format      — ruff format src/ tests/"
	@echo "  make check       — lint + format (fail if dirty)"
	@echo "  make test        — pytest"
	@echo "  make trace       — build Go binary + run once"
	@echo "  make serve       — uvicorn dev server"
	@echo "  make worker      — celery worker (foreground)"
	@echo "  make frontend    — npm run dev in frontend/"
	@echo "  make dev         — up + migrate + serve + worker + frontend"
	@echo "  make proto       — regenerate Go stubs from proto/device.proto"
	@echo "  make seed-vendors — bulk-load OUI CSV into Postgres"
	@echo "  make verify      — check that env + deps + services are in place"
	@echo "  make clean       — down + remove .venv + clean artifacts"

# ── Infrastructure ─────────────────────────────────────────────────────────

up:
	docker compose -f infra/docker-compose.yml up -d
	@echo "Waiting for Postgres…" && \
	  until docker compose -f infra/docker-compose.yml exec -T postgres pg_isready -U device >/dev/null 2>&1; do sleep 1; done
	@echo "Waiting for Kafka…" && \
	  until docker compose -f infra/docker-compose.yml exec -T kafka kafka-broker-api-versions --bootstrap-server localhost:9092 >/dev/null 2>&1; do sleep 2; done
	@echo "Waiting for Redis…" && \
	  until docker compose -f infra/docker-compose.yml exec -T redis redis-cli ping >/dev/null 2>&1; do sleep 1; done
	@echo "Infrastructure ready."

down:
	docker compose -f infra/docker-compose.yml down

migrate:
	uv run alembic upgrade head

seed-vendors:
	uv run python -m scripts.seed_vendors

# ── Python dev loop ────────────────────────────────────────────────────────

lint:
	uv run ruff check src/ tests/

lint-fix:
	uv run ruff check --fix src/ tests/

format:
	uv run ruff format src/ tests/

check: lint-fix
	uv run ruff format --check src/ tests/

test:
	uv run pytest

test-cov:
	uv run pytest --cov=src/device_manager --cov-report=term-missing

serve:
	uv run uvicorn device_manager.infrastructure_web.main:app --reload --host 0.0.0.0 --port 8000

worker:
	uv run celery -A device_manager.application.consumers worker --loglevel=info

# ── Frontend ───────────────────────────────────────────────────────────────

frontend:
	cd frontend && npm run dev

# ── Go binary ──────────────────────────────────────────────────────────────

trace: proto
	cd cmd/nettrace && go build -o ../../bin/nettrace .
	@echo "Built bin/nettrace — run it:"
	@echo "  bin/nettrace trace --subnet 192.168.1.0/24"
	@echo "  bin/nettrace serve --addr :50051"
	bin/nettrace version

proto:
	buf generate

# ── Composite dev workflow ──────────────────────────────────────────────────

# Starts infra, runs migrations, then opens a tmux session with:
#   pane 1: uvicorn (serve)
#   pane 2: celery worker
#   pane 3: npm run dev
# If tmux isn't available, falls back to printing the commands.
dev: up migrate
	@./scripts/dev.sh

# ── Sanity checks ──────────────────────────────────────────────────────────

verify:
	@echo "== uv ===" && uv --version
	@echo "== ruff ===" && uv run ruff --version
	@echo "== Python ===" && uv run python --version
	@echo "== Docker ===" && docker --version
	@echo "== Go ===" && go version
	@echo "== Node ===" && node --version
	@echo "== Containers ===" && docker compose -f infra/docker-compose.yml ps
	@echo "== Env vars ===" && \
	  test -f .env && echo ".env present" || (echo ".env missing — copy .env.example" && exit 1)
	@echo "== Database ===" && \
	  uv run python -c "import asyncpg; print('asyncpg OK')" && \
	  uv run alembic current
	@echo "All checks passed."

# ── Cleanup ────────────────────────────────────────────────────────────────

clean:
	docker compose -f infra/docker-compose.yml down -v
	rm -rf .venv .pytest_cache .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf frontend/node_modules frontend/dist frontend/.vite
	rm -rf bin/
	@echo "Clean."
