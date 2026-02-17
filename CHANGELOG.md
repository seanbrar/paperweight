# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.1] - 2026-02-16

### Changed
- arXiv categories are now batched into a single OR query (`cat:cs.AI OR cat:cs.CL`), reducing N parallel API calls to 1
- `page_size` now matches `min(max_results, 100)` instead of always requesting 100 results
- `ThreadPoolExecutor` removed from `fetch_recent_papers()` since only one API call is made
- `--force-refresh` now fetches today's papers (1-day window) instead of a full 7-day backfill; the 7-day bootstrap is reserved for first runs only
- Quick Start no longer recommends `--force-refresh` for the initial run since `paperweight run` already backfills automatically

### Added
- RSS feed fetcher (`fetch_rss_papers`) for daily lookups — no rate limits, sub-second metadata fetch
- RSS-first routing in `fetch_recent_papers`: daily runs try RSS before falling back to the arXiv API
- Exponential backoff (via `tenacity`) on `arxiv.HTTPError` with waits of 5 → 15 → 45 → 90 s
- `ArxivRateLimitError` exception with user-friendly message for HTTP 429 responses

## [0.3.0] - 2026-02-15

### Added
- Profile switching via `--profile NAME` flag and `PAPERWEIGHT_PROFILE` env var
- Metadata cache (`metadata_cache` config section) to skip repeated arXiv API calls within a TTL window
- Progress logging during triage and summary LLM calls
- Per-call LLM timeout (45 s) for triage and summary to prevent hanging runs
- `--version` flag on the CLI
- Public API surface: `paperweight.__version__`, `load_config`, `get_recent_papers`, `score_papers`, etc. re-exported from `__init__.py`

### Changed
- Triage now uses per-paper async calls (same pattern as summaries) instead of batch `run_many`
- Triage rationale is compact: prompt asks for max 20 words, output is whitespace-normalized and truncated
- `paperweight init` prints a clean error to stderr (no traceback) when config already exists; use `--force` to overwrite

## [0.2.0] - 2026-02-14

### Added
- Database support with PostgreSQL integration for paper storage
- Local arXiv mirror for offline integration testing
- Comprehensive test suite with integration and unit tests
- Deterministic text digest rendering for stdout/file workflows
- Atom feed rendering for secondary delivery workflows
- AI-first title/abstract triage stage with rationale/score annotations
- Content hydration helper to fetch full text only for shortlisted papers
- Minimalist CLI subcommands: `run`, `init`, and `doctor`
- Dedicated CLI ergonomics reference (`docs/CLI.md`)
- Small CLI workflow integration tests (`run` stdout/atom + `doctor`)
- JSON delivery mode for script-friendly output
- Output capping via `--max-items`
- Strict doctor mode (`doctor --strict`) for release/CI gating
- Trusted publishing workflow for release tags (`.github/workflows/release.yml`)

### Changed
- Migrated project to uv for dependency management
- Refactored scraper to use the official `arxiv` Python library
- Restructured test suite with separate integration and unit test directories
- Updated core logic and notifier components
- CLI delivery modes now support `stdout` (default), `atom`, and optional `email`
- Configuration validation now treats notifier/email as optional unless email delivery is used
- Roadmap and docs rewritten around a simplified v0.2 direction
- Main pipeline now runs metadata triage before expensive content extraction
- `paperweight` now defaults to `run` for backward-compatible invocation
- README/CLI/FAQ docs audited and aligned to current behavior
- Roadmap rewritten with quantifiable usefulness and release metrics

### Fixed
- Improved error handling throughout the codebase

## [0.1.2] - 2025-03-23

### Added
- GitHub Actions CI pipeline for automated testing
- Comprehensive docstrings across the codebase
- Expanded README with detailed background and architecture documentation
- Detailed roadmap documentation

### Changed
- Improved test resilience across different environments
- Updated pre-commit hook handling

### Fixed
- pytest configuration for proper import resolution
- Config tests to be more environment agnostic

## [0.1.1] - 2024-09-12

### Changed
- Increased minimum Python version to 3.10

## [0.1.0] - 2024-XX-XX

### Added
- Initial release
- arXiv paper fetching and filtering
- Keyword-based relevance scoring
- LLM-powered summarization (OpenAI and Gemini)
- Email notification system
- YAML-based configuration

[Unreleased]: https://github.com/seanbrar/paperweight/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/seanbrar/paperweight/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/seanbrar/paperweight/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/seanbrar/paperweight/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/seanbrar/paperweight/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/seanbrar/paperweight/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/seanbrar/paperweight/releases/tag/v0.1.0
