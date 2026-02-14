from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from paperweight.db import DatabaseConnectionError
from paperweight.scraper import (
    extract_text_from_source,
    fetch_arxiv_papers,
    get_recent_papers,
)


@patch('paperweight.scraper.arxiv.Client')
def test_fetch_arxiv_papers(MockClient):
    mock_client_instance = MockClient.return_value

    # Mock results
    result1 = MagicMock()
    result1.title = 'Test Paper 1'
    result1.entry_id = 'http://arxiv.org/abs/2401.12345'
    result1.published = datetime(2024, 1, 15)
    result1.summary = 'This is test abstract 1.'

    result2 = MagicMock()
    result2.title = 'Test Paper 2'
    result2.entry_id = 'http://arxiv.org/abs/2401.67890'
    result2.published = datetime(2024, 1, 14, 12, 0, 0)
    result2.summary = 'This is test abstract 2.'

    mock_client_instance.results.return_value = [result1, result2]

    start_date = datetime(2024, 1, 14).date()
    papers = fetch_arxiv_papers('cs.AI', start_date, max_results=2)

    assert len(papers) == 2
    assert papers[0]['title'] == 'Test Paper 1'
    assert papers[1]['title'] == 'Test Paper 2'
    assert papers[0]['date'] == datetime(2024, 1, 15).date()
    assert papers[1]['date'] == datetime(2024, 1, 14).date()


@patch('paperweight.scraper.arxiv.Client')
def test_fetch_arxiv_papers_error(MockClient):
    mock_client_instance = MockClient.return_value
    mock_client_instance.results.side_effect = Exception("General Error")

    with pytest.raises(Exception, match="General Error"):
        fetch_arxiv_papers('cs.AI', date.today(), max_results=10)


@patch('paperweight.scraper.arxiv.Client')
def test_fetch_arxiv_papers_max_results(MockClient):
    mock_client_instance = MockClient.return_value

    result1 = MagicMock()
    result1.title = 'Test Paper 1'
    result1.entry_id = 'http://arxiv.org/abs/2401.12345'
    result1.published = datetime(2024, 1, 15)
    result1.summary = 'Summary 1'

    result2 = MagicMock()
    result2.title = 'Test Paper 2'
    result2.entry_id = 'http://arxiv.org/abs/2401.67890'
    result2.published = datetime(2024, 1, 14)
    result2.summary = 'Summary 2'

    result3 = MagicMock()
    result3.title = 'Test Paper 3'
    result3.entry_id = 'http://arxiv.org/abs/2401.11111'
    result3.published = datetime(2024, 1, 13)
    result3.summary = 'Summary 3'

    # We simulate the iterator returning these
    mock_client_instance.results.return_value = [result1, result2, result3]

    start_date = datetime(2024, 1, 13).date()

    # Test with max_results=2
    # We need to reset the mock if we want to run multiple calls in one test safely regarding return values if they were stateful iterators,
    # but here it returns a list which is iterable multiple times.

    papers = fetch_arxiv_papers('cs.AI', start_date, max_results=2)
    assert len(papers) == 2
    assert papers[0]['title'] == 'Test Paper 1'
    assert papers[1]['title'] == 'Test Paper 2'

    # Test with max_results=None
    papers = fetch_arxiv_papers('cs.AI', start_date, max_results=None)
    assert len(papers) == 3
    assert papers[2]['title'] == 'Test Paper 3'

    # Test with max_results=0
    papers = fetch_arxiv_papers('cs.AI', start_date, max_results=0)
    assert len(papers) == 3
    assert papers[2]['title'] == 'Test Paper 3'


def test_extract_text_from_latex_source():
    """Extract text from LaTeX source content."""
    latex_content = b'''
    \\documentclass{article}
    \\begin{document}
    This is a test LaTeX document.
    \\end{document}
    '''
    latex_text = extract_text_from_source(latex_content, 'source')
    assert "This is a test LaTeX document." in latex_text

def test_extract_text_from_source_invalid_type():
    with pytest.raises(ValueError, match="Invalid source type: invalid_type"):
        extract_text_from_source(b'content', 'invalid_type')

def test_get_recent_papers_db_unreachable():
    config = {
        'db': {
            'enabled': True,
            'host': 'localhost',
            'port': 5432,
            'database': 'paperweight',
            'user': 'paperweight',
            'password': 'pass',
            'sslmode': 'prefer'
        }
    }
    with patch('paperweight.scraper.connect_db', side_effect=Exception("boom")):
        with pytest.raises(DatabaseConnectionError, match="Database enabled but unreachable"):
            get_recent_papers(config)
