export PATH := $(HOME)/.local/bin:$(PATH)

.PHONY: lint format typecheck test all clean install dev

# ---------- Setup ----------
install:
	uv sync

dev:
	uv sync --all-extras
	uv run pre-commit install

# ---------- Quality ----------
lint:
	uv run ruff check .

lint-fix:
	uv run ruff check . --fix

format:
	uv run ruff format .

format-check:
	uv run ruff format . --check

typecheck:
	uv run mypy src/

# ---------- Testing ----------
test:
	uv run pytest

test-unit:
	uv run pytest -m unit

test-integration:
	uv run pytest -m integration

test-fast:
	uv run pytest --no-cov -q

# ---------- Combined ----------
all: lint format-check typecheck test

check: lint format-check typecheck

# ---------- Run ----------
serve:
	uv run uvicorn onboarding_agent.api.app:app --reload --port 8000

cli:
	uv run onboarding-agent

# ---------- Clean ----------
clean:
	rm -rf .venv .mypy_cache .pytest_cache .ruff_cache .coverage htmlcov dist build *.egg-info __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
