# paperweight roadmap

This roadmap replaces the previous feature backlog.
The focus is a useful, low-friction product in `v0.2`, not a distant `v1.0`.

## Product thesis

paperweight should save time by doing high-signal triage on arXiv papers and
producing a short digest users can trust.

The default experience must be:

1. zero setup beyond a config file and LLM key
2. fast enough to run frequently
3. deterministic, scriptable output

## Principles (DOTADIW + YAGNI)

- Default to the simplest path that works.
- Do not require SMTP, Postgres, or dashboards for baseline usage.
- Keep one clear interface and one clear output model.
- Add adapters only when they materially improve delivery.
- Prefer deleting complexity over abstracting it.

## v0.2 (MVP that is already good)

### UX and interface

- [x] Default delivery is deterministic `stdout` digest.
- [x] Add Atom feed output as a secondary delivery format.
- [ ] Add `paperweight init` for minimal config bootstrap.
- [ ] Add `paperweight doctor` for config/env/provider checks.

### AI and ranking

- [x] Make AI relevance judgment core for triage (title + abstract first).
- [ ] Keep summarization bounded with hard input limits.
- [ ] Produce one-line "why this matched" rationale for each paper.

### Performance

- [x] Stop downloading full content for all candidates by default.
- [x] Fetch/extract full text only for shortlisted papers.
- [ ] Add simple local caching for fetched metadata by run.

### Docs

- [ ] Rewrite README around "5-minute first digest".
- [ ] Remove claims not implemented in code.
- [ ] Document output formats and scripting examples.

## v0.3-v0.5 (quality and fit)

- [ ] Tighten scoring quality using user feedback signals.
- [ ] Improve digest rendering (grouping, rationale clarity, compact layout).
- [ ] Add optional adapters where demand exists (email via keychain-backed auth).
- [ ] Stabilize config schema and migration notes.

## Road to v1.0

`v1.0` means stability and reliability, not a huge scope jump:

- Stable CLI contract and config schema.
- Strong test coverage on core triage flow.
- Backward-compatible upgrades from `v0.2+`.
- Operationally boring: predictable runtime, deterministic outputs, clear failures.

## Explicit non-goals (for now)

- Web app/dashboard before core CLI flow is excellent.
- Multi-source ingestion before arXiv triage quality is strong.
- Complex recommendation systems without a validated feedback loop.
