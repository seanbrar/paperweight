# paperweight

[![PyPI](https://img.shields.io/pypi/v/academic-paperweight)](https://pypi.org/project/academic-paperweight/)
[![GitHub License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

paperweight is an arXiv triage CLI.
It fetches recent papers, filters for relevance, and produces a digest you can read in minutes.

## Why this exists

Checking arXiv directly is great for discovery. paperweight is for a different job:

- keep your daily list short
- rank by your interests
- make output scriptable (`stdout`, `json`, `atom`)
- run the same way every day

## Install

```bash
pip install academic-paperweight
```

From source:

```bash
git clone https://github.com/seanbrar/paperweight.git
cd paperweight
uv sync --all-extras
source .venv/bin/activate
```

## Quick start (works without API keys)

```bash
paperweight init
paperweight doctor
paperweight run --force-refresh
```

Notes:

- `init` writes `config.yaml` with safe defaults.
- default analyzer mode is `abstract` (no summarization API key required).
- triage can run with heuristic fallback if no key is present.

## CLI

```bash
paperweight [run-options]
paperweight run [run-options]
paperweight init [--config PATH] [--force]
paperweight doctor [--config PATH] [--strict]
```

Examples:

```bash
# default plain-text digest to stdout
paperweight

# JSON output for scripts
paperweight run --delivery json --output ./paperweight.json --max-items 20

# Atom feed output
paperweight run --delivery atom --output ./paperweight.xml

# optional email delivery (requires notifier.email config)
paperweight run --delivery email

# strict checks for CI/release gates
paperweight doctor --strict
```

Detailed command behavior: `docs/CLI.md`

## Configuration

Core sections:

- `arxiv`: categories and max results
- `triage`: shortlist gate (title + abstract)
- `processor`: scoring config
- `analyzer`: `abstract` or `summary`
- `logging`
- `notifier` (optional, only for email)

See: `docs/CONFIGURATION.md`

## Roadmap

See `docs/ROADMAP.md` for quantified release goals and forward plan.

## Development

```bash
make lint
make test
```

## License

MIT. See `LICENSE`.
