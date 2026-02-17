from datetime import date, datetime
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree as ET

import pytest

from paperweight.db import DatabaseConnectionError
from paperweight.scraper import (
    ArxivRateLimitError,
    _parse_rss_description,
    _parse_rss_item,
    _write_metadata_cache,
    extract_text_from_source,
    fetch_arxiv_papers,
    fetch_recent_papers,
    fetch_rss_papers,
    get_recent_papers,
    hydrate_papers_with_content,
)

# ---------------------------------------------------------------------------
# fetch_arxiv_papers — batched OR query
# ---------------------------------------------------------------------------


@patch("paperweight.scraper.arxiv.Client")
def test_fetch_arxiv_papers(MockClient):
    mock_client_instance = MockClient.return_value

    # Mock results
    result1 = MagicMock()
    result1.title = "Test Paper 1"
    result1.entry_id = "http://arxiv.org/abs/2401.12345"
    result1.published = datetime(2024, 1, 15)
    result1.summary = "This is test abstract 1."

    result2 = MagicMock()
    result2.title = "Test Paper 2"
    result2.entry_id = "http://arxiv.org/abs/2401.67890"
    result2.published = datetime(2024, 1, 14, 12, 0, 0)
    result2.summary = "This is test abstract 2."

    mock_client_instance.results.return_value = [result1, result2]

    start_date = datetime(2024, 1, 14).date()
    papers = fetch_arxiv_papers(["cs.AI"], start_date, max_results=2)

    assert len(papers) == 2
    assert papers[0]["title"] == "Test Paper 1"
    assert papers[1]["title"] == "Test Paper 2"
    assert papers[0]["date"] == datetime(2024, 1, 15).date()
    assert papers[1]["date"] == datetime(2024, 1, 14).date()


@patch("paperweight.scraper.arxiv.Client")
def test_fetch_arxiv_papers_error(MockClient):
    mock_client_instance = MockClient.return_value
    mock_client_instance.results.side_effect = Exception("General Error")

    with pytest.raises(Exception, match="General Error"):
        fetch_arxiv_papers(["cs.AI"], date.today(), max_results=10)


@patch("paperweight.scraper.arxiv.Client")
def test_fetch_arxiv_papers_max_results(MockClient):
    mock_client_instance = MockClient.return_value

    result1 = MagicMock()
    result1.title = "Test Paper 1"
    result1.entry_id = "http://arxiv.org/abs/2401.12345"
    result1.published = datetime(2024, 1, 15)
    result1.summary = "Summary 1"

    result2 = MagicMock()
    result2.title = "Test Paper 2"
    result2.entry_id = "http://arxiv.org/abs/2401.67890"
    result2.published = datetime(2024, 1, 14)
    result2.summary = "Summary 2"

    result3 = MagicMock()
    result3.title = "Test Paper 3"
    result3.entry_id = "http://arxiv.org/abs/2401.11111"
    result3.published = datetime(2024, 1, 13)
    result3.summary = "Summary 3"

    mock_client_instance.results.return_value = [result1, result2, result3]
    start_date = datetime(2024, 1, 13).date()

    # Test with max_results=2
    papers = fetch_arxiv_papers(["cs.AI"], start_date, max_results=2)
    assert len(papers) == 2
    assert papers[0]["title"] == "Test Paper 1"
    assert papers[1]["title"] == "Test Paper 2"

    # Test with max_results=None
    papers = fetch_arxiv_papers(["cs.AI"], start_date, max_results=None)
    assert len(papers) == 3
    assert papers[2]["title"] == "Test Paper 3"

    # Test with max_results=0
    papers = fetch_arxiv_papers(["cs.AI"], start_date, max_results=0)
    assert len(papers) == 3
    assert papers[2]["title"] == "Test Paper 3"


# ---------------------------------------------------------------------------
# Batched OR query construction
# ---------------------------------------------------------------------------


@patch("paperweight.scraper.arxiv.Client")
@patch("paperweight.scraper.arxiv.Search")
def test_batched_or_query_construction(MockSearch, MockClient):
    """Multiple categories are combined into a single OR query."""
    mock_client_instance = MockClient.return_value
    mock_client_instance.results.return_value = []

    fetch_arxiv_papers(["cs.AI", "cs.CL", "cs.LG"], date.today(), max_results=10)

    MockSearch.assert_called_once()
    call_kwargs = MockSearch.call_args
    assert call_kwargs[1]["query"] == "cat:cs.AI OR cat:cs.CL OR cat:cs.LG"


@patch("paperweight.scraper.arxiv.Client")
@patch("paperweight.scraper.arxiv.Search")
def test_single_category_query(MockSearch, MockClient):
    """A single category produces a simple cat: query (no OR)."""
    mock_client_instance = MockClient.return_value
    mock_client_instance.results.return_value = []

    fetch_arxiv_papers(["cs.AI"], date.today(), max_results=10)

    MockSearch.assert_called_once()
    call_kwargs = MockSearch.call_args
    assert call_kwargs[1]["query"] == "cat:cs.AI"


# ---------------------------------------------------------------------------
# page_size matching
# ---------------------------------------------------------------------------


@patch("paperweight.scraper.arxiv.Client")
def test_page_size_matches_max_results(MockClient):
    """page_size should equal max_results when max_results < 100."""
    mock_client_instance = MockClient.return_value
    mock_client_instance.results.return_value = []

    fetch_arxiv_papers(["cs.AI"], date.today(), max_results=15)

    MockClient.assert_called_once_with(
        page_size=15,
        delay_seconds=3.0,
        num_retries=3,
    )


@patch("paperweight.scraper.arxiv.Client")
def test_page_size_caps_at_100(MockClient):
    """page_size should cap at 100 even when max_results > 100."""
    mock_client_instance = MockClient.return_value
    mock_client_instance.results.return_value = []

    fetch_arxiv_papers(["cs.AI"], date.today(), max_results=200)

    MockClient.assert_called_once_with(
        page_size=100,
        delay_seconds=3.0,
        num_retries=3,
    )


@patch("paperweight.scraper.arxiv.Client")
def test_page_size_defaults_to_100_when_no_limit(MockClient):
    """page_size should be 100 when max_results is None."""
    mock_client_instance = MockClient.return_value
    mock_client_instance.results.return_value = []

    fetch_arxiv_papers(["cs.AI"], date.today(), max_results=None)

    MockClient.assert_called_once_with(
        page_size=100,
        delay_seconds=3.0,
        num_retries=3,
    )


# ---------------------------------------------------------------------------
# Single-call fetch_recent_papers
# ---------------------------------------------------------------------------


def test_fetch_recent_papers_single_api_call(monkeypatch):
    """fetch_recent_papers should call fetch_arxiv_papers exactly once (multi-day path)."""
    config = {
        "arxiv": {"categories": ["cs.AI", "cs.CL", "cs.LG"], "max_results": 10},
    }
    call_count = {"n": 0}

    def fake_fetch(categories, start_date, max_results=None):
        call_count["n"] += 1
        assert categories == ["cs.AI", "cs.CL", "cs.LG"]
        return []

    monkeypatch.setattr("paperweight.scraper.fetch_arxiv_papers", fake_fetch)
    fetch_from = __import__("paperweight.scraper", fromlist=["fetch_recent_papers"])
    fetch_from.fetch_recent_papers(config, start_days=3)
    assert call_count["n"] == 1, "Expected exactly 1 API call for batched categories"


# ---------------------------------------------------------------------------
# Rate-limit / retry
# ---------------------------------------------------------------------------


def test_rate_limit_error_friendly_message():
    """ArxivRateLimitError should have a user-friendly message."""
    err = ArxivRateLimitError()
    assert "429" in str(err)
    assert "rate-limited" in str(err).lower()
    assert "wait" in str(err).lower()


@patch("paperweight.scraper.arxiv.Client")
def test_429_raises_rate_limit_error(MockClient):
    """HTTP 429 from arXiv should raise ArxivRateLimitError, not raw HTTPError."""
    import arxiv as _arxiv

    mock_client_instance = MockClient.return_value
    http_err = _arxiv.HTTPError("http://example.com", 0, 429)
    mock_client_instance.results.side_effect = http_err

    with pytest.raises(ArxivRateLimitError, match="429"):
        fetch_arxiv_papers(["cs.AI"], date.today(), max_results=10)


# ---------------------------------------------------------------------------
# Existing tests (unchanged logic, updated signatures)
# ---------------------------------------------------------------------------


def test_extract_text_from_latex_source():
    """Extract text from LaTeX source content."""
    latex_content = b"""
    \\documentclass{article}
    \\begin{document}
    This is a test LaTeX document.
    \\end{document}
    """
    latex_text = extract_text_from_source(latex_content, "source")
    assert "This is a test LaTeX document." in latex_text


def test_extract_text_from_source_invalid_type():
    with pytest.raises(ValueError, match="Invalid source type: invalid_type"):
        extract_text_from_source(b"content", "invalid_type")


def test_get_recent_papers_db_unreachable():
    config = {
        "db": {
            "enabled": True,
            "host": "localhost",
            "port": 5432,
            "database": "paperweight",
            "user": "paperweight",
            "password": "pass",
            "sslmode": "prefer",
        }
    }
    with patch("paperweight.scraper.connect_db", side_effect=Exception("boom")):
        with pytest.raises(
            DatabaseConnectionError, match="Database enabled but unreachable"
        ):
            get_recent_papers(config)


def test_hydrate_papers_with_content(monkeypatch):
    papers = [
        {
            "title": "Test Paper",
            "link": "http://arxiv.org/abs/2401.12345",
            "date": datetime(2024, 1, 15).date(),
            "abstract": "Test abstract",
        }
    ]
    config = {"db": {"enabled": False}}

    monkeypatch.setattr(
        "paperweight.scraper.fetch_paper_contents",
        lambda _ids, max_workers=6: [("2401.12345", b"pdf-bytes", "pdf")],
    )
    monkeypatch.setattr(
        "paperweight.scraper.extract_text_from_source", lambda _content, _method: "text"
    )

    hydrated = hydrate_papers_with_content(papers, config)
    assert len(hydrated) == 1
    assert hydrated[0]["id"] == "2401.12345"
    assert hydrated[0]["content"] == "text"


def test_get_recent_papers_without_content(monkeypatch):
    config = {
        "arxiv": {"categories": ["cs.AI"], "max_results": 2},
        "db": {"enabled": False},
    }
    fake_papers = [
        {
            "title": "Test Paper",
            "link": "http://arxiv.org/abs/2401.12345",
            "date": datetime(2024, 1, 15).date(),
            "abstract": "Test abstract",
        }
    ]

    monkeypatch.setattr("paperweight.scraper.get_last_processed_date", lambda: None)
    monkeypatch.setattr("paperweight.scraper.save_last_processed_date", lambda _d: None)
    monkeypatch.setattr(
        "paperweight.scraper.fetch_recent_papers", lambda _c, _d: fake_papers
    )
    fetch_content = MagicMock()
    monkeypatch.setattr("paperweight.scraper.fetch_paper_contents", fetch_content)

    papers = get_recent_papers(config, force_refresh=True, include_content=False)
    assert len(papers) == 1
    assert papers[0]["content"] == ""
    fetch_content.assert_not_called()


def test_get_recent_papers_uses_metadata_cache(tmp_path, monkeypatch):
    """When metadata cache is enabled and fresh, skip arXiv API calls."""
    cache_path = str(tmp_path / "cache.json")
    config = {
        "arxiv": {"categories": ["cs.AI"], "max_results": 2},
        "db": {"enabled": False},
        "metadata_cache": {"enabled": True, "path": cache_path, "ttl_hours": 4},
    }
    cached_papers = [
        {
            "title": "Cached Paper",
            "link": "http://arxiv.org/abs/2401.99999",
            "date": datetime(2024, 1, 15).date(),
            "abstract": "Cached abstract",
        }
    ]

    # Pre-populate the cache
    from paperweight.scraper import _metadata_cache_key

    key = _metadata_cache_key(config)
    _write_metadata_cache(cache_path, key, cached_papers)

    monkeypatch.setattr("paperweight.scraper.get_last_processed_date", lambda: None)
    monkeypatch.setattr("paperweight.scraper.save_last_processed_date", lambda _d: None)

    fetch_called = {"called": False}

    def fake_fetch(_config, _days):
        fetch_called["called"] = True
        return []

    monkeypatch.setattr("paperweight.scraper.fetch_recent_papers", fake_fetch)
    fetch_content = MagicMock()
    monkeypatch.setattr("paperweight.scraper.fetch_paper_contents", fetch_content)

    papers = get_recent_papers(config, force_refresh=False, include_content=False)
    assert len(papers) == 1
    assert papers[0]["title"] == "Cached Paper"
    assert not fetch_called["called"]
    fetch_content.assert_not_called()


# ---------------------------------------------------------------------------
# RSS description parsing
# ---------------------------------------------------------------------------

_RSS_NS = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def test_parse_rss_description_extracts_abstract():
    desc = "<p>Abstract: This is the abstract text.</p>"
    assert _parse_rss_description(desc) == "This is the abstract text."


def test_parse_rss_description_handles_html_entities():
    desc = "Abstract: x &lt; y &amp; z"
    assert _parse_rss_description(desc) == "x < y & z"


def test_parse_rss_description_empty_input():
    assert _parse_rss_description("") == ""
    assert _parse_rss_description(None) == ""


def test_parse_rss_description_no_marker_falls_back():
    desc = "Just some text without the marker."
    assert _parse_rss_description(desc) == "Just some text without the marker."


# ---------------------------------------------------------------------------
# RSS item parsing
# ---------------------------------------------------------------------------


def _make_item_xml(
    title="Test Paper",
    link="https://arxiv.org/abs/2401.12345",
    description="Abstract: Some abstract",
    pub_date="Mon, 15 Jan 2024 00:00:00 GMT",
    creator="Author One, Author Two",
    categories=("cs.AI",),
    announce_type="new",
):
    """Build a minimal RSS <item> element for testing."""
    parts = [
        "<item>",
        f"<title>{title}</title>",
        f"<link>{link}</link>",
        f"<description>{description}</description>",
    ]
    if pub_date is not None:
        parts.append(f"<pubDate>{pub_date}</pubDate>")
    if creator is not None:
        parts.append(
            f'<dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">{creator}</dc:creator>'
        )
    for cat in categories:
        parts.append(f"<category>{cat}</category>")
    if announce_type is not None:
        parts.append(
            f'<arxiv:announce_type xmlns:arxiv="http://arxiv.org/schemas/atom">{announce_type}</arxiv:announce_type>'
        )
    parts.append("</item>")
    return ET.fromstring("".join(parts))


def test_parse_rss_item_complete():
    item = _make_item_xml()
    paper = _parse_rss_item(item, _RSS_NS)
    assert paper is not None
    assert paper["title"] == "Test Paper"
    assert paper["id"] == "2401.12345"
    assert paper["abstract"] == "Some abstract"
    assert paper["authors"] == ["Author One", "Author Two"]
    assert paper["categories"] == ["cs.AI"]
    assert paper["pdf_url"] == "https://arxiv.org/pdf/2401.12345"
    assert paper["date"] == date(2024, 1, 15)


def test_parse_rss_item_replace_returns_none():
    item = _make_item_xml(announce_type="replace")
    assert _parse_rss_item(item, _RSS_NS) is None


def test_parse_rss_item_missing_pubdate():
    item = _make_item_xml(pub_date=None)
    paper = _parse_rss_item(item, _RSS_NS)
    assert paper is not None
    assert paper["date"] == datetime.now().date()


def test_parse_rss_item_missing_creator():
    item = _make_item_xml(creator=None)
    paper = _parse_rss_item(item, _RSS_NS)
    assert paper is not None
    assert paper["authors"] == []


def test_parse_rss_item_multiple_categories():
    item = _make_item_xml(categories=("cs.AI", "cs.LG", "stat.ML"))
    paper = _parse_rss_item(item, _RSS_NS)
    assert paper["categories"] == ["cs.AI", "cs.LG", "stat.ML"]


# ---------------------------------------------------------------------------
# RSS fetch integration (mocked HTTP)
# ---------------------------------------------------------------------------


def _wrap_rss_feed(items_xml):
    """Wrap <item> XML strings in a minimal RSS feed."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:arxiv="http://arxiv.org/schemas/atom">'
        "<channel>"
        f"{''.join(items_xml)}"
        "</channel></rss>"
    )


_ITEM_A = (
    "<item><title>Paper A</title>"
    "<link>https://arxiv.org/abs/2401.00001</link>"
    "<description>Abstract: Abstract A</description>"
    "<pubDate>Mon, 15 Jan 2024 00:00:00 GMT</pubDate>"
    '<dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">Auth A</dc:creator>'
    "<category>cs.AI</category>"
    '<arxiv:announce_type xmlns:arxiv="http://arxiv.org/schemas/atom">new</arxiv:announce_type>'
    "</item>"
)

_ITEM_B = (
    "<item><title>Paper B</title>"
    "<link>https://arxiv.org/abs/2401.00002</link>"
    "<description>Abstract: Abstract B</description>"
    "<pubDate>Mon, 15 Jan 2024 00:00:00 GMT</pubDate>"
    '<dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">Auth B</dc:creator>'
    "<category>cs.CL</category>"
    '<arxiv:announce_type xmlns:arxiv="http://arxiv.org/schemas/atom">new</arxiv:announce_type>'
    "</item>"
)


@patch("paperweight.scraper._fetch_single_rss_feed")
def test_fetch_rss_single_category(mock_fetch):
    mock_fetch.return_value = _wrap_rss_feed([_ITEM_A])
    papers = fetch_rss_papers(["cs.AI"])
    assert len(papers) == 1
    assert papers[0]["title"] == "Paper A"
    assert papers[0]["id"] == "2401.00001"


@patch("paperweight.scraper._fetch_single_rss_feed")
def test_fetch_rss_deduplicates_across_categories(mock_fetch):
    """Same paper in two category feeds should appear only once."""
    mock_fetch.return_value = _wrap_rss_feed([_ITEM_A])
    papers = fetch_rss_papers(["cs.AI", "cs.LG"])
    assert len(papers) == 1


@patch("paperweight.scraper._fetch_single_rss_feed")
def test_fetch_rss_one_category_fails(mock_fetch):
    """If one category feed fails, other categories still return papers."""

    def side_effect(url):
        if "cs.AI" in url:
            raise ConnectionError("boom")
        return _wrap_rss_feed([_ITEM_B])

    mock_fetch.side_effect = side_effect
    papers = fetch_rss_papers(["cs.AI", "cs.CL"])
    assert len(papers) == 1
    assert papers[0]["title"] == "Paper B"


@patch("paperweight.scraper._fetch_single_rss_feed")
def test_fetch_rss_all_categories_fail(mock_fetch):
    """If all feeds fail, return empty list (no exception)."""
    mock_fetch.side_effect = ConnectionError("boom")
    papers = fetch_rss_papers(["cs.AI", "cs.CL"])
    assert papers == []


# ---------------------------------------------------------------------------
# Routing: fetch_recent_papers RSS vs API
# ---------------------------------------------------------------------------


@patch("paperweight.scraper.fetch_arxiv_papers")
@patch("paperweight.scraper.fetch_rss_papers")
def test_routing_daily_uses_rss(mock_rss, mock_api):
    """start_days=1 → RSS called, API not called."""
    mock_rss.return_value = [
        {
            "title": "RSS Paper",
            "link": "https://arxiv.org/abs/2401.00001",
            "date": date.today(),
            "abstract": "Abstract",
            "authors": [],
            "categories": ["cs.AI"],
            "pdf_url": "https://arxiv.org/pdf/2401.00001",
            "id": "2401.00001",
        }
    ]
    config = {"arxiv": {"categories": ["cs.AI"], "max_results": 10}}
    papers = fetch_recent_papers(config, start_days=1)
    assert len(papers) == 1
    assert papers[0]["title"] == "RSS Paper"
    mock_rss.assert_called_once_with(["cs.AI"])
    mock_api.assert_not_called()


@patch("paperweight.scraper.fetch_arxiv_papers")
@patch("paperweight.scraper.fetch_rss_papers")
def test_routing_multiday_uses_api(mock_rss, mock_api):
    """start_days=3 → API called, RSS not called."""
    mock_api.return_value = [
        {
            "title": "API Paper",
            "link": "https://arxiv.org/abs/2401.00001",
            "date": date.today(),
            "abstract": "Abstract",
            "authors": [],
            "categories": ["cs.AI"],
            "pdf_url": "https://arxiv.org/pdf/2401.00001",
            "id": "2401.00001",
        }
    ]
    config = {"arxiv": {"categories": ["cs.AI"], "max_results": 10}}
    papers = fetch_recent_papers(config, start_days=3)
    assert len(papers) == 1
    mock_rss.assert_not_called()
    mock_api.assert_called_once()


@patch("paperweight.scraper.fetch_arxiv_papers")
@patch("paperweight.scraper.fetch_rss_papers")
def test_routing_rss_fails_falls_back_to_api(mock_rss, mock_api):
    """RSS exception → falls back to API."""
    mock_rss.side_effect = Exception("RSS broken")
    mock_api.return_value = [
        {
            "title": "API Paper",
            "link": "https://arxiv.org/abs/2401.00001",
            "date": date.today(),
            "abstract": "Abstract",
            "authors": [],
            "categories": ["cs.AI"],
            "pdf_url": "https://arxiv.org/pdf/2401.00001",
            "id": "2401.00001",
        }
    ]
    config = {"arxiv": {"categories": ["cs.AI"], "max_results": 10}}
    papers = fetch_recent_papers(config, start_days=1)
    assert len(papers) == 1
    assert papers[0]["title"] == "API Paper"
    mock_api.assert_called_once()


@patch("paperweight.scraper.fetch_arxiv_papers")
@patch("paperweight.scraper.fetch_rss_papers")
def test_routing_rss_empty_falls_back_to_api(mock_rss, mock_api):
    """RSS returns empty → falls back to API."""
    mock_rss.return_value = []
    mock_api.return_value = [
        {
            "title": "API Paper",
            "link": "https://arxiv.org/abs/2401.00001",
            "date": date.today(),
            "abstract": "Abstract",
            "authors": [],
            "categories": ["cs.AI"],
            "pdf_url": "https://arxiv.org/pdf/2401.00001",
            "id": "2401.00001",
        }
    ]
    config = {"arxiv": {"categories": ["cs.AI"], "max_results": 10}}
    papers = fetch_recent_papers(config, start_days=1)
    assert len(papers) == 1
    assert papers[0]["title"] == "API Paper"
    mock_api.assert_called_once()


@patch("paperweight.scraper.fetch_arxiv_papers")
@patch("paperweight.scraper.fetch_rss_papers")
def test_routing_max_results_applied_to_rss(mock_rss, mock_api):
    """max_results cap is applied to RSS results."""
    mock_rss.return_value = [
        {
            "title": f"Paper {i}",
            "link": f"https://arxiv.org/abs/2401.{i:05d}",
            "date": date.today(),
            "abstract": "Abstract",
            "authors": [],
            "categories": ["cs.AI"],
            "pdf_url": f"https://arxiv.org/pdf/2401.{i:05d}",
            "id": f"2401.{i:05d}",
        }
        for i in range(5)
    ]
    config = {"arxiv": {"categories": ["cs.AI"], "max_results": 2}}
    papers = fetch_recent_papers(config, start_days=1)
    assert len(papers) == 2
    mock_api.assert_not_called()
