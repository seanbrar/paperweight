import gzip
import io
import logging
import os
import tarfile
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Union

import requests
from pypdf import PdfReader
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from paperweight.utils import load_config

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout))
)
def fetch_arxiv_papers(category: str, start_date: date, max_results: int = 10) -> List[Dict[str, Any]]:
    base_url = "http://export.arxiv.org/api/query?"
    query = f"cat:{category}"
    params: Dict[str, Union[str, int]] = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }

    response = requests.get(base_url, params=params)
    response.raise_for_status()
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
            break

        papers.append({
            "title": title,
            "link": link,
            "date": submitted_date,
            "abstract": abstract
        })

    logger.debug(f"Fetched {len(papers)} papers for category '{category}'")
    return papers

def fetch_recent_papers(days=1, max_days=7):
    config = load_config()
    categories = config['arxiv']['categories']
    start_date = datetime.now().date() - timedelta(days=days)

    all_papers = []
    processed_ids = set()

    while days <= max_days:
        for category in categories:
            papers = fetch_arxiv_papers(category, start_date, max_results=config['arxiv']['max_results'])
            for paper in papers:
                paper_id = paper['link'].split('/abs/')[-1]
                if paper_id not in processed_ids:
                    all_papers.append(paper)
                    processed_ids.add(paper_id)

        if all_papers:
            break

        days += 1
        start_date = datetime.now().date() - timedelta(days=days)
        # Current approach to handle weekends and other non-working days
        logger.debug(f"No papers found, increasing date range to last {days} days")

    logger.debug(f"Total recent papers fetched: {len(all_papers)}")
    return all_papers

def fetch_paper_content(paper_id):
    source_url = f'http://export.arxiv.org/e-print/{paper_id}'
    pdf_url = f'https://export.arxiv.org/pdf/{paper_id}'

    # Try to fetch source first
    response = requests.get(source_url)
    if response.status_code == 200:
        return response.content, 'source'

    # If source is not available, try PDF
    response = requests.get(pdf_url)
    if response.status_code == 200:
        return response.content, 'pdf'

    return None, None

def extract_text_from_pdf(pdf_content):
    pdf_file = io.BytesIO(pdf_content)
    pdf_reader = PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def extract_text_from_source(content, method):
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
    for i, paper_id in enumerate(paper_ids):
        content, method = fetch_paper_content(paper_id)
        contents.append((paper_id, content, method))

        if (i + 1) % 4 == 0:
            time.sleep(1)
            print("Waiting 1 second...")
    return contents

def get_recent_papers(days=1):
    recent_papers = fetch_recent_papers(days)
    paper_ids = [paper['link'].split('/abs/')[-1] for paper in recent_papers]

    contents = fetch_paper_contents(paper_ids)

    papers_with_content = []
    for paper, (paper_id, content, method) in zip(recent_papers, contents):
        if content:
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

    return papers_with_content

def date_serializer(obj):
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")
