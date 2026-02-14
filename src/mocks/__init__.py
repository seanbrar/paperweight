"""Mock implementations for testing without network access."""

from src.mocks.local_client import (
    DEFAULT_DB_PATH,
    DEFAULT_FILES_DIR,
    DEFAULT_MIRROR_PATH,
    MockArxivClient,
    mock_fetch_arxiv_papers,
    mock_fetch_paper_content,
    patch_scraper_for_local_mirror,
)

__all__ = [
    "DEFAULT_DB_PATH",
    "DEFAULT_FILES_DIR",
    "DEFAULT_MIRROR_PATH",
    "MockArxivClient",
    "mock_fetch_arxiv_papers",
    "mock_fetch_paper_content",
    "patch_scraper_for_local_mirror",
]
