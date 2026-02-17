# paperweight roadmap

This roadmap is metric-driven. Feature work is only accepted if it improves usefulness:
time saved, setup simplicity, and digest quality.

## Product definition

paperweight is a **fast, scriptable arXiv interface** — the himalaya of academic papers.
It fetches structured arXiv data, scores by keywords, and outputs rich JSON.
AI enrichment (triage, summarization) is available via config but imposes zero cost
on the default path.

paperweight should be better than "just checking arXiv" when the user wants:

- a smaller daily reading queue
- deterministic output that can be automated and piped
- keyword-scored relevance filtering out of the box
- structured metadata (authors, categories, PDF URLs) for scripting

## Core success metrics

These metrics guide all releases:

1. **Time to first useful run**
   - target: <= 2 minutes from install to first digest
2. **Daily digest size**
   - target: median 5-20 items after user tuning
3. **Runtime**
   - target: sub-second warm runs (metadata cached), <= 60s cold fetch for 3 categories x 50 papers
4. **CLI reliability**
   - target: >= 99% successful runs in local smoke workflows
5. **Signal quality (human-evaluated)**
   - target: >= 7/10 items marked "worth reading" in pilot usage

## v0.3 focus (config resilience, richer metadata, performance, CLI polish)

1. **Config resilience**
   - DEFAULT_CONFIG ensures partial/minimal configs never crash
   - triage disabled by default (opt-in via config)
   - log file optional (stderr-only by default)
   - target: `paperweight run` works with only `arxiv.categories` set
2. **Richer metadata**
   - capture authors, categories, PDF URL, arXiv ID from API
   - track which keywords matched during scoring
   - JSON output includes full structured data contract
   - target: JSON schema always complete without AI
3. **Performance**
   - lazy imports for heavy dependencies (psycopg, pollux, tiktoken, pypdf)
   - parallel category fetching
   - target: sub-second warm runs, ~3x cold-fetch speedup
4. **CLI polish & API surface**
   - `--version` flag
   - `init` prints clean error (not traceback) when config exists
   - `__init__.py` exposes `__version__` and key public functions
   - target: scriptable from `import paperweight` without submodule diving

## v0.4 focus (typed data, AI enrichment, feedback loop)

1. **Typed data structures**
   - replace `Dict[str, Any]` pipeline with `Paper` dataclass/Pydantic model
   - eliminate in-place mutation in `process_papers` (return new objects)
   - target: zero `KeyError` risk from undocumented dict keys
2. **AI enrichment polish**
   - improve triage rationale quality and compactness
   - target: rationale present on >= 95% of shortlisted items when triage enabled
3. **Feedback loop**
   - add local feedback capture (`relevant` / `irrelevant`)
   - incorporate feedback into ranking
   - target: +20% improvement in user-rated relevance from v0.2 baseline

## v1.0 criteria

1. stable CLI and config semantics
2. upgrade path documented for all `v0.x` users
3. reproducible, deterministic outputs for identical inputs/config
4. reliability and quality metrics sustained for two consecutive minor releases

## Non-goals (until metrics justify)

- web dashboard
- many new paper sources
- broad plugin systems
- complex recommendation models without feedback data
