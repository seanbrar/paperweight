"""Tests for the database storage module."""

from datetime import date, datetime
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from paperweight.storage import (
    create_run,
    finish_run,
    get_last_successful_run_date,
    insert_artifacts,
    insert_scores,
    insert_summaries,
    upsert_papers,
)


@pytest.fixture
def mock_conn():
    """Create a mock database connection with cursor."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


class TestCreateRun:
    """Tests for create_run function."""

    def test_create_run_success(self, mock_conn):
        """Test successful run creation."""
        conn, cursor = mock_conn
        test_uuid = UUID("12345678-1234-5678-1234-567812345678")
        cursor.fetchone.return_value = (test_uuid,)

        result = create_run(conn, "config_hash_123", "1.0.0")

        assert result == test_uuid
        cursor.execute.assert_called_once()
        call_args = cursor.execute.call_args
        assert "INSERT INTO runs" in call_args[0][0]
        assert call_args[0][1] == ("running", "config_hash_123", "1.0.0", None)

    def test_create_run_with_notes(self, mock_conn):
        """Test run creation with notes."""
        conn, cursor = mock_conn
        test_uuid = UUID("12345678-1234-5678-1234-567812345678")
        cursor.fetchone.return_value = (test_uuid,)

        create_run(conn, "hash", "1.0.0", notes="Test notes")

        call_args = cursor.execute.call_args
        assert call_args[0][1][3] == "Test notes"

    def test_create_run_no_result(self, mock_conn):
        """Test run creation when no result is returned."""
        conn, cursor = mock_conn
        cursor.fetchone.return_value = None

        with pytest.raises(RuntimeError, match="Failed to create run record"):
            create_run(conn, "hash", "1.0.0")


class TestGetLastSuccessfulRunDate:
    """Tests for get_last_successful_run_date function."""

    def test_get_last_successful_run_date_found(self, mock_conn):
        """Test when a successful run exists."""
        conn, cursor = mock_conn
        test_datetime = datetime(2024, 1, 15, 10, 30, 0)
        cursor.fetchone.return_value = (test_datetime,)

        result = get_last_successful_run_date(conn)

        assert result == date(2024, 1, 15)
        cursor.execute.assert_called_once()
        assert "WHERE status = 'success'" in cursor.execute.call_args[0][0]

    def test_get_last_successful_run_date_not_found(self, mock_conn):
        """Test when no successful run exists."""
        conn, cursor = mock_conn
        cursor.fetchone.return_value = None

        result = get_last_successful_run_date(conn)

        assert result is None

    def test_get_last_successful_run_date_null_timestamp(self, mock_conn):
        """Test when completed_at is NULL."""
        conn, cursor = mock_conn
        cursor.fetchone.return_value = (None,)

        result = get_last_successful_run_date(conn)

        assert result is None


class TestFinishRun:
    """Tests for finish_run function."""

    def test_finish_run_success(self, mock_conn):
        """Test marking a run as successful."""
        conn, cursor = mock_conn
        run_id = UUID("12345678-1234-5678-1234-567812345678")

        finish_run(conn, run_id, "success")

        cursor.execute.assert_called_once()
        call_args = cursor.execute.call_args
        assert "UPDATE runs" in call_args[0][0]
        assert call_args[0][1] == ("success", None, run_id)

    def test_finish_run_failed_with_notes(self, mock_conn):
        """Test marking a run as failed with error notes."""
        conn, cursor = mock_conn
        run_id = UUID("12345678-1234-5678-1234-567812345678")

        finish_run(conn, run_id, "failed", notes="Connection timeout")

        call_args = cursor.execute.call_args
        assert call_args[0][1] == ("failed", "Connection timeout", run_id)


class TestUpsertPapers:
    """Tests for upsert_papers function."""

    def test_upsert_papers_single(self, mock_conn):
        """Test upserting a single paper."""
        conn, cursor = mock_conn
        paper_uuid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        cursor.fetchone.return_value = (paper_uuid,)

        papers = [
            {
                "id": "2401.12345",
                "link": "https://arxiv.org/abs/2401.12345",
                "title": "Test Paper",
                "abstract": "Test abstract",
                "date": date(2024, 1, 15),
            }
        ]

        result = upsert_papers(conn, papers)

        assert ("2401.12345", "v0") in result
        assert result[("2401.12345", "v0")] == paper_uuid

    def test_upsert_papers_with_version(self, mock_conn):
        """Test upserting a paper with explicit version."""
        conn, cursor = mock_conn
        paper_uuid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        cursor.fetchone.return_value = (paper_uuid,)

        papers = [{"id": "2401.12345v2", "title": "Test Paper"}]

        result = upsert_papers(conn, papers)

        assert ("2401.12345", "v2") in result

    def test_upsert_papers_no_result(self, mock_conn):
        """Test handling when upsert returns no result."""
        conn, cursor = mock_conn
        cursor.fetchone.return_value = None

        papers = [{"id": "2401.12345", "title": "Test Paper"}]

        result = upsert_papers(conn, papers)

        # Should log error and continue, returning empty map
        assert len(result) == 0


class TestInsertScores:
    """Tests for insert_scores function."""

    def test_insert_scores(self, mock_conn):
        """Test inserting paper scores."""
        conn, cursor = mock_conn
        run_id = UUID("12345678-1234-5678-1234-567812345678")
        paper_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        paper_id_map = {("2401.12345", "v0"): paper_id}

        papers = [
            {
                "id": "2401.12345",
                "relevance_score": 0.85,
                "score_breakdown": {"keyword": 0.5, "category": 0.35},
            }
        ]

        insert_scores(conn, run_id, papers, paper_id_map)

        cursor.execute.assert_called_once()
        call_args = cursor.execute.call_args
        assert "INSERT INTO scores" in call_args[0][0]

    def test_insert_scores_missing_paper_id(self, mock_conn):
        """Test that missing paper IDs are skipped with a warning."""
        conn, cursor = mock_conn
        run_id = UUID("12345678-1234-5678-1234-567812345678")
        paper_id_map = {}  # Empty map

        papers = [{"id": "2401.12345", "relevance_score": 0.85}]

        # Should not raise, just log warning and skip
        insert_scores(conn, run_id, papers, paper_id_map)

        cursor.execute.assert_not_called()


class TestInsertSummaries:
    """Tests for insert_summaries function."""

    def test_insert_summaries(self, mock_conn):
        """Test inserting paper summaries."""
        conn, cursor = mock_conn
        run_id = UUID("12345678-1234-5678-1234-567812345678")
        paper_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        paper_id_map = {("2401.12345", "v0"): paper_id}

        papers = [{"id": "2401.12345", "summary": "This paper presents..."}]

        insert_summaries(conn, run_id, papers, paper_id_map, model="gpt-4")

        cursor.execute.assert_called_once()
        call_args = cursor.execute.call_args
        assert "INSERT INTO summaries" in call_args[0][0]

    def test_insert_summaries_no_summary(self, mock_conn):
        """Test that papers without summaries are skipped."""
        conn, cursor = mock_conn
        run_id = UUID("12345678-1234-5678-1234-567812345678")
        paper_id_map = {("2401.12345", "v0"): UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")}

        papers = [{"id": "2401.12345"}]  # No summary field

        insert_summaries(conn, run_id, papers, paper_id_map)

        cursor.execute.assert_not_called()


class TestInsertArtifacts:
    """Tests for insert_artifacts function."""

    def test_insert_artifacts(self, mock_conn):
        """Test inserting paper artifacts."""
        conn, cursor = mock_conn
        paper_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        paper_id_map = {("2401.12345", "v0"): paper_id}

        papers = [
            {
                "id": "2401.12345",
                "artifacts": [
                    {
                        "type": "pdf",
                        "uri": "/data/2401.12345/source.pdf",
                        "checksum": "abc123",
                        "byte_size": 1024,
                    }
                ],
            }
        ]

        insert_artifacts(conn, papers, paper_id_map)

        cursor.execute.assert_called_once()
        call_args = cursor.execute.call_args
        assert "INSERT INTO paper_artifacts" in call_args[0][0]

    def test_insert_artifacts_empty(self, mock_conn):
        """Test that papers without artifacts are skipped."""
        conn, cursor = mock_conn
        paper_id_map = {("2401.12345", "v0"): UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")}

        papers = [{"id": "2401.12345", "artifacts": []}]

        insert_artifacts(conn, papers, paper_id_map)

        cursor.execute.assert_not_called()
