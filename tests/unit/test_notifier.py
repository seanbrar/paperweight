from unittest.mock import MagicMock, patch

from paperweight.notifier import compile_and_send_notifications, send_email_notification


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

@patch('paperweight.notifier.send_email_notification')
def test_compile_and_send_notifications_default_sort_order(mock_send_email):
    papers = [
        {'title': 'Paper A', 'date': '2023-01-01', 'summary': 'Summary A', 'link': 'http://a.com', 'relevance_score': 0.8},
        {'title': 'Paper B', 'date': '2023-01-02', 'summary': 'Summary B', 'link': 'http://b.com', 'relevance_score': 0.9},
        {'title': 'Paper C', 'date': '2023-01-03', 'summary': 'Summary C', 'link': 'http://c.com', 'relevance_score': 0.7},
    ]
    config = {
        'email': {
            'from': 'sender@example.com',
            'to': 'recipient@example.com',
            'password': 'password123',
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587
        }
    }

    compile_and_send_notifications(papers, config)

    mock_send_email.assert_called_once()
    _, body, _ = mock_send_email.call_args[0]

    # Check if the order of papers in the email body matches the input order
    assert body.index('Paper A') < body.index('Paper B') < body.index('Paper C')

@patch('paperweight.notifier.send_email_notification')
def test_compile_and_send_notifications_explicit_relevance_sort(mock_send_email):
    papers = [
        {'title': 'Paper A', 'date': '2023-01-01', 'summary': 'Summary A', 'link': 'http://a.com', 'relevance_score': 0.8},
        {'title': 'Paper B', 'date': '2023-01-02', 'summary': 'Summary B', 'link': 'http://b.com', 'relevance_score': 0.9},
        {'title': 'Paper C', 'date': '2023-01-03', 'summary': 'Summary C', 'link': 'http://c.com', 'relevance_score': 0.7},
    ]
    config = {
        'email': {
            'from': 'sender@example.com',
            'to': 'recipient@example.com',
            'password': 'password123',
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587,
            'sort_order': 'relevance'
        }
    }

    compile_and_send_notifications(papers, config)

    mock_send_email.assert_called_once()
    _, body, _ = mock_send_email.call_args[0]

    # Check if the order of papers in the email body matches the input order
    assert body.index('Paper A') < body.index('Paper B') < body.index('Paper C')

@patch('paperweight.notifier.send_email_notification')
def test_compile_and_send_notifications_alphabetical_sort(mock_send_email):
    papers = [
        {'title': 'Paper B', 'date': '2023-01-02', 'summary': 'Summary B', 'link': 'http://b.com', 'relevance_score': 0.9},
        {'title': 'Paper A', 'date': '2023-01-01', 'summary': 'Summary A', 'link': 'http://a.com', 'relevance_score': 0.8},
        {'title': 'Paper C', 'date': '2023-01-03', 'summary': 'Summary C', 'link': 'http://c.com', 'relevance_score': 0.7},
    ]
    config = {
        'email': {
            'from': 'sender@example.com',
            'to': 'recipient@example.com',
            'password': 'password123',
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587,
            'sort_order': 'alphabetical'
        }
    }

    compile_and_send_notifications(papers, config)

    mock_send_email.assert_called_once()
    _, body, _ = mock_send_email.call_args[0]

    # Check if the order of papers in the email body is alphabetical
    assert body.index('Paper A') < body.index('Paper B') < body.index('Paper C')

@patch('paperweight.notifier.send_email_notification')
def test_compile_and_send_notifications_publication_time_sort(mock_send_email):
    papers = [
        {'title': 'Paper B', 'date': '2023-01-02', 'summary': 'Summary B', 'link': 'http://b.com', 'relevance_score': 0.9},
        {'title': 'Paper A', 'date': '2023-01-01', 'summary': 'Summary A', 'link': 'http://a.com', 'relevance_score': 0.8},
        {'title': 'Paper C', 'date': '2023-01-03', 'summary': 'Summary C', 'link': 'http://c.com', 'relevance_score': 0.7},
    ]
    config = {
        'email': {
            'from': 'sender@example.com',
            'to': 'recipient@example.com',
            'password': 'password123',
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587,
            'sort_order': 'publication_time'
        }
    }

    compile_and_send_notifications(papers, config)

    mock_send_email.assert_called_once()
    _, body, _ = mock_send_email.call_args[0]

    # Check if the order of papers in the email body is by publication time (most recent first)
    assert body.index('Paper C') < body.index('Paper B') < body.index('Paper A')
