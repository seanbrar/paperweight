#!/usr/bin/env python3
"""
Populate Local arXiv Mirror
---------------------------
Downloads a representative set of papers (Metadata + PDF/Source) to `data/local_mirror`.
Features:
- "Golden Set" of manually selected papers.
- Bulk fill from target categories.
- Polite rate limiting (default: 3 seconds/request).
- Resumable (skips existing files).
- SQLite Metadata Index.
- Efficient skipping: file-first checks, batch DB lookups, reuses API results.

Usage:
    python scripts/populate_mirror.py --count 100 --dry-run
    python scripts/populate_mirror.py --categories cs.AI cs.CL --count 50
    python scripts/populate_mirror.py --max-size 50  # Skip files > 50MB
"""

import argparse
import logging
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import arxiv  # type: ignore

# Configuration
DATA_DIR = Path("data/local_mirror")
FILES_DIR = DATA_DIR / "files"
DB_PATH = DATA_DIR / "index.sqlite3"
RATE_LIMIT_DELAY = 3.0  # Seconds
DEFAULT_MAX_SIZE_MB = 100  # Default max file size in MB

# "Golden Set" - Specific papers to stress test specific config rules
GOLDEN_SET_IDS = [
    "1706.03762",  # Attention Is All You Need (High Relevance: "machine learning", "neural networks")
    "1810.04805",  # BERT (High Relevance: "NLP")
    "2303.08774",  # GPT-4 Technical Report (High Relevance: "LLM", "Artificial Intelligence")
    "1904.09456",  # Quantum ML (Target for Exclusion: "Quantum")
    "2401.00001",  # Recent random (Test Date parsing)
]

# Categories to sample from (Config + Extras for noise)
DEFAULT_CATEGORIES = [
    "cs.AI",
    "cs.CL",
    "cs.LG",
    "physics.comp-ph",  # Config commented out, good for testing exclusion
    "quant-ph",         # Quantum Physics (Test exclusion)
    "math.ST",          # Statistics (Noise)
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Populate local arXiv mirror with papers for testing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --count 100                     # Download ~100 papers across categories
  %(prog)s --dry-run                       # Show what would be downloaded
  %(prog)s --categories cs.AI cs.CL        # Only these categories
  %(prog)s --max-size 50                   # Skip sources > 50MB
  %(prog)s --count 200 --categories cs.LG  # 200 papers from cs.LG only
        """
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=50,
        help="Total number of papers to download across all categories (default: 50)"
    )
    parser.add_argument(
        "--categories", "-c",
        nargs="+",
        default=None,
        help=f"Categories to sample from (default: {', '.join(DEFAULT_CATEGORIES)})"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Show what would be downloaded without actually downloading"
    )
    parser.add_argument(
        "--max-size", "-m",
        type=float,
        default=DEFAULT_MAX_SIZE_MB,
        help=f"Maximum file size in MB to download (default: {DEFAULT_MAX_SIZE_MB}MB)"
    )
    parser.add_argument(
        "--skip-golden",
        action="store_true",
        help="Skip the golden set of manually selected papers"
    )
    return parser.parse_args()


def init_db():
    """Initialize SQLite database for metadata."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            id TEXT PRIMARY KEY,
            title TEXT,
            abstract TEXT,
            authors TEXT,
            categories TEXT,
            published DATE,
            updated DATE,
            pdf_url TEXT,
            doi TEXT,
            local_file_path TEXT,
            local_source_path TEXT
        )
    """)
    # Migration: Add local_source_path if it doesn't exist
    try:
        cursor.execute("ALTER TABLE papers ADD COLUMN local_source_path TEXT")
    except sqlite3.OperationalError:
        pass  # Column likely already exists

    conn.commit()
    return conn


def get_file_paths(paper_id: str) -> Tuple[Path, Path]:
    """Get the expected file paths for a paper's PDF and source."""
    pdf_path = FILES_DIR / f"{paper_id}.pdf"
    src_path = FILES_DIR / f"{paper_id}.tar.gz"
    return pdf_path, src_path


def check_files_complete(paper_id: str) -> Tuple[bool, bool, bool]:
    """
    Quick file-system check for paper completeness.
    Returns: (pdf_exists, src_exists, both_complete)
    """
    pdf_path, src_path = get_file_paths(paper_id)
    pdf_exists = pdf_path.exists()
    src_exists = src_path.exists()
    return pdf_exists, src_exists, (pdf_exists and src_exists)


def check_file_size(path: Path, max_size_mb: float) -> bool:
    """Check if a file exceeds the maximum size limit."""
    if not path.exists():
        return True  # Non-existent files are "ok" (will be downloaded)
    size_mb = path.stat().st_size / (1024 * 1024)
    return size_mb <= max_size_mb


def batch_check_db_status(cursor: sqlite3.Cursor, paper_ids: List[str]) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
    """
    Batch check database status for multiple papers.
    Returns dict: paper_id -> (local_file_path, local_source_path) or None if not in DB.
    """
    if not paper_ids:
        return {}

    placeholders = ",".join("?" * len(paper_ids))
    cursor.execute(
        f"SELECT id, local_file_path, local_source_path FROM papers WHERE id IN ({placeholders})",
        paper_ids
    )
    results = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
    return results


def should_skip_paper(paper_id: str, db_status: Optional[Tuple[Optional[str], Optional[str]]]) -> bool:
    """
    Determine if a paper can be completely skipped.
    Optimization: Check files FIRST (no DB/API needed if files exist).
    """
    pdf_exists, src_exists, both_complete = check_files_complete(paper_id)

    # Fast path: Both files exist on disk
    if both_complete:
        # Also verify DB has the paths recorded
        if db_status is not None:
            db_pdf, db_src = db_status
            if db_pdf and db_src:
                return True

    return False


def save_paper_metadata(conn: sqlite3.Connection, paper, paper_id: str, pdf_path: Optional[Path], src_path: Optional[Path]):
    """Save or update paper metadata in the database."""
    cursor = conn.cursor()

    final_pdf_path = str(pdf_path.absolute()) if pdf_path and pdf_path.exists() else None
    final_src_path = str(src_path.absolute()) if src_path and src_path.exists() else None

    logger.info(f"Indexing {paper_id}: {paper.title[:50]}...")
    authors = ", ".join([a.name for a in paper.authors])
    categories = ", ".join(paper.categories)

    cursor.execute("""
        INSERT OR REPLACE INTO papers
        (id, title, abstract, authors, categories, published, updated, pdf_url, doi, local_file_path, local_source_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        paper_id,
        paper.title,
        paper.summary,
        authors,
        categories,
        paper.published.isoformat(),
        paper.updated.isoformat(),
        paper.pdf_url,
        paper.doi,
        final_pdf_path,
        final_src_path
    ))
    conn.commit()


def rate_limit_sleep(context: str = ""):
    """Sleep for rate limiting with optional context logging."""
    if context:
        logger.debug(f"Rate limiting ({RATE_LIMIT_DELAY}s) after {context}")
    time.sleep(RATE_LIMIT_DELAY)


def download_paper_files(paper, paper_id: str, dry_run: bool = False, max_size_mb: float = DEFAULT_MAX_SIZE_MB) -> Tuple[Path, Path]:
    """
    Download PDF and source files for a paper if missing.
    Returns the paths (may or may not exist after download attempt).
    """
    pdf_path, src_path = get_file_paths(paper_id)
    pdf_exists, src_exists, _ = check_files_complete(paper_id)


    # Download PDF (if missing)
    if not pdf_exists:
        if dry_run:
            logger.info(f"[DRY-RUN] Would download PDF for {paper_id}")
        else:
            logger.info(f"Downloading PDF for {paper_id}...")
            try:
                paper.download_pdf(dirpath=FILES_DIR, filename=f"{paper_id}.pdf")
                rate_limit_sleep(f"PDF download for {paper_id}")
                # Check size after download
                if not check_file_size(pdf_path, max_size_mb):
                    size_mb = pdf_path.stat().st_size / (1024 * 1024)
                    logger.warning(f"PDF {paper_id}.pdf exceeds max size ({size_mb:.1f}MB > {max_size_mb}MB), removing")
                    pdf_path.unlink()
            except Exception as e:
                logger.error(f"Failed to download PDF for {paper_id}: {e}")
    else:
        logger.info(f"PDF {paper_id}.pdf exists.")

    # Download Source (if missing)
    if not src_exists:
        if dry_run:
            logger.info(f"[DRY-RUN] Would download Source for {paper_id}")
        else:
            logger.info(f"Downloading Source for {paper_id}...")
            try:
                paper.download_source(dirpath=FILES_DIR, filename=f"{paper_id}.tar.gz")
                rate_limit_sleep(f"Source download for {paper_id}")
                # Check size after download
                if not check_file_size(src_path, max_size_mb):
                    size_mb = src_path.stat().st_size / (1024 * 1024)
                    logger.warning(f"Source {paper_id}.tar.gz exceeds max size ({size_mb:.1f}MB > {max_size_mb}MB), removing")
                    src_path.unlink()
            except Exception as e:
                logger.error(f"Failed to download Source for {paper_id}: {e}")
    else:
        logger.info(f"Source {paper_id}.tar.gz exists.")

    return pdf_path, src_path


def download_paper_by_id(client: arxiv.Client, paper_id: str, conn: sqlite3.Connection,
                          db_status: Optional[Tuple[Optional[str], Optional[str]]] = None,
                          dry_run: bool = False, max_size_mb: float = DEFAULT_MAX_SIZE_MB):
    """
    Download metadata, PDF, and source for a paper by ID.
    Used for Golden Set where we only have IDs.
    """
    # Check if we can skip entirely
    if should_skip_paper(paper_id, db_status):
        logger.info(f"Skipping {paper_id} (All files present)")
        return

    if dry_run:
        logger.info(f"[DRY-RUN] Would fetch metadata for {paper_id}")
        pdf_path, src_path = get_file_paths(paper_id)
        download_paper_files(None, paper_id, dry_run=True, max_size_mb=max_size_mb)
        return

    # Must fetch metadata from API
    try:
        search = arxiv.Search(id_list=[paper_id])
        paper = next(client.results(search))
    except (StopIteration, Exception) as e:
        logger.error(f"Failed to fetch metadata for {paper_id}: {e}")
        return

    # Download files and save metadata
    pdf_path, src_path = download_paper_files(paper, paper_id, dry_run=dry_run, max_size_mb=max_size_mb)
    save_paper_metadata(conn, paper, paper_id, pdf_path, src_path)


def process_paper_with_metadata(paper, conn: sqlite3.Connection,
                                 db_status: Optional[Tuple[Optional[str], Optional[str]]] = None,
                                 dry_run: bool = False, max_size_mb: float = DEFAULT_MAX_SIZE_MB):
    """
    Process a paper when we already have the metadata (from bulk search).
    This avoids redundant API calls.
    """
    paper_id = paper.entry_id.split('/')[-1]

    # Check if we can skip entirely
    if should_skip_paper(paper_id, db_status):
        logger.info(f"Skipping {paper_id} (All files present)")
        return

    # Download files and save metadata (no API call needed - we have the paper object)
    pdf_path, src_path = download_paper_files(paper, paper_id, dry_run=dry_run, max_size_mb=max_size_mb)
    if not dry_run:
        save_paper_metadata(conn, paper, paper_id, pdf_path, src_path)
    else:
        logger.info(f"[DRY-RUN] Would index {paper_id}: {paper.title[:50]}...")


def process_golden_set(client: arxiv.Client, conn: sqlite3.Connection,
                        dry_run: bool = False, max_size_mb: float = DEFAULT_MAX_SIZE_MB):
    """Process the golden set with batch DB lookup optimization."""
    logger.info("--- Processing Golden Set ---")

    cursor = conn.cursor()

    # Batch check DB status for all golden set papers
    db_statuses = batch_check_db_status(cursor, GOLDEN_SET_IDS)

    # Quick pre-filter: count how many can be skipped without any API calls
    skippable = sum(1 for pid in GOLDEN_SET_IDS if should_skip_paper(pid, db_statuses.get(pid)))
    logger.info(f"Golden Set: {skippable}/{len(GOLDEN_SET_IDS)} papers can be skipped (files complete)")

    for pid in GOLDEN_SET_IDS:
        download_paper_by_id(client, pid, conn, db_statuses.get(pid), dry_run=dry_run, max_size_mb=max_size_mb)


def bulk_fill(client: arxiv.Client, conn: sqlite3.Connection, count: int = 20,
              categories: List[str] = None, dry_run: bool = False, max_size_mb: float = DEFAULT_MAX_SIZE_MB):
    """
    Download random papers from target categories.
    Optimized: Reuses paper metadata from search results, batch DB checks.
    """
    if categories is None:
        categories = DEFAULT_CATEGORIES

    logger.info(f"--- Processing Bulk Fill ({count} papers across {len(categories)} categories) ---")
    if dry_run:
        logger.info("[DRY-RUN MODE] No files will be downloaded")

    cursor = conn.cursor()
    papers_per_category = count // len(categories) + 5  # Slight buffer

    for category in categories:
        query = f"cat:{category}"
        logger.info(f"Searching category: {category}")

        search = arxiv.Search(
            query=query,
            max_results=papers_per_category,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )

        # Collect papers first for batch DB lookup
        papers_list = list(client.results(search))
        paper_ids = [p.entry_id.split('/')[-1] for p in papers_list]

        # Batch check DB status
        db_statuses = batch_check_db_status(cursor, paper_ids)

        # Quick pre-filter stats
        skippable = sum(1 for pid in paper_ids if should_skip_paper(pid, db_statuses.get(pid)))
        logger.info(f"Category {category}: {skippable}/{len(paper_ids)} papers can be skipped")

        # Process each paper (reusing metadata from search results)
        for paper in papers_list:
            paper_id = paper.entry_id.split('/')[-1]
            process_paper_with_metadata(paper, conn, db_statuses.get(paper_id),
                                        dry_run=dry_run, max_size_mb=max_size_mb)


def main():
    args = parse_args()

    # Display configuration
    categories = args.categories if args.categories else DEFAULT_CATEGORIES
    logger.info("=" * 60)
    logger.info("arXiv Mirror Population Script")
    logger.info("=" * 60)
    logger.info(f"  Count:      {args.count} papers")
    logger.info(f"  Categories: {', '.join(categories)}")
    logger.info(f"  Max Size:   {args.max_size} MB")
    logger.info(f"  Dry Run:    {args.dry_run}")
    logger.info(f"  Skip Golden: {args.skip_golden}")
    logger.info("=" * 60)

    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True)
    if not FILES_DIR.exists():
        FILES_DIR.mkdir(parents=True)

    conn = init_db()
    client = arxiv.Client(page_size=100, delay_seconds=RATE_LIMIT_DELAY, num_retries=3)

    if not args.skip_golden:
        process_golden_set(client, conn, dry_run=args.dry_run, max_size_mb=args.max_size)

    bulk_fill(client, conn, count=args.count, categories=categories,
              dry_run=args.dry_run, max_size_mb=args.max_size)

    conn.close()
    logger.info("Done.")

if __name__ == "__main__":
    main()
