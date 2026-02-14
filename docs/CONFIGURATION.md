# paperweight configuration

paperweight keeps config intentionally simple.

## Minimal config

```yaml
arxiv:
  categories: ["cs.AI", "cs.CL"]
  max_results: 50

processor:
  keywords: ["transformer", "reasoning", "agents"]
  exclusion_keywords: []
  important_words: []
  title_keyword_weight: 3
  abstract_keyword_weight: 2
  content_keyword_weight: 1
  exclusion_keyword_penalty: 5
  important_words_weight: 0.5
  min_score: 10

analyzer:
  type: summary  # abstract | summary
  llm_provider: openai  # openai | gemini

logging:
  level: INFO
  file: paperweight.log
```

With this config, `paperweight` outputs a digest to `stdout`.

## Optional sections

### `notifier` (only for `--delivery email`)

```yaml
notifier:
  email:
    to: "you@example.com"
    from: "you@example.com"
    password: "${EMAIL_PASSWORD}"
    smtp_server: "smtp.example.com"
    smtp_port: 587
    use_tls: true
    use_auth: true
    sort_order: relevance
```

If you do not use `--delivery email`, this section is optional.

### `feed` (metadata for `--delivery atom`)

```yaml
feed:
  title: "paperweight"
  id: "https://github.com/seanbrar/paperweight"
  link: "https://github.com/seanbrar/paperweight"
```

### `db` (optional Postgres persistence)

```yaml
db:
  enabled: false
  host: localhost
  port: 5432
  database: paperweight
  user: paperweight
  password: "${DB_PASSWORD}"
  sslmode: prefer
```

### `storage` (artifact storage, used with DB workflows)

```yaml
storage:
  base_dir: data/artifacts
```

## Environment overrides

`PAPERWEIGHT_` env vars override config values.

Preferred nested form:

```bash
export PAPERWEIGHT_ARXIV_MAX_RESULTS=100
```

Legacy leaf form is still supported:

```bash
export PAPERWEIGHT_MAX_RESULTS=100
```

## Analyzer keys

When `analyzer.type: summary`, API key is required:

- `OPENAI_API_KEY` for OpenAI
- `GEMINI_API_KEY` for Gemini

## CLI + config interaction

- `--delivery stdout` ignores `notifier`.
- `--delivery atom` uses optional `feed` metadata.
- `--delivery email` requires valid `notifier.email` settings.
