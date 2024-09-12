import os
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import HTTPError

from paperweight.scraper import extract_text_from_source, fetch_arxiv_papers


@patch('paperweight.scraper.requests.get')
def test_fetch_arxiv_papers(mock_get):
    mock_response = MagicMock()
    mock_response.content = '''
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <id>http://arxiv.org/abs/2401.12345</id>
            <published>2024-01-15T00:00:00Z</published>
            <title>Test Paper 1</title>
            <summary>This is test abstract 1.</summary>
        </entry>
        <entry>
            <id>http://arxiv.org/abs/2401.67890</id>
            <published>2024-01-14T00:00:00Z</published>
            <title>Test Paper 2</title>
            <summary>This is test abstract 2.</summary>
        </entry>
    </feed>
    '''
    mock_get.return_value = mock_response

    start_date = datetime(2024, 1, 14).date()
    papers = fetch_arxiv_papers('cs.AI', start_date, max_results=2)

    assert len(papers) == 2
    assert papers[0]['title'] == 'Test Paper 1'
    assert papers[1]['title'] == 'Test Paper 2'
    assert papers[0]['date'] == datetime(2024, 1, 15).date()
    assert papers[1]['date'] == datetime(2024, 1, 14).date()

def test_extract_text_from_source():
    print("Executing test_extract_text_from_source")  # Add this line
    # Test PDF extraction
    current_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_path = os.path.join(current_dir, 'test_data', 'test.pdf')

    assert os.path.exists(pdf_path), f"Test PDF file not found at {pdf_path}"

    with open(pdf_path, 'rb') as f:
        pdf_content = f.read()
    pdf_text = extract_text_from_source(pdf_content, 'pdf')
    assert "Test PDF content" in pdf_text

    # Test LaTeX source extraction
    latex_content = b'''
    \\documentclass{article}
    \\begin{document}
    This is a test LaTeX document.
    \\end{document}
    '''
    latex_text = extract_text_from_source(latex_content, 'source')
    assert "This is a test LaTeX document." in latex_text

@patch('paperweight.scraper.requests.get')
def test_fetch_arxiv_papers_invalid_category(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Invalid field: cat"
    mock_response.raise_for_status.side_effect = HTTPError("400 Client Error: Bad Request")
    mock_get.return_value = mock_response

    with pytest.raises(ValueError, match="Invalid arXiv category: invalid_category. Please check your configuration."):
        fetch_arxiv_papers('invalid_category', date.today(), max_results=10)

@patch('paperweight.scraper.requests.get')
def test_fetch_arxiv_papers_other_http_error(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = HTTPError("500 Server Error: Internal Server Error")
    mock_get.return_value = mock_response

    with pytest.raises(HTTPError, match="500 Server Error: Internal Server Error"):
        fetch_arxiv_papers('cs.AI', date.today(), max_results=10)

@patch('paperweight.scraper.requests.get')
def test_fetch_arxiv_papers_max_results(mock_get):
    mock_response = MagicMock()
    mock_response.content = '''
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <id>http://arxiv.org/abs/2401.12345</id>
            <published>2024-01-15T00:00:00Z</published>
            <title>Test Paper 1</title>
            <summary>This is test abstract 1.</summary>
        </entry>
        <entry>
            <id>http://arxiv.org/abs/2401.67890</id>
            <published>2024-01-14T00:00:00Z</published>
            <title>Test Paper 2</title>
            <summary>This is test abstract 2.</summary>
        </entry>
        <entry>
            <id>http://arxiv.org/abs/2401.11111</id>
            <published>2024-01-13T00:00:00Z</published>
            <title>Test Paper 3</title>
            <summary>This is test abstract 3.</summary>
        </entry>
    </feed>
    '''
    mock_get.return_value = mock_response

    start_date = datetime(2024, 1, 13).date()

    # Test with max_results=2
    papers = fetch_arxiv_papers('cs.AI', start_date, max_results=2)
    assert len(papers) == 2
    assert papers[0]['title'] == 'Test Paper 1'
    assert papers[1]['title'] == 'Test Paper 2'

    # Test with max_results=None (should return all papers)
    papers = fetch_arxiv_papers('cs.AI', start_date, max_results=None)
    assert len(papers) == 3
    assert papers[2]['title'] == 'Test Paper 3'

    # Test with max_results=0 (should be treated as None and return all papers)
    papers = fetch_arxiv_papers('cs.AI', start_date, max_results=0)
    assert len(papers) == 3
    assert papers[2]['title'] == 'Test Paper 3'

    # Verify that the max_results parameter is passed correctly to the API
    calls = mock_get.call_args_list
    assert len(calls) == 3

    # Check max_results=2 call
    assert calls[0][1]['params']['max_results'] == 2
    assert 'max_results' not in calls[1][1]['params']
    assert 'max_results' not in calls[2][1]['params']

    # Verify that other parameters are correct
    for call in calls:
        assert call[1]['params']['search_query'] == 'cat:cs.AI'
        assert call[1]['params']['sortBy'] == 'submittedDate'
        assert call[1]['params']['sortOrder'] == 'descending'

def test_extract_text_from_source_invalid_type():
    with pytest.raises(ValueError, match="Invalid source type: invalid_type"):
        extract_text_from_source(b'content', 'invalid_type')
