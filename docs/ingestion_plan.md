# Ingestion Plan (paperweight)

## Goals
- Persist raw arXiv metadata, extracted content, and outputs with run lineage.
- Support reproducible runs and future evaluation without relying on local files.
- Keep ingestion idempotent using arXiv ID + version.

## Step-by-step flow

1) Initialize run
- Create a `runs` record with `config_hash`, `pipeline_version`, and status `running`.
- Use the most recent successful run as the watermark for incremental fetch.

2) Fetch metadata from arXiv
- Query categories with `start` + `max_results` paging.
- Stop when `published_at` < watermark date.
- Upsert into `papers` on `(arxiv_id, arxiv_version)`.

3) Fetch and store content
- For new paper versions, download source/PDF.
- Write raw files to object storage or local `data/` and save `paper_artifacts`.
- Extract text once and store as `paper_artifacts` type `text`.
- Optionally chunk and store in `paper_text_chunks`.

4) Scoring
- Run baseline keyword scoring.
- Insert `scores` rows with a structured `details_json` breakdown.

5) Summarization
- Generate summaries with prompt + model metadata.
- Cache by `prompt_hash` to avoid re-summarization.
- Insert `summaries` rows with token usage metadata.

6) Notification
- Build notification payload from `scores` + `summaries`.
- Insert a `notifications` row and mark as `sent` when delivered.

7) Finalize run
- Update `runs` status to `success` or `failed`, set `completed_at`.

## Evaluation-ready data
- Use `paper_labels` to store human relevance labels.
- Metrics can be computed per `run_id` and compared across runs.
