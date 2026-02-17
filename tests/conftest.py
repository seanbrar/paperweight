"""Shared pytest fixtures for paperweight tests."""

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from src.mocks.local_client import (
    MockArxivClient,
    patch_scraper_for_local_mirror,
)

ROOT = Path(__file__).parent.parent


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return ROOT


@pytest.fixture
def local_mirror_path() -> Path:
    """Path to the local mirror data directory.

    Skips the test if the mirror doesn't exist.
    """
    mirror_path = ROOT / "data" / "local_mirror"
    if not mirror_path.exists():
        pytest.skip("Local mirror not populated. Run scripts/populate_mirror.py first.")
    return mirror_path


@pytest.fixture
def local_mirror_db(local_mirror_path: Path) -> Path:
    """Path to the local mirror SQLite database."""
    db_path = local_mirror_path / "index.sqlite3"
    if not db_path.exists():
        pytest.skip("Local mirror database not found.")
    return db_path


@pytest.fixture
def local_mirror_files(local_mirror_path: Path) -> Path:
    """Path to the local mirror files directory."""
    files_path = local_mirror_path / "files"
    if not files_path.exists():
        pytest.skip("Local mirror files directory not found.")
    return files_path


@pytest.fixture
def mock_arxiv_client(local_mirror_path: Path) -> MockArxivClient:
    """Create a MockArxivClient using the local mirror."""
    return MockArxivClient(mirror_path=local_mirror_path)


@pytest.fixture
def patched_scraper(monkeypatch, local_mirror_files: Path):
    """Patch the scraper module to use local mirror files.

    This patches:
    - paperweight.scraper.fetch_paper_content
    - paperweight.scraper.fetch_arxiv_papers
    """
    patch_scraper_for_local_mirror(monkeypatch, local_mirror_files)


@pytest.fixture
def base_test_config(tmp_path: Path) -> Dict[str, Any]:
    """Base config for integration tests with local mirror.

    Uses minimal processing to let most papers through.
    """
    return {
        "arxiv": {
            "categories": ["cs.AI", "cs.CL", "cs.LG"],
            "max_results": 10,
        },
        "processor": {
            "keywords": [
                "machine learning",
                "neural network",
                "deep learning",
                "ai",
                "transformer",
            ],
            "exclusion_keywords": [],  # Don't exclude anything for testing
            "important_words": ["novel", "state-of-the-art"],
            "title_keyword_weight": 3,
            "abstract_keyword_weight": 2,
            "content_keyword_weight": 1,
            "exclusion_keyword_penalty": 5,
            "important_words_weight": 0.5,
            "min_score": 0,  # Accept all papers for testing
        },
        "analyzer": {
            "type": "abstract",
        },
        "notifier": {
            "email": {
                "from": "test@example.com",
                "to": "test@example.com",
                "smtp_server": "localhost",
                "smtp_port": 1025,
                "use_tls": False,
                "use_auth": False,
            }
        },
        "triage": {
            "enabled": False,
        },
        "logging": {
            "level": "DEBUG",
        },
        "db": {
            "enabled": False,
        },
        "storage": {
            "base_dir": str(tmp_path / "artifacts"),
        },
    }


@pytest.fixture
def production_config(project_root: Path) -> Dict[str, Any]:
    """Load the production config.yaml file."""
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        pytest.skip("config.yaml not found")

    with config_path.open("r") as f:
        return yaml.safe_load(f)
