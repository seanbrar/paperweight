"""Local mock client for testing without real arXiv API calls.

This module provides mock implementations that read from data/local_mirror
to enable integration testing without network access.
"""

import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

import arxiv

# Default paths - can be overridden
DEFAULT_MIRROR_PATH = Path("data/local_mirror")
DEFAULT_DB_PATH = DEFAULT_MIRROR_PATH / "index.sqlite3"
DEFAULT_FILES_DIR = DEFAULT_MIRROR_PATH / "files"


def mock_fetch_paper_content(
    paper_id: str, files_dir: Path = DEFAULT_FILES_DIR
) -> Tuple[Optional[bytes], Optional[str]]:
    """Mock replacement for paperweight.scraper.fetch_paper_content.

    Reads content from local files instead of making HTTP requests.
    Follows the same source-first, PDF-fallback pattern as the real function.

    Args:
        paper_id: The arXiv paper ID (e.g., "2401.12345" or "2401.12345v1")
        files_dir: Directory containing the local mirror files

    Returns:
        Tuple of (content_bytes, method) where method is "source" or "pdf",
        or (None, None) if no file found.
    """
    # Normalize paper_id - strip version if present for base lookup
    base_id = paper_id.split("v")[0] if "v" in paper_id else paper_id

    # Try different ID patterns (with/without version)
    id_patterns = [paper_id]
    if paper_id != base_id:
        id_patterns.append(base_id)

    # Also try finding versioned files if we only have base ID
    if paper_id == base_id:
        # Look for any versioned file
        for f in files_dir.glob(f"{base_id}v*.tar.gz"):
            id_patterns.insert(0, f.stem.replace(".tar", ""))
            break
        for f in files_dir.glob(f"{base_id}v*.pdf"):
            if f.stem not in id_patterns:
                id_patterns.insert(0, f.stem)
            break

    # Try source first (.tar.gz), then PDF
    for pid in id_patterns:
        source_path = files_dir / f"{pid}.tar.gz"
        if source_path.exists():
            return source_path.read_bytes(), "source"

    for pid in id_patterns:
        pdf_path = files_dir / f"{pid}.pdf"
        if pdf_path.exists():
            return pdf_path.read_bytes(), "pdf"

    return None, None


def mock_fetch_arxiv_papers(
    categories: List[str],
    start_date: Any,
    max_results: Optional[int] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Mock replacement for paperweight.scraper.fetch_arxiv_papers.

    Reads paper metadata from local SQLite database instead of arXiv API.

    Args:
        categories: arXiv categories to filter by (e.g., ``['cs.AI', 'cs.CL']``)
        start_date: Not used in mock (we return all matching papers)
        max_results: Maximum number of results to return
        db_path: Path to the SQLite database

    Returns:
        List of paper dictionaries with title, link, date, abstract.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Local mirror DB not found at {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build category filter with OR logic
    cat_conditions = " OR ".join(["categories LIKE ?" for _ in categories])
    sql = f"SELECT * FROM papers WHERE ({cat_conditions})"
    params: List[Any] = [f"%{cat}%" for cat in categories]

    if max_results:
        sql += " LIMIT ?"
        params.append(int(max_results))

    cursor.execute(sql, params)
    rows = cursor.fetchall()

    papers = []
    for row in rows:
        papers.append(
            {
                "title": row["title"],
                "link": f"http://arxiv.org/abs/{row['id']}",
                "date": datetime.fromisoformat(row["published"]).date(),
                "abstract": row["abstract"],
            }
        )

    conn.close()
    return papers


def patch_scraper_for_local_mirror(monkeypatch, files_dir: Path = DEFAULT_FILES_DIR):
    """Apply all necessary patches to use local mirror instead of real API.

    Use this in pytest fixtures to mock the scraper module.

    Args:
        monkeypatch: pytest monkeypatch fixture
        files_dir: Directory containing local mirror files

    Example:
        @pytest.fixture
        def patched_scraper(monkeypatch):
            patch_scraper_for_local_mirror(monkeypatch)
    """

    def local_fetch_paper_content(paper_id):
        return mock_fetch_paper_content(paper_id, files_dir)

    monkeypatch.setattr(
        "paperweight.scraper.fetch_paper_content", local_fetch_paper_content
    )

    # Also patch the retry-decorated wrapper if needed
    monkeypatch.setattr(
        "paperweight.scraper.fetch_arxiv_papers", mock_fetch_arxiv_papers
    )


class MockArxivClient:
    """Drop-in replacement for arxiv.Client that searches a local SQLite mirror.

    This mocks the arxiv library's Client class for use in tests that need
    to work with arxiv.Search objects directly.
    """

    def __init__(
        self,
        page_size: int = 100,
        delay_seconds: float = 3,
        num_retries: int = 3,
        mirror_path: Path = DEFAULT_MIRROR_PATH,
    ):
        self.page_size = page_size
        self.delay_seconds = delay_seconds
        self.num_retries = num_retries
        self.mirror_db_path = mirror_path / "index.sqlite3"
        self.files_dir = mirror_path / "files"

        if not self.mirror_db_path.exists():
            raise FileNotFoundError(
                f"Local mirror DB not found at {self.mirror_db_path}. "
                "Run scripts/populate_mirror.py first."
            )

    def results(
        self, search: arxiv.Search, offset: int = 0
    ) -> Generator[arxiv.Result, None, None]:
        """Execute search against local SQLite database."""
        conn = sqlite3.connect(self.mirror_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query_str = getattr(search, "query", "")
        id_list = getattr(search, "id_list", [])

        sql = "SELECT * FROM papers WHERE 1=1"
        params: List[Any] = []

        if id_list:
            conditions = []
            for paper_id in id_list:
                if re.search(r"v\d+$", paper_id):
                    conditions.append("id = ?")
                    params.append(paper_id)
                else:
                    conditions.append("id LIKE ?")
                    params.append(f"{paper_id}%")
            sql += " AND (" + " OR ".join(conditions) + ")"
        elif query_str:
            terms = query_str.split()
            for term in terms:
                if term.startswith("cat:"):
                    cat = term.split(":", 1)[1]
                    sql += " AND categories LIKE ?"
                    params.append(f"%{cat}%")
                else:
                    sql += " AND (title LIKE ? OR abstract LIKE ?)"
                    params.append(f"%{term}%")
                    params.append(f"%{term}%")

        max_results = getattr(search, "max_results", None)
        if max_results:
            sql += " LIMIT ?"
            params.append(int(max_results))

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        for row in rows:
            yield self._row_to_result(row)

        conn.close()

    def _row_to_result(self, row: sqlite3.Row) -> arxiv.Result:
        """Convert a SQLite row to an arxiv.Result object."""

        class Author:
            def __init__(self, name: str):
                self.name = name

        authors = [Author(n.strip()) for n in row["authors"].split(",")]
        paper_id = row["id"]

        res = arxiv.Result(
            entry_id=f"http://arxiv.org/abs/{paper_id}",
            updated=datetime.fromisoformat(row["updated"]),
            published=datetime.fromisoformat(row["published"]),
            title=row["title"],
            authors=authors,
            summary=row["abstract"],
            comment=None,
            journal_ref=None,
            doi=row["doi"],
            primary_category=row["categories"].split(",")[0].strip(),
            categories=[cat.strip() for cat in row["categories"].split(",")],
            links=[],
        )

        # Monkey-patch download methods to use local files
        local_pdf_path = row["local_file_path"]
        local_source_path = row["local_source_path"]

        def mock_download_pdf(dirpath: str = "./", filename: str = "") -> str:
            if not filename:
                filename = f"{paper_id}.pdf"
            target_path = Path(dirpath) / filename

            if local_pdf_path and Path(local_pdf_path).exists():
                shutil.copy(local_pdf_path, target_path)
                return str(target_path)
            raise FileNotFoundError(f"Mock PDF file missing for {paper_id}")

        def mock_download_source(dirpath: str = "./", filename: str = "") -> str:
            if not filename:
                filename = f"{paper_id}.tar.gz"
            target_path = Path(dirpath) / filename

            if local_source_path and Path(local_source_path).exists():
                shutil.copy(local_source_path, target_path)
                return str(target_path)
            raise FileNotFoundError(f"Mock source file missing for {paper_id}")

        res.download_pdf = mock_download_pdf  # type: ignore
        res.download_source = mock_download_source  # type: ignore
        res.pdf_url = row["pdf_url"]

        return res
