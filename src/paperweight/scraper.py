import gzip
import io
import logging
import os
import tarfile
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import requests
from pypdf import PdfReader
from requests.exceptions import HTTPError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from paperweight.utils import (
    get_last_processed_date,
    load_config,
    save_last_processed_date,
)

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout))
)
def fetch_arxiv_papers(category: str, start_date: date, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
    logger.debug(f"Fetching arXiv papers for category '{category}' since {start_date}")
    base_url = "http://export.arxiv.org/api/query?"
    query = f"cat:{category}"
    params: Dict[str, Union[str, int]] = {
        "search_query": query,
        "start": 0,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }
    if max_results is not None and max_results > 0:
        params["max_results"] = max_results

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
    except HTTPError as http_err:
        if response.status_code == 400 and "Invalid field: cat" in response.text:
            logger.error(f"Invalid arXiv category: {category}. Please check your configuration.")
            raise ValueError(f"Invalid arXiv category: {category}. Please check your configuration.") from http_err
        else:
            logger.error(f"HTTP error occurred: {http_err}")
            raise

    root = ET.fromstring(response.content)

    papers = []
    for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
        title_elem = entry.find('{http://www.w3.org/2005/Atom}title')
        link_elem = entry.find('{http://www.w3.org/2005/Atom}id')
        published_elem = entry.find('{http://www.w3.org/2005/Atom}published')
        summary_elem = entry.find('{http://www.w3.org/2005/Atom}summary')

        if title_elem is None or link_elem is None or published_elem is None or summary_elem is None:
            logger.warning("Skipping entry due to missing required elements")
            continue

        title = title_elem.text.strip() if title_elem.text else ""
        link = link_elem.text.strip() if link_elem.text else ""
        submitted = published_elem.text.strip() if published_elem.text else ""
        abstract = summary_elem.text.strip() if summary_elem.text else ""

        try:
            submitted_date = datetime.strptime(submitted, "%Y-%m-%dT%H:%M:%SZ").date()
        except ValueError:
            logger.warning(f"Invalid date format for paper: {title}")
            continue

        logger.debug(f"Paper '{title}' submitted on {submitted_date}")

        if submitted_date < start_date:
            logger.debug(f"Stopping fetch: paper date {submitted_date} is before start date {start_date}")
            break

        papers.append({
            "title": title,
            "link": link,
            "date": submitted_date,
            "abstract": abstract
        })

        if max_results is not None and max_results > 0 and len(papers) >= max_results:
            logger.debug(f"Reached max_results limit of {max_results}")
            break

    logger.info(f"Successfully fetched {len(papers)} papers for category '{category}' since {start_date}")
    return papers

def fetch_recent_papers(start_days=1):
    config = load_config()
    categories = config['arxiv']['categories']
    max_results = config['arxiv'].get('max_results', 0)  # Default to 0 if not set
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=start_days)

    logger.info(f"Fetching papers from {start_date} to {end_date}")

    all_papers = []
    processed_ids = set()

    for category in categories:
        logger.info(f"Processing category: {category}")
        try:
            papers = fetch_arxiv_papers(category, start_date, max_results=max_results if max_results > 0 else None)
            new_papers = [paper for paper in papers if paper['link'].split('/abs/')[-1] not in processed_ids]
            processed_ids.update(paper['link'].split('/abs/')[-1] for paper in new_papers)

            if max_results > 0:
                new_papers = new_papers[:max_results]

            all_papers.extend(new_papers)
            logger.debug(f"Added {len(new_papers)} new papers from category {category}")
        except ValueError as ve:
            logger.error(f"Error fetching papers for category {category}: {ve}")
            continue

    logger.info(f"Fetched a total of {len(all_papers)} papers")
    return all_papers

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout, requests.RequestException))
)
def fetch_paper_content(paper_id):
    logger.debug(f"Fetching content for paper ID: {paper_id}")
    source_url = f'http://export.arxiv.org/e-print/{paper_id}'
    pdf_url = f'https://export.arxiv.org/pdf/{paper_id}'

    try:
        # Try to fetch source first
        response = requests.get(source_url, timeout=30)
        response.raise_for_status()
        logger.debug(f"Successfully fetched source for paper ID: {paper_id}")
        return response.content, 'source'
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch source for paper ID: {paper_id}. Error: {e}")

    try:
        # If source is not available, try PDF
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        logger.debug(f"Successfully fetched PDF for paper ID: {paper_id}")
        return response.content, 'pdf'
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch PDF for paper ID: {paper_id}. Error: {e}")

    logger.error(f"Failed to fetch content for paper ID: {paper_id}")
    return None, None

def extract_text_from_pdf(pdf_content):
    pdf_file = io.BytesIO(pdf_content)
    pdf_reader = PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def extract_text_from_source(content, method):
    if method not in ['pdf', 'source']:
        raise ValueError(f"Invalid source type: {method}")

    if method == 'pdf':
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
                    if ext.lower() in ['.tex', '.txt', '.log']:
                        f = tar.extractfile(member)
                        if f:
                            text += f.read().decode('utf-8', errors='ignore')
                    elif ext.lower() in ['.png', '.jpg', '.jpeg']:
                        # Optionally log the presence of image files
                        logger.debug(f"Skipping image file: {member.name}")
                    else:
                        logger.debug(f"Unhandled file type: {member.name}")
            return text
    else:
        # If it's not a tar file, assume it's a single file
        return decompressed.decode('utf-8', errors='ignore')

def fetch_paper_contents(paper_ids):
    contents = []
    total_papers = len(paper_ids)
    logger.info(f"Fetching content for {total_papers} papers")
    for i, paper_id in enumerate(paper_ids):
        try:
            content, method = fetch_paper_content(paper_id)
            contents.append((paper_id, content, method))
        except Exception as e:
            logger.error(f"Error fetching content for paper ID {paper_id}: {e}")
            contents.append((paper_id, None, None))

        if (i + 1) % 4 == 0:
            time.sleep(1)
            logger.debug(f"Processed {i + 1}/{total_papers} papers. Waiting 1 second...")

        if (i + 1) % 20 == 0:
            logger.info(f"Processed {i + 1}/{total_papers} papers")

    logger.info(f"Finished fetching content for all {total_papers} papers")
    return contents

def get_recent_papers(force_refresh=False):
    last_processed_date = get_last_processed_date()
    logger.info(f"Last processed date: {last_processed_date}")
    current_date = datetime.now().date()
    logger.info(f"Current date: {current_date}")

    if last_processed_date is None or force_refresh:
        # If never run before, fetch papers from the last 7 days
        days = 7
        logger.info("First run detected. Fetching papers from the last 7 days.")
    else:
        days = (current_date - last_processed_date).days
        if days == 0:
            logger.info("Already processed papers for today. No new papers to fetch.")
            return []
        elif days > 7:
            # If more than a week has passed, limit to 7 days to avoid overload
            days = 7
            logger.warning(f"More than a week since last run. Limiting fetch to last {days} days.")

    logger.info(f"Fetching papers for the last {days} days")
    recent_papers = fetch_recent_papers(days)
    logger.info(f"Fetched {len(recent_papers)} recent papers")
    paper_ids = [paper['link'].split('/abs/')[-1] for paper in recent_papers]

    contents = fetch_paper_contents(paper_ids)

    papers_with_content = []
    for paper, (paper_id, content, method) in zip(recent_papers, contents):
        if content:
            logger.debug(f"Extracting text for paper ID: {paper_id}")
            text = extract_text_from_source(content, method)

            papers_with_content.append({
                "id": paper_id,
                "title": paper['title'],
                "link": paper['link'],
                "date": paper['date'],
                "abstract": paper['abstract'],
                "content": text,
                "content_type": method
            })

    if papers_with_content:
        save_last_processed_date(current_date)
        logger.info(f"Processed {len(papers_with_content)} papers. Last processed date updated to {current_date}")
    else:
        logger.info("No new papers found.")

    logger.info(f"Returning {len(papers_with_content)} papers with content")
    return papers_with_content

