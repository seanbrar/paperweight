"""Main module for the paperweight application.

This module serves as the entry point for the paperweight application, coordinating
the paper fetching, processing, analysis, and notification processes. It handles
configuration loading, logging setup, and the main execution flow of the application.
"""

import argparse
import logging
import os
import sys
import traceback
from pathlib import Path

import requests
import yaml

from paperweight.analyzer import get_abstracts, triage_papers
from paperweight.db import DatabaseConnectionError, connect_db, is_db_enabled
from paperweight.logging_config import setup_logging
from paperweight.notifier import (
    compile_and_send_notifications,
    render_atom_feed,
    render_json_digest,
    render_text_digest,
    write_output,
)
from paperweight.processor import process_papers
from paperweight.progress import ProgressReporter
from paperweight.scraper import get_recent_papers, hydrate_papers_with_content
from paperweight.storage import (
    create_run,
    finish_run,
    insert_artifacts,
    insert_scores,
    insert_summaries,
    upsert_papers,
)
from paperweight.utils import get_package_version, hash_config, load_config

logger = logging.getLogger(__name__)

MINIMAL_CONFIG_TEMPLATE = """arxiv:
  categories:
    - cs.AI
    - cs.CL
  max_results: 50

triage:
  enabled: true
  llm_provider: openai
  min_score: 60
  max_selected: 25

processor:
  keywords:
    - transformer
    - reasoning
    - language model
  exclusion_keywords: []
  important_words: []
  title_keyword_weight: 3
  abstract_keyword_weight: 2
  content_keyword_weight: 1
  exclusion_keyword_penalty: 5
  important_words_weight: 0.5
  min_score: 10

analyzer:
  type: abstract
  llm_provider: openai
  max_input_tokens: 7000
  max_input_chars: 20000

metadata_cache:
  enabled: true
  path: .paperweight_cache.json
  ttl_hours: 4

concurrency:
  content_fetch: 6
  triage: 3
  summary: 3

logging:
  level: INFO
  file: paperweight.log
"""


def setup_and_get_papers(force_refresh, include_content=True, config_path="config.yaml", profile=None):
    """Set up the application and fetch papers.

    Args:
        force_refresh: Boolean indicating whether to ignore the last processed date
                      and fetch all papers within the configured time window.

    Returns:
        Tuple of (papers, config) where papers is a list of paper dictionaries and
        config is the loaded configuration dictionary.
    """
    config = load_config(config_path=config_path, profile=profile)
    setup_logging(config["logging"])
    logger.info("Configuration loaded successfully")

    if force_refresh:
        logger.info("Force refresh requested. Ignoring last processed date.")
        return (
            get_recent_papers(
                config, force_refresh=True, include_content=include_content
            ),
            config,
        )
    else:
        return get_recent_papers(config, include_content=include_content), config


def get_summary_model(config):
    """Extract the summary model identifier from configuration.

    Args:
        config: Configuration dictionary.

    Returns:
        Model identifier string or None if not configured.
    """
    analyzer_type = config.get("analyzer", {}).get("type")
    if analyzer_type == "summary":
        return config["analyzer"].get("llm_provider")
    elif analyzer_type == "abstract":
        return "abstract"
    return None


def score_papers(papers, config):
    """Score papers based on configured criteria (title + abstract keywords).

    Args:
        papers: List of paper dictionaries to score.
        config: Configuration dictionary containing processing parameters.

    Returns:
        List of scored papers above the min_score threshold, or None if empty.
    """
    if not papers:
        logger.info("No new papers to process. Exiting.")
        return None

    processed_papers = process_papers(papers, config["processor"])
    logger.info(f"Scored {len(processed_papers)} papers above threshold")

    if not processed_papers:
        logger.info("No papers met the relevance criteria. Exiting.")
        return None

    return processed_papers


def summarize_scored_papers(processed_papers, config):
    """Attach summaries to already-scored papers.

    Args:
        processed_papers: List of scored paper dictionaries.
        config: Configuration dictionary.

    Returns:
        The same list with ``summary`` field attached, or None if input is empty.
    """
    if not processed_papers:
        return None

    summary_concurrency = config.get("concurrency", {}).get("summary")
    summaries = get_abstracts(processed_papers, config["analyzer"], summary_concurrency=summary_concurrency)
    for paper, summary in zip(processed_papers, summaries):
        paper["summary"] = (
            summary if summary else paper.get("abstract", "No summary available")
        )

    return processed_papers


def process_and_summarize_papers(recent_papers, config):
    """Process and analyze papers based on configured criteria.

    Convenience wrapper that scores then summarizes in one call.
    Retained for backward compatibility.

    Args:
        recent_papers: List of paper dictionaries to process.
        config: Configuration dictionary containing processing parameters.

    Returns:
        List of processed papers with relevance scores and summaries.
    """
    scored = score_papers(recent_papers, config)
    if scored is None:
        return None
    return summarize_scored_papers(scored, config)


def _initialize_db_run(config, recent_papers):
    """Initialize a database run and persist paper metadata.

    Args:
        config: Configuration dictionary.
        recent_papers: List of paper dictionaries.

    Returns:
        Tuple of (run_id, paper_id_map) where run_id is a UUID and
        paper_id_map maps (arxiv_id, version) to database UUIDs.
    """
    config_hash = hash_config(config)
    pipeline_version = get_package_version()
    with connect_db(config["db"]) as conn:
        run_id = create_run(conn, config_hash, pipeline_version)
        paper_id_map = {}
        if recent_papers:
            paper_id_map = upsert_papers(conn, recent_papers)
            # NOTE: Artifacts are already written to disk by get_recent_papers()
            # (via scraper._store_artifacts). This call records their metadata in DB.
            insert_artifacts(conn, recent_papers, paper_id_map)
        conn.commit()
    return run_id, paper_id_map


def _persist_results(config, run_id, processed_papers, paper_id_map):
    """Persist processing results (scores and summaries) to the database.

    Args:
        config: Configuration dictionary.
        run_id: UUID of the current run.
        processed_papers: List of processed paper dictionaries.
        paper_id_map: Mapping of (arxiv_id, version) to database UUIDs.
    """
    summary_model = get_summary_model(config)
    with connect_db(config["db"]) as conn:
        insert_scores(conn, run_id, processed_papers, paper_id_map)
        insert_summaries(conn, run_id, processed_papers, paper_id_map, summary_model)
        conn.commit()


def _finalize_run(config, run_id, status, notes):
    """Mark a pipeline run as finished in the database.

    Args:
        config: Configuration dictionary.
        run_id: UUID of the run to finalize.
        status: Final status ('success' or 'failed').
        notes: Optional notes (e.g., error message).
    """
    try:
        with connect_db(config["db"], autocommit=True) as conn:
            finish_run(conn, run_id, status, notes)
    except Exception as e:
        logger.error(f"Failed to finalize run status: {e}")


def _get_error_message(error):
    """Get a human-readable error message for known exception types.

    Args:
        error: The exception that occurred.

    Returns:
        Human-readable error description string.
    """
    if isinstance(error, requests.RequestException):
        return "Network error occurred"
    if isinstance(error, yaml.YAMLError):
        return "Configuration error"
    if isinstance(error, KeyError):
        return "Missing configuration key"
    if isinstance(error, ValueError):
        return "Configuration validation error"
    if isinstance(error, DatabaseConnectionError):
        return "Database error"
    return "An unexpected error occurred"


def _handle_error(error, error_type):
    """Log an error and return its string representation.

    Args:
        error: The exception that occurred.
        error_type: Human-readable description of the error type.

    Returns:
        String representation of the error for storage.
    """
    logger.error(f"{error_type}: {error}")
    return str(error)


def _deliver_output(processed_papers, config, args):
    """Deliver processed papers via the requested adapter."""
    if args.delivery == "stdout":
        digest = render_text_digest(processed_papers, sort_order=args.sort_order)
        write_output(digest, args.output)
        return

    if args.delivery == "json":
        json_payload = render_json_digest(processed_papers, sort_order=args.sort_order)
        write_output(json_payload + "\n", args.output)
        return

    if args.delivery == "atom":
        feed_config = config.get("feed", {})
        feed_xml = render_atom_feed(
            processed_papers,
            sort_order=args.sort_order,
            feed_title=feed_config.get("title", "paperweight"),
            feed_id=feed_config.get("id", "https://github.com/seanbrar/paperweight"),
            feed_link=feed_config.get("link", "https://github.com/seanbrar/paperweight"),
        )
        write_output(feed_xml, args.output)
        return

    notifier_config = config.get("notifier")
    if not notifier_config:
        raise ValueError("Email delivery requested but notifier config is missing.")

    notification_sent = compile_and_send_notifications(processed_papers, notifier_config)
    if notification_sent:
        logger.info("Notifications compiled and sent successfully")
    else:
        logger.warning("Failed to send notifications")


def _apply_triage_and_hydrate(recent_papers, config):
    """AI triage on metadata, then fetch full content only for shortlisted papers."""
    triaged_papers = triage_papers(recent_papers, config)
    if not triaged_papers:
        logger.info("AI triage selected no papers. Exiting.")
        return []

    return hydrate_papers_with_content(triaged_papers, config)


def _add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh papers regardless of last processed date",
    )
    parser.add_argument(
        "--delivery",
        choices=["stdout", "json", "atom", "email"],
        default="stdout",
        help="Delivery target for results (default: stdout)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Optional output file path for stdout/atom delivery",
    )
    parser.add_argument(
        "--sort-order",
        choices=["relevance", "alphabetical", "publication_time"],
        default="relevance",
        help="Sort order for digest output",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=0,
        help="Optional cap on papers to process and deliver (0 = no cap)",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Activate a named profile from the config's profiles section",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress status lines on stderr",
    )


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="paperweight: Fetch, triage, and summarize arXiv papers"
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run the paperweight pipeline")
    _add_run_arguments(run_parser)

    init_parser = subparsers.add_parser("init", help="Create a minimal config file")
    init_parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to write config file (default: config.yaml)",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing config file if present",
    )

    doctor_parser = subparsers.add_parser("doctor", help="Validate local configuration")
    doctor_parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    doctor_parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero if any warnings are present",
    )
    doctor_parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Activate a named profile from the config's profiles section",
    )

    return parser


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    args_list = list(argv if argv is not None else sys.argv[1:])
    parser = _build_cli_parser()

    # Backward-compatible default: `paperweight [run-args]` == `paperweight run [run-args]`
    known_commands = {"run", "init", "doctor"}
    if args_list and args_list[0] in {"-h", "--help"}:
        return parser.parse_args(args_list)
    if args_list and args_list[0] in known_commands:
        return parser.parse_args(args_list)

    run_parser = argparse.ArgumentParser(
        description="paperweight: Fetch, triage, and summarize arXiv papers"
    )
    _add_run_arguments(run_parser)
    run_args = run_parser.parse_args(args_list)
    run_args.command = "run"
    return run_args


def _write_minimal_config(path: str, force: bool = False) -> None:
    target = Path(path)
    if target.exists() and not force:
        raise ValueError(f"Config file already exists: {target}. Use --force to overwrite.")

    base_template = Path("config-base.yaml")
    content = (
        base_template.read_text(encoding="utf-8")
        if base_template.exists()
        else MINIMAL_CONFIG_TEMPLATE
    )
    target.write_text(content, encoding="utf-8")
    print(f"Wrote config: {target}")


def _doctor(config_path: str, strict: bool = False, profile: str | None = None) -> int:
    results: list[tuple[str, str, str]] = []

    config_file = Path(config_path)
    if config_file.exists():
        results.append(("OK", "config file", str(config_file)))
    else:
        results.append(("FAIL", "config file", f"Missing: {config_file}"))
        _print_doctor(results)
        return 1

    try:
        config = load_config(config_path=config_path, profile=profile)
        results.append(("OK", "config parse", "Loaded and validated"))
    except Exception as e:
        results.append(("FAIL", "config parse", str(e)))
        _print_doctor(results)
        return 1

    active_profile = config.get("active_profile")
    if active_profile:
        results.append(("OK", "profile", active_profile))

    triage_cfg = config.get("triage", {})
    triage_enabled = triage_cfg.get("enabled", True)
    triage_provider = (
        triage_cfg.get("llm_provider")
        or config.get("analyzer", {}).get("llm_provider")
        or "openai"
    )
    triage_key = (
        triage_cfg.get("api_key")
        or config.get("analyzer", {}).get("api_key")
        or os.getenv(f"{str(triage_provider).upper()}_API_KEY")
    )

    if triage_enabled and triage_key:
        results.append(("OK", "triage auth", f"{triage_provider} key available"))
    elif triage_enabled:
        results.append(
            ("WARN", "triage auth", "No API key found; heuristic fallback will be used")
        )
    else:
        results.append(("OK", "triage", "Disabled"))

    delivery_modes = ["stdout", "atom"]
    notifier = config.get("notifier", {})
    if notifier:
        delivery_modes.append("email")
    results.append(("OK", "delivery modes", ", ".join(delivery_modes)))

    _print_doctor(results)
    has_warn = any(status == "WARN" for status, _, _ in results)
    return 1 if strict and has_warn else 0


def _print_doctor(results: list[tuple[str, str, str]]) -> None:
    print("paperweight doctor")
    print("")
    for status, check, detail in results:
        print(f"[{status}] {check}: {detail}")


def _run_pipeline(args: argparse.Namespace) -> int:  # noqa: C901
    config = None
    run_id = None
    paper_id_map = {}
    run_status = "failed"
    run_notes = None
    db_enabled = False
    had_error = False

    progress = ProgressReporter(quiet=getattr(args, "quiet", False))

    try:
        # 1. Metadata (cached by default)
        progress.phase("fetching metadata...")
        recent_papers, config = setup_and_get_papers(
            args.force_refresh,
            include_content=False,
            config_path=args.config,
            profile=getattr(args, "profile", None),
        )
        if args.max_items and args.max_items > 0 and len(recent_papers) > args.max_items:
            logger.info(
                "Applying max-items compute cap: processing first %s of %s fetched papers",
                args.max_items,
                len(recent_papers),
            )
            recent_papers = recent_papers[: args.max_items]

        categories = config.get("arxiv", {}).get("categories", [])
        progress.phase_end(
            "fetching metadata...",
            f"{len(recent_papers)} papers ({len(categories)} categories)",
        )

        # 2. Triage (title + abstract — no content needed)
        progress.phase("triaging...")
        triaged_papers = triage_papers(recent_papers, config)
        if not triaged_papers:
            logger.info("AI triage selected no papers. Exiting.")
            triaged_papers = []
        progress.phase_end("triaging...", f"{len(triaged_papers)}/{len(recent_papers)} selected")

        # 3. Score (title + abstract keywords — no content needed)
        progress.phase("scoring...")
        scored_papers = score_papers(triaged_papers, config)
        progress.phase_end(
            "scoring...",
            f"{len(scored_papers)} papers above threshold" if scored_papers else "0 papers above threshold",
        )

        # 4. Hydrate ONLY if analyzer needs full content (summary mode)
        if scored_papers and config.get("analyzer", {}).get("type") == "summary":
            progress.phase("fetching content...")
            scored_papers = hydrate_papers_with_content(scored_papers, config)
            progress.phase_end("fetching content...", f"{len(scored_papers)} hydrated")

        db_enabled = is_db_enabled(config)

        if db_enabled and scored_papers:
            run_id, paper_id_map = _initialize_db_run(config, scored_papers)

        # 5. Summarize (abstract passthrough or LLM)
        if scored_papers and config.get("analyzer", {}).get("type") == "summary":
            progress.phase("summarizing...")
        processed_papers = summarize_scored_papers(scored_papers, config)
        if scored_papers and config.get("analyzer", {}).get("type") == "summary":
            count = len(processed_papers) if processed_papers else 0
            progress.phase_end("summarizing...", f"{count}/{len(scored_papers)} done")

        if db_enabled and run_id and processed_papers:
            _persist_results(config, run_id, processed_papers, paper_id_map)

        if processed_papers:
            _deliver_output(processed_papers, config, args)

        delivered = len(processed_papers) if processed_papers else 0
        progress.phase_end("done —", f"{delivered} papers delivered to stdout")

        run_status = "success"
    except (
        requests.RequestException,
        yaml.YAMLError,
        KeyError,
        ValueError,
        DatabaseConnectionError,
    ) as e:
        had_error = True
        error_type = _get_error_message(e)
        run_notes = _handle_error(e, error_type)
    except Exception as e:
        had_error = True
        run_notes = _handle_error(e, "An unexpected error occurred")
    finally:
        if db_enabled and run_id:
            _finalize_run(config, run_id, run_status, run_notes)
    return 1 if had_error else 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = _parse_args(argv)
    if args.command is None:
        # No subcommand means default run mode.
        args.command = "run"
        args.config = getattr(args, "config", "config.yaml")
        args.force_refresh = getattr(args, "force_refresh", False)
        args.delivery = getattr(args, "delivery", "stdout")
        args.output = getattr(args, "output", None)
        args.sort_order = getattr(args, "sort_order", "relevance")
        args.max_items = getattr(args, "max_items", 0)
        args.profile = getattr(args, "profile", None)
        args.quiet = getattr(args, "quiet", False)
    if args.command == "init":
        _write_minimal_config(args.config, force=args.force)
        return 0
    if args.command == "doctor":
        return _doctor(args.config, strict=getattr(args, "strict", False), profile=getattr(args, "profile", None))
    return _run_pipeline(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Uncaught exception in main: {e}")
        traceback.print_exc()
