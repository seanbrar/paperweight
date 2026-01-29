# Testing Structure

This document describes how tests are organized in paperweight.

For guidance on *what* to test, see [Testing Philosophy](testing-philosophy.md).

---

## Boundary-First Flat Structure

Tests are organized by **boundary**, not by source module or test type.

### Tenets

1. **One file per boundary.** A boundary is where user input enters, output leaves, or external systems integrate. Each boundary gets one test file—not one per source file, not one per test category.

2. **Flat over nested.** No directory hierarchy mirroring source structure. If you need to find tests for a module, search by boundary responsibility, not by path.

3. **Markers over directories.** Test *type* (integration, api) is expressed via pytest markers, not directory placement. Run `pytest -m "integration"` to select integration tests, regardless of which file they're in.

4. **Interior modules don't need dedicated tests.** Internal logic is tested through its boundary. A scoring bug surfaces in processor tests; a date parsing bug surfaces in scraper tests.

### Boundaries in Paperweight

| Boundary | Responsibility |
|----------|----------------|
| **Configuration** | User YAML + environment → validated config dict |
| **Pipeline** | Config → fetched, scored, summarized, notified papers |
| **Contracts** | Cross-cutting architectural invariants |
| **arXiv** | Network requests → paper metadata and content |
| **LLM** | Paper content → summaries (with fallback) |
| **SMTP** | Papers → email notifications |
| **Database** | Papers → persistent storage |
| **Local Mirror** | Offline testing environment for pipeline |

New boundaries are rare. If you're creating a new test file, ask: *is this a new boundary, or does it belong to an existing one?*

---

## Where Does My Test Go?

```
Is this an architectural invariant that spans modules?
  → test_contracts.py

Does this test the complete pipeline flow?
  → test_pipeline.py

Does this test config loading, validation, or env var handling?
  → test_config.py

Does this test fetching from arXiv or extracting content?
  → test_scraper.py

Does this test LLM summarization or fallback behavior?
  → test_analyzer.py

Does this test paper scoring or normalization?
  → test_processor.py

Does this test email composition or delivery?
  → test_notifier.py

Does this require a real external service (database, etc.)?
  → tests/api/ (gate behind environment variable)

Does this use the local mirror for offline testing?
  → test_local_mirror.py

None of the above?
  → Probably belongs in an existing boundary file.
     If genuinely new, justify the new boundary.
```

---

## Relationship to Testing Philosophy

The [Testing Philosophy](testing-philosophy.md) document answers: *Should I write this test?*

This document answers: *Where does it go?*

Testing Philosophy provides the principles. This document applies those principles to paperweight's specific boundaries.
