import argparse
import logging
import traceback

import requests
import yaml

from paperweight.analyzer import get_abstracts
from paperweight.logging_config import setup_logging
from paperweight.notifier import compile_and_send_notifications
from paperweight.processor import process_papers
from paperweight.scraper import get_recent_papers
from paperweight.utils import load_config

logger = logging.getLogger(__name__)

def setup_and_get_papers(force_refresh):
    config = load_config()
    setup_logging(config['logging'])
    logger.info("Configuration loaded successfully")

    if force_refresh:
        logger.info("Force refresh requested. Ignoring last processed date.")
        return get_recent_papers(force_refresh=True), config
    else:
        return get_recent_papers(), config

def process_and_summarize_papers(recent_papers, config):
    if not recent_papers:
        logger.info("No new papers to process. Exiting.")
        return None

    processed_papers = process_papers(recent_papers, config['processor'])
    logger.info(f"Processed {len(processed_papers)} papers")

    if not processed_papers:
        logger.info("No papers met the relevance criteria. Exiting.")
        return None

    summaries = get_abstracts(processed_papers, config['analyzer'])
    for paper, summary in zip(processed_papers, summaries):
        paper['summary'] = summary if summary else paper.get('abstract', 'No summary available')

    return processed_papers

def main():
    parser = argparse.ArgumentParser(description="paperweight: Fetch and process arXiv papers")
    parser.add_argument('--force-refresh', action='store_true', help='Force refresh papers regardless of last processed date')
    args = parser.parse_args()

    try:
        recent_papers, config = setup_and_get_papers(args.force_refresh)
        processed_papers = process_and_summarize_papers(recent_papers, config)

        if processed_papers:
            notification_sent = compile_and_send_notifications(processed_papers, config['notifier'])
            if notification_sent:
                logger.info("Notifications compiled and sent successfully")
            else:
                logger.warning("Failed to send notifications")
    except requests.RequestException as e:
        logger.error(f"Network error occurred: {e}")
    except yaml.YAMLError as e:
        logger.error(f"Configuration error: {e}")
    except KeyError as e:
        logger.error(f"Missing configuration key: {e}")
    except ValueError as e:
        logger.error(f"Configuration validation error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Uncaught exception in main: {e}")
        traceback.print_exc()
