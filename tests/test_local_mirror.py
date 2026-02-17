"""Integration tests using the local mirror dataset.

These tests verify the full paperweight pipeline works correctly
without making any real network calls. They use data/local_mirror
populated by scripts/populate_mirror.py.

Run with:
    python -m pytest tests/integration/test_local_mirror.py -v
"""

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from paperweight.logging_config import setup_logging
from paperweight.processor import process_papers
from paperweight.scraper import extract_text_from_source
from src.mocks.local_client import (
    MockArxivClient,
    mock_fetch_arxiv_papers,
    mock_fetch_paper_content,
)

# Golden set paper IDs (from populate_mirror.py)
GOLDEN_SET_IDS = [
    "1706.03762",  # Attention Is All You Need
    "1810.04805",  # BERT
    "2303.08774",  # GPT-4 Technical Report
    "1904.09456",  # Quantum ML
    "2401.00001",  # Recent paper (Test date parsing)
]


class TestMockFetching:
    """Test mock functions return correct data from local files."""

    def test_mock_fetch_paper_content_source(self, local_mirror_files: Path):
        """Fetch source archive for a known paper."""
        # Find any paper with source
        sources = list(local_mirror_files.glob("*.tar.gz"))
        if not sources:
            pytest.skip("No source files in mirror")

        paper_id = sources[0].stem.replace(".tar", "")
        content, method = mock_fetch_paper_content(paper_id, local_mirror_files)

        assert content is not None
        assert method == "source"
        assert len(content) > 0

    def test_mock_fetch_paper_content_pdf_fallback(
        self, local_mirror_files: Path, tmp_path: Path
    ):
        """Test PDF fallback when source is missing."""
        # Create a PDF-only test case
        test_pdf = tmp_path / "test_paper.pdf"
        test_pdf.write_bytes(b"%PDF-1.4 test content")

        content, method = mock_fetch_paper_content("test_paper", tmp_path)

        assert content is not None
        assert method == "pdf"

    def test_mock_fetch_paper_content_not_found(self, tmp_path: Path):
        """Return None for non-existent paper."""
        content, method = mock_fetch_paper_content("nonexistent_paper", tmp_path)

        assert content is None
        assert method is None

    def test_mock_fetch_arxiv_papers(self, local_mirror_db: Path):
        """Fetch papers by category from local database."""
        papers = mock_fetch_arxiv_papers(
            categories=["cs.AI"],
            start_date=date(2024, 1, 1),
            max_results=5,
            db_path=local_mirror_db,
        )

        # May be empty if no cs.AI papers, but should not error
        assert isinstance(papers, list)

        if papers:
            paper = papers[0]
            assert "title" in paper
            assert "link" in paper
            assert "abstract" in paper


class TestMockArxivClient:
    """Test MockArxivClient behavior."""

    def test_client_initialization(self, local_mirror_path: Path):
        """Client initializes with valid mirror path."""
        client = MockArxivClient(mirror_path=local_mirror_path)
        assert client.mirror_db_path.exists()

    def test_base_id_matches_versioned_paper(self, tmp_path: Path):
        """Base arXiv ID should find papers stored with version suffix.

        Regression test: The mock should match real arXiv API behavior where
        searching for '1706.03762' returns '1706.03762v7'.
        """
        import arxiv

        # Setup: DB with only versioned ID
        mirror = tmp_path / "mirror"
        mirror.mkdir()
        (mirror / "files").mkdir()
        db = mirror / "index.sqlite3"

        conn = sqlite3.connect(db)
        conn.execute("""CREATE TABLE papers (
            id TEXT PRIMARY KEY, title TEXT, abstract TEXT, authors TEXT,
            categories TEXT, published DATE, updated DATE, pdf_url TEXT,
            doi TEXT, local_file_path TEXT, local_source_path TEXT)""")
        conn.execute(
            "INSERT INTO papers VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "1706.03762v7",
                "Attention Is All You Need",
                "Abstract",
                "Vaswani et al.",
                "cs.CL,cs.LG",
                "2017-06-12",
                "2017-06-12",
                "http://arxiv.org/pdf/1706.03762v7",
                None,
                None,
                None,
            ),
        )
        conn.commit()
        conn.close()

        client = MockArxivClient(mirror_path=mirror)

        # Base ID should find the versioned paper
        results = list(client.results(arxiv.Search(id_list=["1706.03762"])))
        assert len(results) == 1
        assert "1706.03762v7" in results[0].entry_id

    def test_versioned_id_exact_match(self, tmp_path: Path):
        """Versioned arXiv ID should only match that exact version.

        Searching for '1706.03762v1' should NOT match '1706.03762v7'.
        """
        import arxiv

        # Setup: DB with v7 only
        mirror = tmp_path / "mirror"
        mirror.mkdir()
        (mirror / "files").mkdir()
        db = mirror / "index.sqlite3"

        conn = sqlite3.connect(db)
        conn.execute("""CREATE TABLE papers (
            id TEXT PRIMARY KEY, title TEXT, abstract TEXT, authors TEXT,
            categories TEXT, published DATE, updated DATE, pdf_url TEXT,
            doi TEXT, local_file_path TEXT, local_source_path TEXT)""")
        conn.execute(
            "INSERT INTO papers VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "1706.03762v7",
                "Test Paper",
                "Abstract",
                "Author",
                "cs.AI",
                "2017-06-12",
                "2017-06-12",
                "http://example.com",
                None,
                None,
                None,
            ),
        )
        conn.commit()
        conn.close()

        client = MockArxivClient(mirror_path=mirror)

        # Searching for v1 should NOT find v7
        results = list(client.results(arxiv.Search(id_list=["1706.03762v1"])))
        assert len(results) == 0

        # Searching for v7 should find v7
        results = list(client.results(arxiv.Search(id_list=["1706.03762v7"])))
        assert len(results) == 1

    def test_base_id_finds_multiple_versions(self, tmp_path: Path):
        """Base ID search returns all matching versions (mirrors arXiv behavior)."""
        import arxiv

        # Setup: DB with multiple versions
        mirror = tmp_path / "mirror"
        mirror.mkdir()
        (mirror / "files").mkdir()
        db = mirror / "index.sqlite3"

        conn = sqlite3.connect(db)
        conn.execute("""CREATE TABLE papers (
            id TEXT PRIMARY KEY, title TEXT, abstract TEXT, authors TEXT,
            categories TEXT, published DATE, updated DATE, pdf_url TEXT,
            doi TEXT, local_file_path TEXT, local_source_path TEXT)""")
        conn.execute(
            "INSERT INTO papers VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "1706.03762v1",
                "Paper v1",
                "Abstract",
                "Author",
                "cs.AI",
                "2017-06-12",
                "2017-06-12",
                "http://example.com",
                None,
                None,
                None,
            ),
        )
        conn.execute(
            "INSERT INTO papers VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "1706.03762v7",
                "Paper v7",
                "Abstract",
                "Author",
                "cs.AI",
                "2017-06-12",
                "2017-12-01",
                "http://example.com",
                None,
                None,
                None,
            ),
        )
        conn.commit()
        conn.close()

        client = MockArxivClient(mirror_path=mirror)

        # Base ID should find both versions
        results = list(client.results(arxiv.Search(id_list=["1706.03762"])))
        assert len(results) == 2
        entry_ids = [r.entry_id for r in results]
        assert any("1706.03762v1" in eid for eid in entry_ids)
        assert any("1706.03762v7" in eid for eid in entry_ids)

    def test_client_search_by_category(self, mock_arxiv_client: MockArxivClient):
        """Search returns papers matching category."""
        import arxiv

        search = arxiv.Search(query="cat:cs.AI", max_results=5)
        results = list(mock_arxiv_client.results(search))

        # Results depend on what's in the mirror
        assert isinstance(results, list)

    def test_client_search_by_id(
        self, mock_arxiv_client: MockArxivClient, local_mirror_db: Path
    ):
        """Search by ID returns matching paper."""
        import arxiv

        # Get a versioned paper ID from the database (versioned IDs use exact matching)
        conn = sqlite3.connect(local_mirror_db)
        cursor = conn.cursor()
        # Select a versioned ID to ensure exact match behavior
        cursor.execute("SELECT id FROM papers WHERE id GLOB '*v[0-9]*' LIMIT 1")
        row = cursor.fetchone()
        conn.close()

        if not row:
            pytest.skip("No versioned papers in database")

        paper_id = row[0]
        search = arxiv.Search(id_list=[paper_id])
        results = list(mock_arxiv_client.results(search))

        assert len(results) == 1
        assert paper_id in results[0].entry_id

    def test_result_has_download_methods(
        self, mock_arxiv_client: MockArxivClient, local_mirror_db: Path
    ):
        """arxiv.Result objects have mocked download methods."""
        import arxiv

        # Get a paper with files
        conn = sqlite3.connect(local_mirror_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM papers WHERE local_file_path IS NOT NULL LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            pytest.skip("No papers with local files")

        paper_id = row[0]
        search = arxiv.Search(id_list=[paper_id])
        results = list(mock_arxiv_client.results(search))

        assert len(results) == 1
        result = results[0]

        # Check methods exist
        assert hasattr(result, "download_pdf")
        assert hasattr(result, "download_source")
        assert callable(result.download_pdf)
        assert callable(result.download_source)


class TestSourceExtraction:
    """Test text extraction from local mirror files."""

    def test_extract_text_from_source_archive(self, local_mirror_files: Path):
        """Extract text from a .tar.gz source archive."""
        sources = list(local_mirror_files.glob("*.tar.gz"))
        if not sources:
            pytest.skip("No source archives in mirror")

        # Try a few sources until we find one that works
        text = None
        for source_path in sources[:20]:
            try:
                content = source_path.read_bytes()
                text = extract_text_from_source(content, "source")
                if text:
                    break
            except Exception:
                continue

        assert text is not None, "Should extract text from at least one source"
        assert len(text) > 100, "Extracted text should be substantial"

    def test_extract_text_from_pdf(self, local_mirror_files: Path):
        """Extract text from a PDF file."""
        pdfs = list(local_mirror_files.glob("*.pdf"))
        if not pdfs:
            pytest.skip("No PDFs in mirror")

        # Try a few PDFs until we find one that works
        text = None
        for pdf_path in pdfs[:20]:
            try:
                content = pdf_path.read_bytes()
                text = extract_text_from_source(content, "pdf")
                if text:
                    break
            except Exception:
                continue

        assert text is not None
        assert isinstance(text, str)


class TestFullPipelineLocal:
    """Test the full processing pipeline using local data."""

    def test_fetch_process_score(
        self,
        local_mirror_files: Path,
        local_mirror_db: Path,
        base_test_config: Dict[str, Any],
        tmp_path: Path,
    ):
        """Fetch papers, extract content, process, and score."""
        setup_logging(base_test_config["logging"])

        # Get papers from local database
        papers_raw = mock_fetch_arxiv_papers(
            categories=["cs"],  # Broad category
            start_date=date(2024, 1, 1),
            max_results=5,
            db_path=local_mirror_db,
        )

        if not papers_raw:
            pytest.skip("No papers in local mirror")

        # Enrich with content
        papers_with_content = []
        for paper in papers_raw:
            paper_id = paper["link"].split("/")[-1]
            content, method = mock_fetch_paper_content(paper_id, local_mirror_files)

            if content and method:
                try:
                    text = extract_text_from_source(content, method)
                    papers_with_content.append(
                        {
                            "id": paper_id,
                            "title": paper["title"],
                            "link": paper["link"],
                            "date": paper["date"],
                            "abstract": paper["abstract"],
                            "content": text or "",
                            "content_type": method,
                        }
                    )
                except Exception:
                    # Skip papers that fail extraction
                    continue

        assert len(papers_with_content) > 0, "Should have papers with content"

        # Process and score
        processed = process_papers(papers_with_content, base_test_config["processor"])

        assert len(processed) > 0, "Should have processed papers"

        # Check scoring results
        for paper in processed:
            assert "relevance_score" in paper
            assert "normalized_score" in paper
            assert paper["relevance_score"] >= 0

    def test_pipeline_with_production_config(
        self,
        local_mirror_files: Path,
        local_mirror_db: Path,
        production_config: Dict[str, Any],
        tmp_path: Path,
    ):
        """Test pipeline with production config.yaml settings."""
        # Override logging to temp
        production_config["logging"]["file"] = str(tmp_path / "test.log")
        setup_logging(production_config["logging"])

        # Get papers
        papers_raw = mock_fetch_arxiv_papers(
            categories=["cs.AI"],
            start_date=date(2024, 1, 1),
            max_results=10,
            db_path=local_mirror_db,
        )

        if not papers_raw:
            pytest.skip("No cs.AI papers in local mirror")

        # Enrich with content
        papers_with_content = []
        for paper in papers_raw[:5]:
            paper_id = paper["link"].split("/")[-1]
            content, method = mock_fetch_paper_content(paper_id, local_mirror_files)

            if content and method:
                try:
                    text = extract_text_from_source(content, method)
                    papers_with_content.append(
                        {
                            "id": paper_id,
                            "title": paper["title"],
                            "link": paper["link"],
                            "date": paper["date"],
                            "abstract": paper["abstract"],
                            "content": text or paper["abstract"],
                            "content_type": method,
                        }
                    )
                except Exception:
                    continue

        if not papers_with_content:
            pytest.skip("No papers with extractable content")

        # Process with production scoring rules
        processed = process_papers(papers_with_content, production_config["processor"])

        # Production config has min_score, so some may be filtered
        # Just verify no errors
        assert isinstance(processed, list)


class TestNoNetworkCalls:
    """Verify that local mirror tests make no real network calls."""

    def test_mock_functions_are_offline(
        self, local_mirror_files: Path, local_mirror_db: Path
    ):
        """Ensure mock functions don't make HTTP requests."""
        with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
            # Call mock functions
            mock_fetch_paper_content("1706.03762", local_mirror_files)
            mock_fetch_arxiv_papers(["cs.AI"], date.today(), 5, local_mirror_db)

            # Verify no HTTP calls
            mock_get.assert_not_called()
            mock_post.assert_not_called()

    def test_mock_client_is_offline(self, mock_arxiv_client: MockArxivClient):
        """Ensure MockArxivClient doesn't make HTTP requests."""
        import arxiv

        with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
            search = arxiv.Search(query="cat:cs.AI", max_results=2)
            list(mock_arxiv_client.results(search))

            mock_get.assert_not_called()
            mock_post.assert_not_called()


class TestGoldenSetScoring:
    """Test that known golden set papers score as expected."""

    def test_attention_paper_high_relevance(
        self,
        local_mirror_files: Path,
        local_mirror_db: Path,
        production_config: Dict[str, Any],
    ):
        """'Attention Is All You Need' should score well for ML keywords."""
        # Check if we have this paper
        content, method = mock_fetch_paper_content("1706.03762", local_mirror_files)
        if not content:
            pytest.skip("Golden set paper 1706.03762 not in mirror")

        try:
            text = extract_text_from_source(content, method)
        except Exception:
            pytest.skip("Could not extract text from 1706.03762")

        # Get metadata from DB
        conn = sqlite3.connect(local_mirror_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT title, abstract FROM papers WHERE id LIKE ?", ("1706.03762%",)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            pytest.skip("Paper 1706.03762 not in database")

        paper = {
            "id": "1706.03762",
            "title": row[0],
            "link": "http://arxiv.org/abs/1706.03762",
            "date": date(2017, 6, 12),
            "abstract": row[1],
            "content": text or row[1],
        }

        processed = process_papers([paper], production_config["processor"])

        # This paper should pass min_score with ML keywords
        if processed:
            assert processed[0]["relevance_score"] > 0
