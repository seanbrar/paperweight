.PHONY: install test lint typecheck format clean build all

# Development setup
install:
	uv sync --all-extras

# Run tests
test:
	uv run pytest

# Run tests with coverage
test-cov:
	uv run pytest --cov=paperweight --cov-report=term-missing

# Lint code
lint:
	uv run ruff check src tests

# Type check
typecheck:
	uv run mypy src/paperweight

# Format code
format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

# Clean build artifacts
clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Build distribution
build: clean
	uv build

# Run all checks (lint, typecheck, test)
all: lint typecheck test
