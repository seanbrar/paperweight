"""Persistence helpers for Postgres-backed paperweight runs."""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Json

from paperweight.utils import split_arxiv_id

logger = logging.getLogger(__name__)


def create_run(
    conn: Connection,
    config_hash: str,
    pipeline_version: str,
    notes: Optional[str] = None,
) -> UUID:
    """Create a new pipeline run record.

    Args:
        conn: Database connection.
        config_hash: Hash of the configuration used for this run.
        pipeline_version: Version of the pipeline.
        notes: Optional notes for the run.

    Returns:
        UUID of the created run.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO runs (status, config_hash, pipeline_version, notes)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            ("running", config_hash, pipeline_version, notes),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("Failed to create run record")
        return row[0]


def get_last_successful_run_date(conn: Connection) -> Optional[date]:
    """Get the completion date of the last successful run.

    Args:
        conn: Database connection.

    Returns:
        Date of the last successful run, or None if no successful runs exist.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT completed_at
            FROM runs
            WHERE status = 'success'
            ORDER BY completed_at DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row or row[0] is None:
            return None
        return row[0].date()


def finish_run(
    conn: Connection,
    run_id: UUID,
    status: str,
    notes: Optional[str] = None,
) -> None:
    """Mark a run as finished with the given status.

    Args:
        conn: Database connection.
        run_id: UUID of the run to update.
        status: Final status ('success' or 'failed').
        notes: Optional notes (e.g., error message on failure).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE runs
            SET status = %s, completed_at = now(), notes = %s
            WHERE id = %s
            """,
            (status, notes, run_id),
        )


def upsert_papers(
    conn: Connection, papers: List[Dict[str, Any]]
) -> Dict[Tuple[str, str], UUID]:
    """Insert or update paper records.

    Args:
        conn: Database connection.
        papers: List of paper dictionaries.

    Returns:
        Mapping of (arxiv_id, version) tuples to database UUIDs.
    """
    paper_id_map: Dict[Tuple[str, str], UUID] = {}
    with conn.cursor() as cur:
        for paper in papers:
            arxiv_id, arxiv_version = split_arxiv_id(paper.get("id") or paper["link"])
            published_at = paper.get("date")
            if isinstance(published_at, datetime):
                published_at = published_at.date()
            title = paper.get("title") or f"Untitled ({arxiv_id})"
            cur.execute(
                """
                INSERT INTO papers (
                    arxiv_id,
                    arxiv_version,
                    title,
                    abstract,
                    published_at,
                    updated_at,
                    primary_category,
                    categories,
                    link,
                    doi,
                    authors
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (arxiv_id, arxiv_version) DO UPDATE SET
                    title = EXCLUDED.title,
                    abstract = EXCLUDED.abstract,
                    published_at = EXCLUDED.published_at,
                    updated_at = EXCLUDED.updated_at,
                    primary_category = EXCLUDED.primary_category,
                    categories = EXCLUDED.categories,
                    link = EXCLUDED.link,
                    doi = EXCLUDED.doi,
                    authors = EXCLUDED.authors
                RETURNING id
                """,
                (
                    arxiv_id,
                    arxiv_version,
                    title,
                    paper.get("abstract"),
                    published_at,
                    paper.get("updated_at"),
                    paper.get("primary_category"),
                    paper.get("categories"),
                    paper.get("link"),
                    paper.get("doi"),
                    paper.get("authors"),
                ),
            )
            row = cur.fetchone()
            if row is None:
                logger.error("Failed to upsert paper %s", arxiv_id)
                continue
            paper_id_map[(arxiv_id, arxiv_version)] = row[0]
    return paper_id_map


def insert_scores(
    conn: Connection,
    run_id: UUID,
    papers: List[Dict[str, Any]],
    paper_id_map: Dict[Tuple[str, str], UUID],
    score_type: str = "keyword",
) -> None:
    """Insert relevance scores for papers.

    Args:
        conn: Database connection.
        run_id: UUID of the current run.
        papers: List of processed paper dictionaries with scores.
        paper_id_map: Mapping of (arxiv_id, version) to database UUIDs.
        score_type: Type of score (default: "keyword").
    """
    with conn.cursor() as cur:
        for paper in papers:
            arxiv_id, arxiv_version = split_arxiv_id(paper.get("id") or paper["link"])
            paper_id = paper_id_map.get((arxiv_id, arxiv_version))
            if not paper_id:
                logger.warning(
                    "Skipping score insert; missing paper_id for %s",
                    paper.get("link"),
                )
                continue
            cur.execute(
                """
                INSERT INTO scores (run_id, paper_id, score_type, score, details_json)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    paper_id,
                    score_type,
                    paper.get("relevance_score"),
                    Json(paper.get("score_breakdown")),
                ),
            )


def insert_summaries(
    conn: Connection,
    run_id: UUID,
    papers: List[Dict[str, Any]],
    paper_id_map: Dict[Tuple[str, str], UUID],
    model: Optional[str] = None,
    prompt_hash: Optional[str] = None,
) -> None:
    """Insert paper summaries.

    Args:
        conn: Database connection.
        run_id: UUID of the current run.
        papers: List of processed paper dictionaries with summaries.
        paper_id_map: Mapping of (arxiv_id, version) to database UUIDs.
        model: Model identifier used for summarization.
        prompt_hash: Hash of the prompt used for summarization.
    """
    with conn.cursor() as cur:
        for paper in papers:
            summary = paper.get("summary")
            if not summary:
                continue
            arxiv_id, arxiv_version = split_arxiv_id(paper.get("id") or paper["link"])
            paper_id = paper_id_map.get((arxiv_id, arxiv_version))
            if not paper_id:
                logger.warning(
                    "Skipping summary insert; missing paper_id for %s",
                    paper.get("link"),
                )
                continue
            cur.execute(
                """
                INSERT INTO summaries (run_id, paper_id, summary_text, model, prompt_hash)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (run_id, paper_id, summary, model, prompt_hash),
            )


def insert_artifacts(
    conn: Connection,
    papers: List[Dict[str, Any]],
    paper_id_map: Dict[Tuple[str, str], UUID],
) -> None:
    """Insert paper artifact records.

    Args:
        conn: Database connection.
        papers: List of paper dictionaries with artifact metadata.
        paper_id_map: Mapping of (arxiv_id, version) to database UUIDs.
    """
    with conn.cursor() as cur:
        for paper in papers:
            artifacts = paper.get("artifacts") or []
            if not artifacts:
                continue
            arxiv_id, arxiv_version = split_arxiv_id(paper.get("id") or paper["link"])
            paper_id = paper_id_map.get((arxiv_id, arxiv_version))
            if not paper_id:
                logger.warning(
                    "Skipping artifacts insert; missing paper_id for %s",
                    paper.get("link"),
                )
                continue
            for artifact in artifacts:
                cur.execute(
                    """
                    INSERT INTO paper_artifacts (
                        paper_id,
                        artifact_type,
                        storage_uri,
                        checksum,
                        byte_size
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        paper_id,
                        artifact.get("type"),
                        artifact.get("uri"),
                        artifact.get("checksum"),
                        artifact.get("byte_size"),
                    ),
                )
