"""Real PostgreSQL integration tests.

These tests require a running PostgreSQL database and are gated behind
the PAPERWEIGHT_TEST_DATABASE_URL environment variable.

To run these tests:
    export PAPERWEIGHT_TEST_DATABASE_URL="postgresql://user:pass@localhost:5432/paperweight_test"
    pytest tests/api/test_database.py -v
"""

import os
from datetime import date

import pytest

DATABASE_URL_ENV = "PAPERWEIGHT_TEST_DATABASE_URL"


def parse_database_url(url: str) -> dict:
    """Parse a PostgreSQL URL into a config dict."""
    # postgresql://user:pass@host:port/database
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/"),
        "user": parsed.username,
        "password": parsed.password,
        "sslmode": "prefer",
    }


@pytest.fixture
def db_config():
    """Get database config from environment."""
    url = os.getenv(DATABASE_URL_ENV)
    if not url:
        pytest.skip(f"Set {DATABASE_URL_ENV} to run database tests")
    return parse_database_url(url)


@pytest.fixture
def db_connection(db_config):
    """Create a database connection for testing."""
    from paperweight.db import connect_db

    with connect_db(db_config) as conn:
        yield conn
        # Rollback any uncommitted changes to keep tests isolated
        conn.rollback()


@pytest.mark.api
class TestRealDatabase:
    """Tests against a real PostgreSQL database."""

    def test_create_and_finish_run(self, db_connection):
        """Create a run record and mark it complete."""
        from paperweight.storage import create_run, finish_run

        run_id = create_run(
            db_connection,
            config_hash="test_hash_123",
            pipeline_version="0.1.0",
            notes="test run",
        )

        assert run_id is not None

        finish_run(db_connection, run_id, "success", notes="completed")

        # Verify the run was updated
        with db_connection.cursor() as cursor:
            cursor.execute(
                "SELECT status, notes FROM runs WHERE id = %s",
                (run_id,),
            )
            row = cursor.fetchone()
            assert row[0] == "success"
            assert row[1] == "completed"

    def test_upsert_papers_idempotent(self, db_connection):
        """Upserting the same paper twice returns the same ID."""
        from paperweight.storage import upsert_papers

        papers = [
            {
                "id": "test.12345",
                "link": "https://arxiv.org/abs/test.12345",
                "title": "Test Paper",
                "abstract": "Test abstract",
                "date": date(2024, 1, 15),
            }
        ]

        # First upsert
        result1 = upsert_papers(db_connection, papers)
        db_connection.commit()

        # Second upsert of same paper
        result2 = upsert_papers(db_connection, papers)
        db_connection.commit()

        # Should get the same paper ID
        assert ("test.12345", "v0") in result1
        assert ("test.12345", "v0") in result2
        assert result1[("test.12345", "v0")] == result2[("test.12345", "v0")]

    def test_full_storage_cycle(self, db_connection):
        """Complete storage cycle: run, papers, scores, summaries."""
        from paperweight.storage import (
            create_run,
            finish_run,
            insert_scores,
            insert_summaries,
            upsert_papers,
        )

        # Create run
        run_id = create_run(
            db_connection,
            config_hash="cycle_test",
            pipeline_version="0.1.0",
        )

        # Upsert papers
        papers = [
            {
                "id": "cycle.001",
                "link": "https://arxiv.org/abs/cycle.001",
                "title": "Cycle Test Paper",
                "abstract": "Testing the full cycle",
                "date": date(2024, 1, 15),
                "relevance_score": 0.85,
                "score_breakdown": {"keyword": 0.5, "category": 0.35},
                "summary": "This paper tests the storage cycle.",
            }
        ]
        paper_id_map = upsert_papers(db_connection, papers)

        # Insert scores
        insert_scores(db_connection, run_id, papers, paper_id_map)

        # Insert summaries
        insert_summaries(db_connection, run_id, papers, paper_id_map, model="test")

        # Finish run
        finish_run(db_connection, run_id, "success")

        db_connection.commit()

        # Verify everything was stored
        with db_connection.cursor() as cursor:
            # Check run
            cursor.execute("SELECT status FROM runs WHERE id = %s", (run_id,))
            assert cursor.fetchone()[0] == "success"

            # Check paper
            paper_id = paper_id_map[("cycle.001", "v0")]
            cursor.execute("SELECT title FROM papers WHERE id = %s", (paper_id,))
            assert cursor.fetchone()[0] == "Cycle Test Paper"

            # Check score
            cursor.execute(
                "SELECT score FROM scores WHERE run_id = %s AND paper_id = %s",
                (run_id, paper_id),
            )
            assert cursor.fetchone()[0] == pytest.approx(0.85)

            # Check summary
            cursor.execute(
                "SELECT summary_text FROM summaries WHERE run_id = %s AND paper_id = %s",
                (run_id, paper_id),
            )
            assert "storage cycle" in cursor.fetchone()[0]
