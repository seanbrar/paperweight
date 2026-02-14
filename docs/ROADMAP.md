# paperweight roadmap

This roadmap is metric-driven. Feature work is only accepted if it improves usefulness:
time saved, setup simplicity, and digest quality.

## Product definition

paperweight should be better than "just checking arXiv" when the user wants:

- a smaller daily reading queue
- deterministic output that can be automated
- relevance filtering that improves over time

## Core success metrics

These metrics guide all releases:

1. **Time to first useful run**
   - target: <= 5 minutes from install to first digest
2. **Daily digest size**
   - target: median 5-20 items after user tuning
3. **Runtime**
   - target: <= 120 seconds for `3 categories x max_results=50` on default non-summary mode
4. **CLI reliability**
   - target: >= 99% successful runs in local smoke workflows
5. **Signal quality (human-evaluated)**
   - target: >= 7/10 items marked "worth reading" in pilot usage

## v0.2 release gates (must pass)

1. CLI contract stable:
   - `run`, `init`, `doctor`
   - `run` delivery: `stdout`, `json`, `atom`, optional `email`
2. Zero-key baseline works:
   - `init` defaults to `analyzer.type: abstract`
   - `run` works without LLM keys via triage fallback
3. Setup validation:
   - `doctor --strict` returns non-zero on warnings/failures
4. Output ergonomics:
   - deterministic text digest
   - scriptable JSON
   - Atom feed export
5. Quality checks:
   - lint clean
   - tests green (including small CLI integration suite)
6. Packaging:
   - release workflow present and tag-driven

## v0.3 focus (quality lift, not surface-area lift)

1. **Speed**
   - add metadata cache
   - target: >= 40% runtime reduction on repeated daily runs
2. **Digest quality**
   - improve triage rationale quality and compactness
   - target: rationale present on >= 95% of shortlisted items
3. **Workflow fit**
   - add saved presets/profile switching
   - target: switch profile in one command, no config edits

## v0.4 focus (feedback loop)

1. add local feedback capture (`relevant` / `irrelevant`)
2. incorporate feedback into ranking
3. target: +20% improvement in user-rated relevance from v0.2 baseline

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
