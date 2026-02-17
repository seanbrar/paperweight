"""Module for fetching and processing arXiv papers.

This module handles all interactions with the arXiv API, including fetching paper metadata,
downloading PDFs, and extracting text content. It includes retry mechanisms for robust
API interactions and various methods for processing paper content.
"""

import gzip
import hashlib
import io
import json
import logging
import os
import tarfile
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)  # ThreadPoolExecutor still used by fetch_paper_contents
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import arxiv
import arxiv as _arxiv_module
import requests
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from paperweight.db import DatabaseConnectionError, connect_db
from paperweight.storage import get_last_successful_run_date
from paperweight.utils import (
    get_last_processed_date,
    save_last_processed_date,
    split_arxiv_id,
)

logger = logging.getLogger(__name__)


class ArxivRateLimitError(RuntimeError):
    """Raised when arXiv returns HTTP 429 (Too Many Requests).

    Provides a user-friendly error message instead of a raw stack trace.
    """

    def __init__(self, original: Exception | None = None):
        message = (
            "arXiv rate-limited our request (HTTP 429).\n"
            "  The API allows ≤1 request every 3 seconds.\n"
            "  Please wait a few minutes and try again, "
            "or reduce arxiv.max_results."
        )
        super().__init__(message)
        self.original = original


def _log_arxiv_retry(retry_state: RetryCallState) -> None:
    """Log a tenacity retry attempt for arXiv API calls."""
    wait = retry_state.next_action.sleep if retry_state.next_action else 0
    logger.warning(
        "arXiv request failed (attempt %d), retrying in %.0fs…",
        retry_state.attempt_number,
        wait,
    )


def fetch_arxiv_papers(
    categories: List[str], start_date: date, max_results: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Fetch papers from arXiv API for one or more categories.

    Categories are batched into a single API query using OR syntax
    (e.g. ``cat:cs.AI OR cat:cs.CL``) to minimize HTTP requests.

    Args:
        categories: arXiv categories to fetch (e.g., ``['cs.AI', 'cs.CL']``).
        start_date: The date from which to start fetching papers.
        max_results: Optional maximum number of results to return.

    Returns:
        List of dictionaries containing paper metadata.

    Raises:
        ArxivRateLimitError: If arXiv returns HTTP 429 after all retries.
    """
    logger.debug(
        "Fetching arXiv papers for categories %s since %s", categories, start_date
    )

    # Build a single batched query: "cat:cs.AI OR cat:cs.CL OR …"
    query = " OR ".join(f"cat:{c}" for c in categories)

    # Match page_size to max_results so we don't over-fetch
    effective_page_size = min(max_results, 100) if max_results else 100

    client = arxiv.Client(
        page_size=effective_page_size,
        delay_seconds=3.0,
        num_retries=3,
    )

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    return _fetch_with_backoff(client, search, start_date, max_results)


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=3, min=5, max=90),
    retry=retry_if_exception_type(_arxiv_module.HTTPError),
    before_sleep=_log_arxiv_retry,
    reraise=True,
)
def _fetch_with_backoff(
    client: arxiv.Client,
    search: arxiv.Search,
    start_date: date,
    max_results: Optional[int],
) -> List[Dict[str, Any]]:
    """Consume ``client.results()`` with tenacity retry on HTTP errors.

    The arxiv.py library raises ``arxiv.HTTPError`` for non-200 responses
    (including 429). This wrapper adds exponential backoff
    (5 s → 15 s → 45 s) on top of the library's own flat retry.
    """
    papers: List[Dict[str, Any]] = []

    try:
        for result in client.results(search):
            submitted_date = result.published.date()

            logger.debug("Paper '%s' submitted on %s", result.title, submitted_date)

            if submitted_date < start_date:
                logger.debug(
                    "Stopping fetch: paper date %s is before start date %s",
                    submitted_date,
                    start_date,
                )
                break

            arxiv_id, _ = split_arxiv_id(result.entry_id)
            papers.append(
                {
                    "title": result.title,
                    "link": result.entry_id,
                    "date": submitted_date,
                    "abstract": result.summary,
                    "authors": [a.name for a in result.authors],
                    "categories": list(result.categories),
                    "pdf_url": result.pdf_url,
                    "id": arxiv_id,
                }
            )

            if (
                max_results is not None
                and max_results > 0
                and len(papers) >= max_results
            ):
                break

    except _arxiv_module.HTTPError as exc:
        if getattr(exc, "status", None) == 429:
            raise ArxivRateLimitError(original=exc) from exc
        raise

    logger.info(
        "Successfully fetched %d papers for query '%s' since %s",
        len(papers),
        search.query,
        start_date,
    )
    return papers


def fetch_recent_papers(config, start_days=1):
    """Fetch papers published within the last specified number of days.

    All configured categories are combined into a single arXiv API query
    using OR syntax to minimize HTTP requests.

    Args:
        config: Application configuration dictionary.
        start_days: Number of days to look back for papers.

    Returns:
        List of dictionaries containing paper metadata.
    """
    categories = config["arxiv"]["categories"]
    max_results = config["arxiv"].get("max_results", 0)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=start_days)

    logger.info("Fetching papers from %s to %s", start_date, end_date)
    logger.info("Categories: %s (single batched query)", categories)

    papers = fetch_arxiv_papers(
        categories,
        start_date,
        max_results=max_results if max_results > 0 else None,
    )

    # Deduplicate by arXiv ID (papers can appear in multiple categories)
    seen_ids: set = set()
    unique_papers: list = []
    for paper in papers:
        paper_id = paper["link"].split("/abs/")[-1]
        if paper_id not in seen_ids:
            seen_ids.add(paper_id)
            unique_papers.append(paper)

    if max_results > 0:
        unique_papers = unique_papers[:max_results]

    logger.info(
        "Fetched %d unique papers (from %d raw)", len(unique_papers), len(papers)
    )
    return unique_papers


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(
        (requests.ConnectionError, requests.Timeout, requests.RequestException)
    ),
)
def fetch_paper_content(paper_id):
    """Fetch the content of a specific paper from arXiv.

    Args:
        paper_id: The arXiv ID of the paper to fetch.

    Returns:
        Tuple of (content, method) where method indicates the source type.

    Raises:
        requests.ConnectionError: If connection to arXiv fails.
        requests.Timeout: If the request times out.
        requests.RequestException: For other request-related errors.
    """
    logger.debug(f"Fetching content for paper ID: {paper_id}")
    source_url = f"http://export.arxiv.org/e-print/{paper_id}"
    pdf_url = f"https://export.arxiv.org/pdf/{paper_id}"

    try:
        # Try to fetch source first
        response = requests.get(source_url, timeout=30)
        response.raise_for_status()
        logger.debug(f"Successfully fetched source for paper ID: {paper_id}")
        return response.content, "source"
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch source for paper ID: {paper_id}. Error: {e}")

    try:
        # If source is not available, try PDF
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        logger.debug(f"Successfully fetched PDF for paper ID: {paper_id}")
        return response.content, "pdf"
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch PDF for paper ID: {paper_id}. Error: {e}")

    logger.error(f"Failed to fetch content for paper ID: {paper_id}")
    return None, None


def extract_text_from_pdf(pdf_content):
    """Extract text content from a PDF file.

    Args:
        pdf_content: Binary content of the PDF file.

    Returns:
        Extracted text as a string.
    """
    from pypdf import PdfReader

    pdf_file = io.BytesIO(pdf_content)
    pdf_reader = PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text


def extract_text_from_source(content, method):
    """Extract text from various source formats.

    Args:
        content: The content to extract text from.
        method: The method to use for extraction ('pdf' or 'source').

    Returns:
        Extracted text as a string.
    """
    if method not in ["pdf", "source"]:
        raise ValueError(f"Invalid source type: {method}")

    if method == "pdf":
        return extract_text_from_pdf(content)

    # Try to decompress gzip content
    try:
        decompressed = gzip.decompress(content)
    except gzip.BadGzipFile:
        # If it's not gzipped, use the original content
        decompressed = content

    # Check if it's a tar file
    if tarfile.is_tarfile(io.BytesIO(decompressed)):
        with tarfile.open(fileobj=io.BytesIO(decompressed)) as tar:
            text = ""
            for member in tar.getmembers():
                if member.isfile():
                    _, ext = os.path.splitext(member.name)
                    if ext.lower() in [".tex", ".txt", ".log"]:
                        f = tar.extractfile(member)
                        if f:
                            text += f.read().decode("utf-8", errors="ignore")
                    elif ext.lower() in [".png", ".jpg", ".jpeg"]:
                        # Optionally log the presence of image files
                        logger.debug(f"Skipping image file: {member.name}")
                    else:
                        logger.debug(f"Unhandled file type: {member.name}")
            return text
    else:
        # If it's not a tar file, assume it's a single file
        return decompressed.decode("utf-8", errors="ignore")


def fetch_paper_contents(paper_ids, max_workers=6):
    """Fetch contents for multiple papers in parallel.

    Args:
        paper_ids: List of arXiv paper IDs to fetch.
        max_workers: Maximum number of concurrent download threads.

    Returns:
        List of (paper_id, content, method) tuples, in the same order as *paper_ids*.
    """
    total_papers = len(paper_ids)
    logger.info(f"Fetching content for {total_papers} papers (workers={max_workers})")

    results: List[Any] = [None] * total_papers
    index_by_id = {pid: i for i, pid in enumerate(paper_ids)}

    def _fetch(paper_id):
        try:
            content, method = fetch_paper_content(paper_id)
            return paper_id, content, method
        except Exception as e:
            logger.error(f"Error fetching content for paper ID {paper_id}: {e}")
            return paper_id, None, None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch, pid): pid for pid in paper_ids}
        completed = 0
        for future in as_completed(futures):
            paper_id, content, method = future.result()
            results[index_by_id[paper_id]] = (paper_id, content, method)
            completed += 1
            if completed % 20 == 0:
                logger.info(f"Fetched {completed}/{total_papers} papers")

    logger.info(f"Finished fetching content for all {total_papers} papers")
    return results


def _hydrate_papers_with_content(papers, config, db_enabled):
    """Attach extracted content/artifacts to paper metadata."""
    if not papers:
        return []

    max_workers = config.get("concurrency", {}).get("content_fetch", 6)
    paper_ids = [paper["link"].split("/abs/")[-1] for paper in papers]
    contents = fetch_paper_contents(paper_ids, max_workers=max_workers)

    papers_with_content = []
    storage_base = config.get("storage", {}).get("base_dir", "data/artifacts")
    for paper, (paper_id, content, method) in zip(papers, contents):
        if content:
            logger.debug(f"Extracting text for paper ID: {paper_id}")
            text = extract_text_from_source(content, method)

            artifacts = []
            if db_enabled:
                artifacts = _store_artifacts(
                    paper_id, method, content, text, storage_base
                )

            paper_with_content = dict(paper)
            paper_with_content.update(
                {
                    "id": paper_id,
                    "content": text,
                    "content_type": method,
                    "artifacts": artifacts,
                }
            )
            papers_with_content.append(paper_with_content)

    logger.info(
        "Hydrated %s/%s papers with full content", len(papers_with_content), len(papers)
    )
    return papers_with_content


def hydrate_papers_with_content(papers, config):
    """Public helper to fetch/extract full content for an existing shortlist."""
    db_enabled = config.get("db", {}).get("enabled", False)
    return _hydrate_papers_with_content(papers, config, db_enabled)


def _int_setting(value, default, *, minimum=0):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, parsed)


def _metadata_cache_options(config):
    """Return (enabled, path, ttl_hours) from config['metadata_cache']."""
    mc = config.get("metadata_cache", {})
    enabled = mc.get("enabled", True)
    path = mc.get("path", ".paperweight_cache.json")
    ttl_hours = _int_setting(mc.get("ttl_hours"), 4, minimum=0)
    return enabled, path, ttl_hours


def _metadata_cache_key(config):
    """Build a stable key from the parameters that affect which papers are fetched."""
    cats = sorted(config.get("arxiv", {}).get("categories", []))
    max_r = config.get("arxiv", {}).get("max_results", 0)
    today = datetime.now().date().isoformat()
    raw = f"{cats}|{max_r}|{today}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _serialize_metadata_papers(papers):
    """Convert paper list to JSON-safe form (dates become ISO strings)."""
    out = []
    for p in papers:
        rec = dict(p)
        if isinstance(rec.get("date"), date):
            rec["date"] = rec["date"].isoformat()
        out.append(rec)
    return out


def _deserialize_metadata_papers(records):
    """Restore paper list from JSON-safe form."""
    out = []
    for rec in records:
        rec = dict(rec)
        if isinstance(rec.get("date"), str):
            rec["date"] = datetime.strptime(rec["date"], "%Y-%m-%d").date()
        out.append(rec)
    return out


def _load_metadata_cache(cache_path, expected_key, ttl_hours):
    """Return cached papers or None if cache is missing/stale/corrupt."""
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("key") != expected_key:
            return None
        written = datetime.fromisoformat(data["written_at"])
        if (datetime.now() - written).total_seconds() > ttl_hours * 3600:
            return None
        return _deserialize_metadata_papers(data["papers"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return None


def _write_metadata_cache(cache_path, key, papers):
    """Write paper metadata to the cache file."""
    payload = {
        "key": key,
        "written_at": datetime.now().isoformat(),
        "papers": _serialize_metadata_papers(papers),
    }
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        logger.debug("Wrote metadata cache to %s (%d papers)", cache_path, len(papers))
    except OSError as e:
        logger.warning("Could not write metadata cache: %s", e)


def get_recent_papers(config, force_refresh=False, include_content=True):  # noqa: C901
    """Get recent papers, either from cache or by fetching new ones.

    Args:
        force_refresh: If True, ignore cache and fetch new papers.
        include_content: If True, fetch and extract full paper content.

    Returns:
        List of dictionaries containing paper metadata.
    """
    db_enabled = config.get("db", {}).get("enabled", False)
    used_local_watermark = not db_enabled
    if db_enabled:
        try:
            with connect_db(config["db"]) as conn:
                last_processed_date = get_last_successful_run_date(conn)
        except Exception as e:
            raise DatabaseConnectionError(
                "Database enabled but unreachable. Check host, port, credentials, and sslmode."
            ) from e
    else:
        last_processed_date = get_last_processed_date()
    logger.info(f"Last processed date: {last_processed_date}")
    current_date = datetime.now().date()
    logger.info(f"Current date: {current_date}")

    # Metadata cache: check before computing days so same-day runs can hit cache
    cache_enabled, cache_path, cache_ttl = _metadata_cache_options(config)
    cache_key = _metadata_cache_key(config)
    recent_papers = None
    if cache_enabled and not force_refresh:
        recent_papers = _load_metadata_cache(cache_path, cache_key, cache_ttl)
        if recent_papers is not None:
            logger.info("Loaded %d papers from metadata cache", len(recent_papers))

    if recent_papers is None:
        if last_processed_date is None or force_refresh:
            # If never run before, fetch papers from the last 7 days
            days = 7
            logger.info("First run detected. Fetching papers from the last 7 days.")
        else:
            days = (current_date - last_processed_date).days
            if days == 0:
                logger.info(
                    "Already processed papers for today. No new papers to fetch."
                )
                return []
            elif days > 7:
                # If more than a week has passed, limit to 7 days to avoid overload
                days = 7
                logger.warning(
                    f"More than a week since last run. Limiting fetch to last {days} days."
                )

        logger.info(f"Fetching papers for the last {days} days")
        recent_papers = fetch_recent_papers(config, days)
        if cache_enabled:
            _write_metadata_cache(cache_path, cache_key, recent_papers)

    logger.info(f"Fetched {len(recent_papers)} recent papers")

    papers_result = recent_papers
    if include_content:
        papers_result = _hydrate_papers_with_content(recent_papers, config, db_enabled)
    else:
        papers_result = []
        for paper in recent_papers:
            paper_without_content = dict(paper)
            if "id" not in paper_without_content:
                paper_without_content["id"] = paper["link"].split("/abs/")[-1]
            paper_without_content.update(
                {
                    "content": "",
                    "content_type": None,
                    "artifacts": [],
                }
            )
            papers_result.append(paper_without_content)

    if recent_papers and used_local_watermark:
        save_last_processed_date(current_date)
        logger.info(
            "Processed fetch window (%s papers). Last processed date updated to %s",
            len(recent_papers),
            current_date,
        )
    else:
        logger.info("No new papers found.")

    logger.info(
        "Returning %s papers (%s content)",
        len(papers_result),
        "with" if include_content else "without",
    )
    return papers_result


def _store_artifacts(paper_id, method, content, text, storage_base):
    """Store paper artifacts (source and extracted text) to disk.

    Args:
        paper_id: arXiv paper identifier.
        method: Content retrieval method ('pdf' or 'source').
        content: Raw binary content of the paper.
        text: Extracted text content.
        storage_base: Base directory for artifact storage.

    Returns:
        List of artifact metadata dictionaries with type, uri, checksum, and byte_size.
    """
    arxiv_id, arxiv_version = split_arxiv_id(paper_id)
    artifacts = []
    safe_id = arxiv_id.replace("/", "_")
    paper_dir = os.path.join(storage_base, f"{safe_id}_{arxiv_version}")

    try:
        os.makedirs(paper_dir, exist_ok=True)
    except OSError as e:
        logger.error("Failed to create artifact directory %s: %s", paper_dir, e)
        return artifacts

    if content:
        raw_ext = "pdf" if method == "pdf" else "bin"
        raw_path = os.path.join(paper_dir, f"source.{raw_ext}")
        try:
            _write_bytes(raw_path, content)
            artifacts.append(
                _artifact_record(
                    "source" if method == "source" else "pdf", raw_path, content
                )
            )
        except OSError as e:
            logger.error("Failed to write source artifact %s: %s", raw_path, e)

    if text:
        text_path = os.path.join(paper_dir, "extracted.txt")
        try:
            _write_text(text_path, text)
            artifacts.append(_artifact_record("text", text_path, text.encode("utf-8")))
        except OSError as e:
            logger.error("Failed to write text artifact %s: %s", text_path, e)

    return artifacts


def _artifact_record(artifact_type, path, payload):
    """Create an artifact metadata record.

    Args:
        artifact_type: Type of artifact ('pdf', 'source', or 'text').
        path: File path where the artifact is stored.
        payload: Binary content of the artifact.

    Returns:
        Dictionary with artifact metadata (type, uri, checksum, byte_size).
    """
    checksum = hashlib.sha256(payload).hexdigest()
    return {
        "type": artifact_type,
        "uri": path,
        "checksum": checksum,
        "byte_size": len(payload),
    }


def _write_bytes(path, payload):
    """Write binary data to a file.

    Args:
        path: File path to write to.
        payload: Binary data to write.
    """
    with open(path, "wb") as handle:
        handle.write(payload)


def _write_text(path, text):
    """Write text data to a file with UTF-8 encoding.

    Args:
        path: File path to write to.
        text: Text content to write.
    """
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
