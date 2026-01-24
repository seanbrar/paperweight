-- paperweight database schema (Postgres)
-- Run this on a fresh database.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  status text NOT NULL,
  config_hash text NOT NULL,
  pipeline_version text NOT NULL,
  notes text
);

CREATE TABLE papers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  arxiv_id text NOT NULL,
  arxiv_version text NOT NULL,
  title text NOT NULL,
  abstract text,
  published_at date,
  updated_at timestamptz,
  primary_category text,
  categories text[],
  link text,
  doi text,
  authors text[],
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (arxiv_id, arxiv_version)
);

CREATE TABLE paper_artifacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  paper_id uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  artifact_type text NOT NULL,
  storage_uri text NOT NULL,
  checksum text,
  byte_size bigint,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE scores (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  paper_id uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  score_type text NOT NULL,
  score double precision NOT NULL,
  details_json jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE summaries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  paper_id uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  summary_text text NOT NULL,
  model text,
  prompt_hash text,
  token_usage_json jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE paper_labels (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  paper_id uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  label_source text NOT NULL,
  label_value boolean NOT NULL,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (paper_id, label_source)
);

CREATE INDEX papers_arxiv_id_idx ON papers (arxiv_id);
CREATE INDEX papers_published_at_idx ON papers (published_at);
CREATE INDEX scores_run_id_idx ON scores (run_id);
CREATE INDEX scores_paper_id_idx ON scores (paper_id);
CREATE INDEX paper_artifacts_paper_id_idx ON paper_artifacts (paper_id);
CREATE INDEX summaries_run_id_idx ON summaries (run_id);
CREATE INDEX summaries_paper_id_idx ON summaries (paper_id);
