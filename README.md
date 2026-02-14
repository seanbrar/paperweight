# paperweight

[![PyPI](https://img.shields.io/pypi/v/academic-paperweight)](https://pypi.org/project/academic-paperweight/)
[![GitHub License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

paperweight is an arXiv triage CLI.
It fetches recent papers, ranks them against your interests, and generates a digest.

## Why use it

The goal is simple: stop reading papers you do not care about.

paperweight gives you:

- fast shortlist generation from selected arXiv categories
- AI triage on title+abstract before expensive content processing
- optional AI summaries (OpenAI/Gemini via Pollux)
- deterministic output you can script around

## v0.2 direction

- Primary delivery: `stdout` digest
- Secondary delivery: Atom feed file
- Optional delivery: email

See `/Users/sean/GitHub/paperweight/docs/ROADMAP.md` for the full plan.

## Install

```bash
pip install academic-paperweight
```

Or from source:

```bash
git clone https://github.com/seanbrar/paperweight.git
cd paperweight
uv sync --all-extras
source .venv/bin/activate
```

## Quick start

1. Copy `/Users/sean/GitHub/paperweight/config-base.yaml` to `config.yaml`.
2. Set your LLM API key (required when `analyzer.type: summary`):
   ```bash
   export OPENAI_API_KEY=...
   # or
   export GEMINI_API_KEY=...
   ```
3. Run:
   ```bash
   paperweight
   ```

This prints the digest to `stdout` by default.

## CLI

```bash
paperweight [run-options]
paperweight run [run-options]
paperweight init [--config PATH] [--force]
paperweight doctor [--config PATH]
```

Examples:

```bash
# default stdout digest
paperweight

# write Atom feed
paperweight --delivery atom --output ./paperweight.xml

# optional email delivery (requires notifier.email config)
paperweight --delivery email

# bootstrap a config file
paperweight init

# validate local setup
paperweight doctor
```

## Configuration

Main sections:

- `arxiv`: categories and max results
- `triage`: AI shortlist settings (title + abstract gate)
- `processor`: keyword-based scoring settings
- `analyzer`: `abstract` or `summary`
- `logging`: log level/file
- `notifier`: optional; required only for email delivery

Full details: `/Users/sean/GitHub/paperweight/docs/CONFIGURATION.md`

## Development

```bash
make test
make lint
```

## License

MIT. See `/Users/sean/GitHub/paperweight/LICENSE`.
