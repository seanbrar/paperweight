# CLI reference

paperweight has three commands:

1. `run`: execute the pipeline and deliver output
2. `init`: create a minimal config
3. `doctor`: validate local setup

`paperweight` is shorthand for `paperweight run`.

## run

```bash
paperweight run \
  [--config PATH] \
  [--force-refresh] \
  [--delivery stdout|json|atom|email] \
  [--output PATH] \
  [--sort-order relevance|alphabetical|publication_time] \
  [--max-items N]
```

Behavior:

- fetches recent arXiv papers
- runs triage on title + abstract
- hydrates full text only for shortlisted papers
- scores/summarizes and delivers digest
- `--max-items N` caps how many fetched papers enter processing (triage/hydration/summary); output may be fewer than `N` after filtering

Delivery modes:

- `stdout`: plain text digest (default)
- `json`: script-friendly array of objects
- `atom`: Atom feed XML
- `email`: SMTP send via `notifier.email` config

`json` fields:

- `title`
- `date`
- `score`
- `why`
- `link`
- `summary`

## init

```bash
paperweight init [--config PATH] [--force]
```

Behavior:

- writes a minimal `config.yaml` template
- refuses to overwrite unless `--force` is passed

## doctor

```bash
paperweight doctor [--config PATH] [--strict]
```

Checks:

- config file exists
- config parses and validates
- triage provider key availability
- enabled delivery adapters

Exit codes:

- `0`: healthy (or warnings present without `--strict`)
- `1`: hard failure, or warning in strict mode
