"""paperweight — an arXiv triage CLI."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__: str = _pkg_version("academic-paperweight")
except PackageNotFoundError:
    __version__ = "unknown"

# Public API re-exports — keep the surface small and intentional.
from paperweight.main import (  # noqa: E402
    process_and_summarize_papers,
    score_papers,
    setup_and_get_papers,
    summarize_scored_papers,
)
from paperweight.scraper import ArxivRateLimitError, get_recent_papers  # noqa: E402
from paperweight.utils import load_config  # noqa: E402

__all__ = [
    "__version__",
    "ArxivRateLimitError",
    "get_recent_papers",
    "load_config",
    "process_and_summarize_papers",
    "score_papers",
    "setup_and_get_papers",
    "summarize_scored_papers",
]
