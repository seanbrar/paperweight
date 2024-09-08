import logging

import requests
import yaml

from paperweight.analyzer import get_abstracts
from paperweight.logging_config import setup_logging
from paperweight.notifier import compile_and_send_notifications
from paperweight.processor import process_papers
from paperweight.scraper import get_recent_papers
from paperweight.utils import load_config


def main():
    try:
        setup_logging()
        logger = logging.getLogger(__name__)

        config = load_config()
        logger.info("Configuration loaded")

        recent_papers = get_recent_papers(days=1)
        logger.debug(f"Recent papers retrieved: {len(recent_papers)}")
        logger.debug("Sample of recent papers:")
        for paper in recent_papers[:3]:
            logger.debug(f"  - {paper['title']} ({paper['id']})")

        processed_papers = process_papers(recent_papers, config['processor'])
        logger.debug(f"Processed papers: {len(processed_papers)}")
        logger.debug(f"Papers filtered out: {len(recent_papers) - len(processed_papers)}")

        summaries = get_abstracts(processed_papers, config['analyzer'])
        for paper, summary in zip(processed_papers, summaries):
            paper['summary'] = summary if summary else paper.get('abstract', 'No summary available')

        logger.debug(f"{config['analyzer']['type'].capitalize()}s of processed papers:")
        for summary in summaries:
            logger.debug(summary)
            logger.debug("---")

        compile_and_send_notifications(processed_papers, config['notifier'])
        logger.info("Notifications compiled and sent")
    except requests.RequestException as e:
        logger.error(f"Network error occurred: {e}")
    except yaml.YAMLError as e:
        logger.error(f"Configuration error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
if __name__ == "__main__":
    main()
