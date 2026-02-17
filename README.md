# paperweight

[![PyPI](https://img.shields.io/pypi/v/academic-paperweight)](https://pypi.org/project/academic-paperweight/)
[![GitHub License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

paperweight is an arXiv triage CLI.
It fetches recent papers, filters them against your research interests, and produces
a ranked digest — optionally with LLM-powered summarization — that you can read in minutes.

## Why this exists

Checking arXiv directly is great for discovery. paperweight is for a different job:

- keep your daily list short
- rank by your interests
- make output scriptable (`stdout`, `json`, `atom`)
- run the same way every day

## How it works

```
arXiv API → metadata fetch → AI triage → keyword scoring → (optional) LLM summary → deliver
```

1. **Fetch** — pull recent papers from configured arXiv categories.
2. **Triage** — an LLM shortlists papers by title and abstract (or pass all through with heuristic fallback when no key is set).
3. **Score** — keyword matching against titles and abstracts produces a relevance score.
4. **Summarize** — in `abstract` mode (default) the abstract is passed through as-is; in `summary` mode an LLM generates a concise summary from the full paper.
5. **Deliver** — output as plain text, JSON, Atom feed, or email.

## Install

```bash
pip install academic-paperweight
```

From source (requires [uv](https://docs.astral.sh/uv/)):

```bash
git clone https://github.com/seanbrar/paperweight.git
cd paperweight
uv sync --all-extras
source .venv/bin/activate
```

## Quick start (works without API keys)

```bash
paperweight init           # create config.yaml with safe defaults
paperweight doctor         # check your setup for issues
paperweight run --force-refresh  # fetch papers and produce a digest
```

Notes:

- Default analyzer mode is `abstract` (no API key required).
- Triage runs with heuristic fallback if no LLM key is present.

## Example output

Running `paperweight` with the default config prints a plain-text digest to stdout:

```
paperweight digest

1. CoPE-VideoLM: Codec Primitives For Efficient Video Language Models
   Authors: Sayan Deb Sarkar, Rémi Pautrat, Ondrej Miksik +4 more
   Date: 2026-02-13
   Score: 6.24
   Matched: language model, reasoning, transformer
   Link: http://arxiv.org/abs/2602.13191v1
   Summary: Video Language Models (VideoLMs) empower AI systems to understand
   temporal dynamics in videos. To fit to the maximum context window constraint,
   current methods use keyframe sampling which can miss both macro-level events
   and micro-level details ...

2. In-Context Autonomous Network Incident Response: ...
   Authors: Yiran Gao, Kim Hammar, Tao Li
   Date: 2026-02-13
   Score: 6.24
   Matched: language model, reasoning
   Link: http://arxiv.org/abs/2602.13156v1
   Summary: Rapidly evolving cyberattacks demand incident response systems ...
```

Pipe to JSON for scripting, or deliver as an Atom feed or email — see [CLI](#cli) below.

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
paperweight run --delivery json --output ./paperweight.json

# Atom feed output
paperweight run --delivery atom --output ./paperweight.xml

# optional email delivery (requires notifier.email config)
paperweight run --delivery email

# cap processing to 20 papers (output may be fewer after filtering)
paperweight run --max-items 20

# strict checks for CI/release gates
paperweight doctor --strict

# activate a named profile
paperweight run --profile fast
```

Full command reference: [docs/CLI.md](docs/CLI.md)

## Configuration

`paperweight init` generates a `config.yaml` with all required sections. Core sections:

| Section | Purpose |
|---|---|
| `arxiv` | arXiv categories to watch and max results per fetch |
| `triage` | LLM-powered shortlisting on title + abstract (opt-in, requires API key) |
| `processor` | Keyword lists and scoring weights for relevance ranking |
| `analyzer` | `abstract` (default, no key) or `summary` (LLM-generated) |
| `concurrency` | Thread/worker limits for fetching, triage, and summarization |
| `feed` | Metadata for `--delivery atom` output |
| `metadata_cache` | Avoids repeated arXiv API calls within a TTL window |
| `profiles` | Named config overlays activated with `--profile NAME` |
| `logging` | Log level and optional log file path |
| `notifier` | SMTP settings for `--delivery email` |
| `db` | Optional Postgres persistence for runs and results |
| `storage` | Base directory for artifact storage |

Full reference: [docs/CONFIGURATION.md](docs/CONFIGURATION.md)

### Secrets and environment variables

API keys and passwords can be supplied via:

- a `.env` file in the project root (`OPENAI_API_KEY`, `GEMINI_API_KEY`, etc.)
- `${VAR}` interpolation in `config.yaml` (e.g., `password: ${EMAIL_PASSWORD}`)
- `PAPERWEIGHT_` prefixed env vars to override any config value

See [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md) for details.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for quantified release goals and forward plan.

## Development

```bash
make lint        # ruff check
make typecheck   # mypy
make test        # pytest with coverage
make format      # auto-format with ruff
make all         # lint + typecheck + test
```

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for the full contributing guide.

## License

[MIT](LICENSE)
