# FAQ

## Is paperweight still useful if I can just check arXiv directly?

Yes, if your main pain is triage time. paperweight is best when you want:

- a short, ranked list instead of scanning every new submission
- consistent daily output with the same filters
- scriptable output (`json`/`atom`) for your own workflows

If you enjoy broad discovery and manual browsing, arXiv directly may be better.

## Do I need API keys?

No for basic usage.

- `init`, `doctor`, and `run` in `analyzer.type: abstract` mode work without keys.
- if triage key is missing, triage falls back to heuristic mode.
- summaries in `analyzer.type: summary` require a provider key.

## What should I use as a first-run setup?

```bash
paperweight init
paperweight doctor
paperweight run --force-refresh
```

## Which output mode should I choose?

- `stdout`: best for direct terminal use
- `json`: best for scripts/automation
- `atom`: best for feed readers
- `email`: best for push delivery when SMTP is configured

## How do I keep runs fast?

- keep `arxiv.max_results` moderate
- use triage to shortlist aggressively (`triage.min_score`, `triage.max_selected`)
- stay on `analyzer.type: abstract` unless summaries are needed

## How do I validate setup in CI before release?

Use:

```bash
paperweight doctor --strict
```

This returns non-zero if warnings are present.
