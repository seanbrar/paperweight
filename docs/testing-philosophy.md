# Testing Philosophy

This document describes the principles that guide testing decisions in paperweight.

For guidance on how tests are organized, see [Testing Structure](testing-structure.md).

---

## Overview

Paperweight's test suite prioritizes signal over coverage. Tests should catch real problems, not merely execute code paths. This philosophy results in fewer tests—each earning its place by providing meaningful protection.

---

## Core Principles

### Signal over coverage

A test that fails should indicate a real problem. A test that passes should inspire confidence. Tests that do neither are overhead.

Coverage is a proxy metric. Paperweight targets meaningful coverage of critical paths rather than high percentages of executed code.

### Trust the architecture

Paperweight's configuration validation, type hints, and module structure prevent many error classes at design time. We don't write tests for:

- Python language guarantees (immutability, iteration behavior)
- Standard library behavior (dict.get(), os.path operations)
- Configuration validation that's already enforced at load time

### Test at boundaries

The most valuable tests are at the edges where paperweight interacts with external systems:

| Boundary | What it tests |
|----------|---------------|
| **Configuration** | YAML loading, env var expansion, validation |
| **arXiv API** | Paper fetching, date filtering, content extraction |
| **LLM Providers** | Summarization, fallback to abstracts |
| **SMTP** | Email notification delivery |
| **PostgreSQL** | Paper storage, run tracking |

Interior logic (scoring algorithms, text processing) is tested through integration when possible.

### Regression-driven growth

The best tests are written in response to bugs that actually happened. Speculative tests may or may not catch real problems. Tests born from real failures are insurance policies with proven value.

---

## What to Test

| Category | Example |
|----------|---------|
| **Boundary integration** | arXiv client behavior, SMTP delivery, database operations |
| **Error handling** | YAML parse errors, network failures, missing API keys |
| **Configuration edge cases** | Invalid categories, missing sections, env var expansion |
| **Algorithmic correctness** | Score calculation, normalization |

## What Not to Test

| Category | Reason |
|----------|--------|
| **Mock-only unit tests** | Testing mocks provides no signal about real behavior |
| **Python guarantees** | dict.get() defaults, list iteration |
| **Interior sorting logic** | Covered by integration tests |
| **Database SQL construction** | Tested through real database integration |

---

## Test Categories in Paperweight

### Integration tests (`test_pipeline.py`, `test_local_mirror.py`)

Test the complete pipeline flow. These are the backbone of the test suite.

### Boundary tests (`test_config.py`, `test_scraper.py`, `test_notifier.py`)

Test where paperweight meets external systems.

### Contract tests (`test_contracts.py`)

Verify architectural invariants: module imports, exception hierarchies.

### API tests (`tests/api/`)

Tests against real external services, gated behind environment variables.

---

## On Coverage

Current coverage is intentionally moderate (~60-70%). Gaps exist where:

1. Code is tested transitively through integration
2. Error paths are defensive and unlikely
3. Database operations are covered by optional API tests

When adding `# pragma: no cover`, always include a reason:

```python
except Exception:  # pragma: no cover - defensive fallback
    logger.error("Unexpected error")
```

---

## Adding New Tests

Before writing a test, ask:

1. **Is this a boundary?** If yes, test it.
2. **Has this failed before?** If yes, add a regression test.
3. **Is this complex algorithm?** If yes, test edge cases.
4. **Is this interior logic tested elsewhere?** If yes, maybe skip.

When in doubt, test. But be intentional—every test should be justifiable.
