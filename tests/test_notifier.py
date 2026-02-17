from datetime import date
from unittest.mock import MagicMock, patch

from paperweight.notifier import (
    compile_and_send_notifications,
    render_atom_feed,
    render_json_digest,
    render_text_digest,
    send_email_notification,
    write_output,
)


@patch('paperweight.notifier.smtplib.SMTP')
def test_send_email_notification(mock_smtp):
    mock_server = MagicMock()
    mock_smtp.return_value = mock_server

    config = {
        'email': {
            'from': 'sender@example.com',
            'to': 'recipient@example.com',
            'password': 'password123',
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587
        }
    }
    send_email_notification("Test Subject", "Test Body", config)

    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with('sender@example.com', 'password123')
    mock_server.sendmail.assert_called_once()
    mock_server.quit.assert_called_once()


@patch('paperweight.notifier.send_email_notification')
def test_compile_and_send_notifications_empty_list(mock_send_email):
    config = {
        'email': {
            'from': 'sender@example.com',
            'to': 'recipient@example.com',
            'password': 'password123',
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587
        }
    }
    compile_and_send_notifications([], config)
    mock_send_email.assert_not_called()


def test_render_text_digest_deterministic():
    papers = [
        {
            "title": "B Paper",
            "date": date(2024, 1, 2),
            "summary": "Summary B",
            "link": "http://arxiv.org/abs/2",
            "relevance_score": 2.0,
            "triage_rationale": "Matched transformer + planning",
            "authors": ["Alice", "Bob", "Carol", "Dave"],
            "keywords_matched": ["transformer"],
        },
        {
            "title": "A Paper",
            "date": date(2024, 1, 1),
            "summary": "Summary A",
            "link": "http://arxiv.org/abs/1",
            "relevance_score": 1.0,
            "triage_rationale": "Matched profile keywords",
            "authors": ["Eve"],
            "keywords_matched": ["agent"],
        },
    ]
    digest = render_text_digest(papers, sort_order="alphabetical")
    assert "1. A Paper" in digest
    assert "2. B Paper" in digest
    assert "Why: Matched profile keywords" in digest
    assert "Authors: Alice, Bob, Carol +1 more" in digest
    assert "Authors: Eve" in digest
    assert "Matched: transformer" in digest
    assert "Matched: agent" in digest


def test_render_atom_feed_contains_required_elements():
    papers = [
        {
            "title": "Test Paper",
            "date": date(2024, 1, 2),
            "summary": "Summary text",
            "link": "http://arxiv.org/abs/2401.12345",
            "relevance_score": 5.5,
            "authors": ["Alice Smith", "Bob Jones"],
            "categories": ["cs.AI", "cs.CL"],
        }
    ]
    feed = render_atom_feed(papers)
    assert "<?xml" in feed
    assert "<feed" in feed
    assert "<entry>" in feed
    assert "Test Paper" in feed
    assert "http://arxiv.org/abs/2401.12345" in feed
    assert "Alice Smith" in feed
    assert "Bob Jones" in feed
    assert 'term="cs.AI"' in feed
    assert 'term="cs.CL"' in feed


def test_write_output_to_file(tmp_path):
    target = tmp_path / "digest.txt"
    write_output("hello\n", str(target))
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_render_json_digest_contains_expected_fields():
    papers = [
        {
            "title": "Test Paper",
            "date": date(2024, 1, 2),
            "abstract": "An abstract about transformers.",
            "summary": "Summary text",
            "link": "http://arxiv.org/abs/2401.12345",
            "relevance_score": 5.5,
            "triage_score": 85.0,
            "triage_rationale": "Matched core interests",
            "id": "2401.12345",
            "authors": ["Alice Smith"],
            "categories": ["cs.AI"],
            "pdf_url": "https://arxiv.org/pdf/2401.12345",
            "keywords_matched": ["transformer"],
        }
    ]
    import json

    payload = render_json_digest(papers)
    data = json.loads(payload)
    record = data[0]
    assert record["title"] == "Test Paper"
    assert record["arxiv_id"] == "2401.12345"
    assert record["authors"] == ["Alice Smith"]
    assert record["categories"] == ["cs.AI"]
    assert record["pdf_url"] == "https://arxiv.org/pdf/2401.12345"
    assert record["keywords_matched"] == ["transformer"]
    assert record["score"] == 5.5
    assert record["triage_score"] == 85.0
    assert record["triage_rationale"] == "Matched core interests"
    # summary differs from abstract, so it should appear
    assert record["summary"] == "Summary text"
