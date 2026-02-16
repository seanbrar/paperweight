"""Integration tests for the paperweight pipeline.

This file tests the complete data flow through the system:
- Fetching papers from arXiv
- Processing and scoring papers
- Generating summaries
- Sending notifications
- Database storage (when enabled)

Also includes error handling tests for the main entry point.
"""

import os
import time
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests
import yaml

from paperweight.analyzer import get_abstracts
from paperweight.db import DatabaseConnectionError, connect_db, is_db_enabled
from paperweight.logging_config import setup_logging
from paperweight.main import main
from paperweight.notifier import compile_and_send_notifications
from paperweight.processor import process_papers
from paperweight.scraper import get_recent_papers
from paperweight.storage import (
    create_run,
    finish_run,
    insert_artifacts,
    insert_scores,
    insert_summaries,
    upsert_papers,
)
from paperweight.utils import get_package_version, hash_config

ROOT = Path(__file__).parent.parent
LIVE_INTEGRATION_ENV = "PAPERWEIGHT_LIVE_INTEGRATION"
MAILPIT_HOST_ENV = "PAPERWEIGHT_MAILPIT_HOST"
MAILPIT_PORT_ENV = "PAPERWEIGHT_MAILPIT_PORT"
MAILPIT_HTTP_PORT_ENV = "PAPERWEIGHT_MAILPIT_HTTP_PORT"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def integration_config(tmp_path):
    """Load and patch config for integration testing."""
    config_path = ROOT / "config.yaml"
    if not config_path.exists():
        pytest.skip("Config file not found")

    with config_path.open("r") as handle:
        config = yaml.safe_load(handle)

    # Fast, predictable test settings
    config["arxiv"]["max_results"] = 2
    config["arxiv"]["categories"] = ["cs.AI"]
    config["processor"]["min_score"] = 0
    config["analyzer"]["type"] = "abstract"
    # Route email through Mailpit to avoid real sends
    email_config = config.setdefault("notifier", {}).setdefault("email", {})
    email_config.setdefault("from", "paperweight@example.com")
    email_config.setdefault("to", "paperweight@example.com")
    email_config["smtp_server"] = os.getenv(MAILPIT_HOST_ENV, "localhost")
    email_config["smtp_port"] = int(os.getenv(MAILPIT_PORT_ENV, "1025"))
    email_config["use_tls"] = False
    email_config["use_auth"] = False
    # Use a separate log file for tests
    config["logging"]["file"] = str(tmp_path / "test_paperweight.log")

    return config


@pytest.fixture
def mock_main_dependencies(mocker):
    """Mock all external dependencies for main() tests."""
    # Mock sys.argv to prevent argparse from picking up pytest arguments
    mocker.patch('sys.argv', ['paperweight'])

    # Mock configuration and logging
    mock_load_config = mocker.patch('paperweight.main.load_config')
    mock_load_config.return_value = {
        "logging": {"level": "INFO"},
        "processor": {},
        "analyzer": {"type": "abstract"},
        "notifier": {"email": {}},
        "db": {"enabled": False},
    }
    mock_setup_logging = mocker.patch('paperweight.main.setup_logging')

    # Mock paper fetching and processing
    mock_get_recent_papers = mocker.patch('paperweight.main.get_recent_papers')
    mock_get_recent_papers.return_value = [{"id": "1234.5678", "title": "Test Paper"}]
    mock_triage_papers = mocker.patch("paperweight.main.triage_papers")
    mock_triage_papers.side_effect = lambda papers, _config: papers
    mock_hydrate_papers = mocker.patch("paperweight.main.hydrate_papers_with_content")
    mock_hydrate_papers.side_effect = lambda papers, _config: papers

    mock_process_papers = mocker.patch('paperweight.main.process_papers')
    mock_process_papers.return_value = [
        {"id": "1234.5678", "title": "Test Paper", "relevance_score": 0.8}
    ]

    mock_get_abstracts = mocker.patch('paperweight.main.get_abstracts')
    mock_get_abstracts.return_value = ["Test summary"]

    # Mock digest rendering/writing
    mock_render_text_digest = mocker.patch('paperweight.main.render_text_digest')
    mock_render_text_digest.return_value = "digest"
    mock_render_json_digest = mocker.patch('paperweight.main.render_json_digest')
    mock_render_json_digest.return_value = "[]"
    mock_write_output = mocker.patch('paperweight.main.write_output')
    mock_render_atom_feed = mocker.patch('paperweight.main.render_atom_feed')
    mock_render_atom_feed.return_value = "<feed/>"

    # Mock notifications
    mock_notifications = mocker.patch(
        'paperweight.main.compile_and_send_notifications'
    )
    mock_notifications.return_value = True

    # Mock database functions
    mock_is_db_enabled = mocker.patch('paperweight.main.is_db_enabled')
    mock_is_db_enabled.return_value = False

    # Mock logger
    mock_logger = mocker.patch('paperweight.main.logger')

    return {
        'load_config': mock_load_config,
        'setup_logging': mock_setup_logging,
        'get_recent_papers': mock_get_recent_papers,
        'triage_papers': mock_triage_papers,
        'hydrate_papers_with_content': mock_hydrate_papers,
        'process_papers': mock_process_papers,
        'get_abstracts': mock_get_abstracts,
        'render_text_digest': mock_render_text_digest,
        'render_json_digest': mock_render_json_digest,
        'write_output': mock_write_output,
        'render_atom_feed': mock_render_atom_feed,
        'notifications': mock_notifications,
        'logger': mock_logger,
        'is_db_enabled': mock_is_db_enabled,
    }


# ---------------------------------------------------------------------------
# Full Pipeline Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv(LIVE_INTEGRATION_ENV),
    reason=f"Set {LIVE_INTEGRATION_ENV}=1 to run live integration test."
)
def test_pipeline_end_to_end(integration_config):  # noqa: C901
    """Full pipeline: fetch, process, summarize, store, notify."""
    setup_logging(integration_config["logging"])

    # Mailpit config
    mailpit_host = os.getenv(MAILPIT_HOST_ENV, "localhost")
    mailpit_http_port = os.getenv(MAILPIT_HTTP_PORT_ENV, "8025")
    mailpit_url = f"http://{mailpit_host}:{mailpit_http_port}/api/v1/messages"

    # Check Mailpit before run
    try:
        resp = requests.get(mailpit_url, timeout=2)
        resp.raise_for_status()
        start_count = len(resp.json().get("messages", []))
    except Exception as e:
        pytest.skip(f"Mailpit not accessible: {e}")

    # Pipeline Steps
    db_enabled = is_db_enabled(integration_config)
    run_id = None
    run_status = "failed"
    run_notes = None

    try:
        if db_enabled:
            config_hash = hash_config(integration_config)
            pipeline_version = get_package_version()
            with connect_db(integration_config["db"]) as conn:
                run_id = create_run(conn, config_hash, pipeline_version, "pytest_integration")
                conn.commit()

        # 1. Fetch
        papers = get_recent_papers(integration_config, force_refresh=True)
        assert len(papers) > 0, "No papers fetched"

        if db_enabled:
            with connect_db(integration_config["db"]) as conn:
                paper_id_map = upsert_papers(conn, papers)
                insert_artifacts(conn, papers, paper_id_map)
                conn.commit()

        # 2. Process
        processed = process_papers(papers, integration_config["processor"])
        assert len(processed) > 0, "Processor filtered all papers"

        # 3. Summarize
        summaries = get_abstracts(processed, integration_config["analyzer"])
        for paper, summary in zip(processed, summaries):
            paper["summary"] = summary or paper.get("abstract", "")
            assert paper["summary"], "Paper summary is empty"

        if db_enabled:
            with connect_db(integration_config["db"]) as conn:
                insert_scores(conn, run_id, processed, paper_id_map)
                insert_summaries(conn, run_id, processed, paper_id_map)
                conn.commit()

        # 4. Notify
        notification_sent = compile_and_send_notifications(processed, integration_config["notifier"])
        assert notification_sent, "Notification send failed"

        # 5. Verify Email
        timeout = 10
        start_time = time.time()
        email_received = False

        while time.time() - start_time < timeout:
            try:
                resp = requests.get(mailpit_url, timeout=2)
                resp.raise_for_status()
                current_count = len(resp.json().get("messages", []))
                if current_count > start_count:
                    email_received = True
                    break
            except Exception:
                pass
            time.sleep(1)

        assert email_received, "Mailpit did not receive the notification email"

        run_status = "success"

    except Exception as e:
        run_notes = str(e)
        raise
    finally:
        if db_enabled and run_id:
            with connect_db(integration_config["db"]) as conn:
                finish_run(conn, run_id, run_status, run_notes)
                conn.commit()


@pytest.mark.integration
def test_pipeline_end_to_end_stubbed(monkeypatch, tmp_path):
    """Full pipeline with stubbed external calls."""
    config = {
        "arxiv": {"categories": ["cs.AI"], "max_results": 2},
        "processor": {
            "keywords": ["ai", "transformer"],
            "exclusion_keywords": [],
            "important_words": [],
            "title_keyword_weight": 3,
            "abstract_keyword_weight": 2,
            "content_keyword_weight": 1,
            "exclusion_keyword_penalty": 5,
            "important_words_weight": 0.5,
            "min_score": 0,
        },
        "analyzer": {"type": "abstract"},
        "notifier": {
            "email": {
                "from": "paperweight@example.com",
                "to": "paperweight@example.com",
                "smtp_server": "localhost",
                "smtp_port": 1025,
                "use_tls": False,
                "use_auth": False,
            }
        },
        "logging": {"level": "INFO", "file": str(tmp_path / "test_paperweight.log")},
        "db": {"enabled": False},
    }

    fake_papers = [
        {
            "title": "Transformer Advances",
            "link": "http://arxiv.org/abs/2401.12345",
            "date": date(2024, 1, 15),
            "abstract": "Transformer models for AI.",
        },
        {
            "title": "AI Systems at Scale",
            "link": "http://arxiv.org/abs/2401.67890",
            "date": date(2024, 1, 14),
            "abstract": "Scaling AI systems.",
        },
    ]

    def fake_fetch_recent_papers(_config, _days):
        return list(fake_papers)

    def fake_fetch_paper_contents(paper_ids, max_workers=6):
        return [(paper_id, b"stub content", "pdf") for paper_id in paper_ids]

    monkeypatch.setattr(
        "paperweight.scraper.fetch_recent_papers", fake_fetch_recent_papers
    )
    monkeypatch.setattr(
        "paperweight.scraper.fetch_paper_contents", fake_fetch_paper_contents
    )
    monkeypatch.setattr(
        "paperweight.scraper.extract_text_from_source", lambda _c, _m: "stub text"
    )
    monkeypatch.setattr("paperweight.scraper.get_last_processed_date", lambda: None)
    monkeypatch.setattr("paperweight.scraper.save_last_processed_date", lambda _d: None)

    send_email = MagicMock(return_value=True)
    monkeypatch.setattr("paperweight.notifier.send_email_notification", send_email)

    setup_logging(config["logging"])

    papers = get_recent_papers(config, force_refresh=True)
    assert len(papers) == 2

    processed = process_papers(papers, config["processor"])
    summaries = get_abstracts(processed, config["analyzer"])
    for paper, summary in zip(processed, summaries):
        paper["summary"] = summary or paper.get("abstract", "")
        assert paper["summary"]

    notification_sent = compile_and_send_notifications(processed, config["notifier"])
    assert notification_sent is True
    send_email.assert_called_once()


# ---------------------------------------------------------------------------
# Error Handling Tests (absorbed from test_main.py)
# ---------------------------------------------------------------------------

class TestMainErrorHandling:
    """Tests for error handling in the main entry point."""

    def test_config_yaml_error(self, mock_main_dependencies):
        """YAML parsing errors are logged."""
        mock_main_dependencies['load_config'].side_effect = yaml.YAMLError("Invalid YAML")

        main()
        mock_main_dependencies['logger'].error.assert_called_with(
            "Configuration error: Invalid YAML"
        )

    def test_network_error(self, mock_main_dependencies):
        """Network errors are logged."""
        mock_main_dependencies['load_config'].side_effect = requests.RequestException(
            "Connection failed"
        )

        main()
        mock_main_dependencies['logger'].error.assert_called_with(
            "Network error occurred: Connection failed"
        )

    def test_database_unreachable(self, mock_main_dependencies, mocker):
        """Database connection errors are logged."""
        mocker.patch(
            'paperweight.main.setup_and_get_papers',
            side_effect=DatabaseConnectionError("Database enabled but unreachable."),
        )

        main()
        mock_main_dependencies['logger'].error.assert_called_with(
            "Database error: Database enabled but unreachable."
        )

    def test_no_papers_found(self, mock_main_dependencies):
        """When no papers are found, notification is not called."""
        mock_main_dependencies['get_recent_papers'].return_value = []

        main()
        mock_main_dependencies['notifications'].assert_not_called()
        mock_main_dependencies['logger'].info.assert_any_call(
            "No new papers to process. Exiting."
        )

    def test_default_delivery_writes_digest(self, mock_main_dependencies):
        """Default mode renders and writes stdout digest; abstract mode skips hydration."""
        main()
        mock_main_dependencies['get_recent_papers'].assert_called_once_with(
            mock_main_dependencies['load_config'].return_value, include_content=False
        )
        mock_main_dependencies['triage_papers'].assert_called_once()
        mock_main_dependencies['process_papers'].assert_called_once()
        # Abstract mode skips content hydration entirely
        mock_main_dependencies['hydrate_papers_with_content'].assert_not_called()
        mock_main_dependencies['render_text_digest'].assert_called_once()
        mock_main_dependencies['write_output'].assert_called_once()
        mock_main_dependencies['notifications'].assert_not_called()

    def test_email_delivery_uses_notifier(self, mock_main_dependencies, monkeypatch):
        """Email mode delegates to notifier adapter."""
        monkeypatch.setattr('sys.argv', ['paperweight', '--delivery', 'email'])
        main()
        mock_main_dependencies['notifications'].assert_called_once()

    def test_json_delivery_uses_json_renderer(self, mock_main_dependencies, monkeypatch):
        """JSON mode renders JSON payload and writes output."""
        monkeypatch.setattr('sys.argv', ['paperweight', '--delivery', 'json'])
        main()
        mock_main_dependencies['render_json_digest'].assert_called_once()
        mock_main_dependencies['write_output'].assert_called_once()
