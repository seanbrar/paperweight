# CLI reference

paperweight has three commands:

1. `run`: execute the pipeline and deliver output
2. `init`: create a minimal config
3. `doctor`: validate local setup

`paperweight` is shorthand for `paperweight run`.

Global flags:

- `--version` — print version and exit

## run

```bash
paperweight run \
  [--config PATH] \
  [--force-refresh] \
  [--delivery stdout|json|atom|email] \
  [--output PATH] \
  [--sort-order relevance|alphabetical|publication_time] \
  [--max-items N] \
  [--profile NAME] \
  [--quiet]
```

Behavior:

- fetches recent arXiv papers
- runs triage on title + abstract
- hydrates full text only for shortlisted papers
- scores/summarizes and delivers digest
- `--max-items N` caps how many fetched papers enter processing (triage/hydration/summary); output may be fewer than `N` after filtering
- `--profile NAME` activates a named profile from the config's `profiles` section (or set `PAPERWEIGHT_PROFILE` env var)
- `--quiet` suppresses progress status lines on stderr

Delivery modes:

- `stdout`: plain text digest (default)
- `json`: script-friendly array of objects
- `atom`: Atom feed XML
- `email`: SMTP send via `notifier.email` config

`json` fields (always present):

- `title` — paper title
- `arxiv_id` — arXiv identifier
- `authors` — list of author names
- `categories` — list of arXiv categories
- `published` — publication date (ISO format)
- `abstract` — paper abstract
- `link` — arXiv abstract URL
- `pdf_url` — direct PDF URL
- `score` — relevance score (float)
- `keywords_matched` — list of matched keywords

`json` fields (conditional):

- `triage_score` — present when triage is enabled
- `triage_rationale` — present when triage is enabled
- `summary` — present when summary differs from abstract (i.e. LLM summarization was used)

## init

```bash
paperweight init [--config PATH] [--force]
```

Behavior:

- writes a minimal `config.yaml` template
- refuses to overwrite unless `--force` is passed
- prints a clean error message (no traceback) if config already exists

## doctor

```bash
paperweight doctor [--config PATH] [--strict] [--profile NAME]
```

Checks:

- config file exists
- config parses and validates
- triage provider key availability
- enabled delivery adapters

Exit codes:

- `0`: healthy (or warnings present without `--strict`)
- `1`: hard failure, or warning in strict mode

