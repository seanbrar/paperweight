# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/seanbrar/paperweight/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/seanbrar/paperweight/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/seanbrar/paperweight/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/seanbrar/paperweight/releases/tag/v0.1.0
