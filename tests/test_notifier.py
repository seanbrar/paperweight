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
