import logging
import sys
import time
from pathlib import Path

import requests
import yaml

# Add src and scripts to sys.path
ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT / "src"))
sys.path.append(str(ROOT / "scripts"))

import export_email

from paperweight.analyzer import get_abstracts
from paperweight.db import connect_db, is_db_enabled
from paperweight.logging_config import setup_logging
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

MAILPIT_API_URL = "http://localhost:8025/api/v1/messages"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("dev_integration_test")


def load_config():
    config_path = Path("config.yaml")
    if not config_path.exists():
        logger.error("❌ Config file not found: %s", config_path)
        sys.exit(1)
    with config_path.open("r") as handle:
        return yaml.safe_load(handle)


def mailpit_message_count():
    response = requests.get(MAILPIT_API_URL, timeout=5)
    response.raise_for_status()
    data = response.json()
    return len(data.get("messages", []))


def wait_for_mailpit_message(previous_count, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            current = mailpit_message_count()
        except Exception:
            time.sleep(1)
            continue
        if current > previous_count:
            return True
        time.sleep(1)
    return False


def export_latest_email():
    try:
        latest_summary = export_email.get_latest_message()
    except SystemExit:
        return None

    if not latest_summary:
        return None

    message_id = latest_summary["ID"]
    message = export_email.get_message_content(message_id)
    markdown = export_email.format_as_markdown(message)
    return export_email.save_email(markdown, message_id)


def main():
    logger.info("🚀 Starting Paperweight Dev Integration Test...")
    config = load_config()
    setup_logging(config["logging"])

    # Fast, predictable test settings
    config["arxiv"]["max_results"] = 2
    config["arxiv"]["categories"] = ["cs.AI"]
    config["processor"]["min_score"] = 0

    db_enabled = is_db_enabled(config)
    run_id = None
    paper_id_map = {}
    run_status = "failed"
    run_notes = None

    try:
        if db_enabled:
            config_hash = hash_config(config)
            pipeline_version = get_package_version()
            with connect_db(config["db"]) as conn:
                run_id = create_run(conn, config_hash, pipeline_version, "dev_test")

        mailpit_start = mailpit_message_count()
        logger.info("📨 Mailpit messages before run: %s", mailpit_start)

        logger.info("🔍 Fetching papers (force refresh)...")
        papers = get_recent_papers(config, force_refresh=True)
        if not papers:
            logger.error("❌ No papers fetched.")
            return 1

        if db_enabled:
            with connect_db(config["db"]) as conn:
                paper_id_map = upsert_papers(conn, papers)
                insert_artifacts(conn, papers, paper_id_map)

        logger.info("🧮 Scoring papers...")
        processed = process_papers(papers, config["processor"])
        if not processed:
            logger.error("❌ Processor filtered all papers.")
            return 1

        logger.info("🧠 Summarizing papers...")
        summaries = get_abstracts(processed, config["analyzer"])
        for paper, summary in zip(processed, summaries):
            paper["summary"] = summary or paper.get("abstract", "")

        if db_enabled:
            with connect_db(config["db"]) as conn:
                insert_scores(conn, run_id, processed, paper_id_map)
                insert_summaries(conn, run_id, processed, paper_id_map)

        logger.info("📤 Sending notification email...")
        notification_sent = compile_and_send_notifications(processed, config["notifier"])
        if not notification_sent:
            logger.error("❌ Notification send failed.")
            return 1

        if not wait_for_mailpit_message(mailpit_start, timeout=12):
            logger.error("❌ Mailpit did not receive a new message in time.")
            return 1

        exported_path = export_latest_email()
        if not exported_path:
            logger.error("❌ Failed to export latest email from Mailpit.")
            return 1

        run_status = "success"
        logger.info("✅ Exported email markdown: %s", exported_path)
        logger.info("🎉 SUCCESS: End-to-end pipeline verified.")
        return 0
    except Exception as e:
        run_notes = str(e)
        logger.error("❌ Integration test failed: %s", e)
        return 1
    finally:
        if db_enabled and run_id:
            try:
                with connect_db(config["db"]) as conn:
                    finish_run(conn, run_id, run_status, run_notes)
            except Exception as e:
                logger.error("❌ Failed to finalize run status: %s", e)


if __name__ == "__main__":
    sys.exit(main())
