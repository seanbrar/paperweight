import pytest
import yaml

from paperweight.db import DatabaseConnectionError
from paperweight.main import main


@pytest.fixture
def mock_main_dependencies(mocker):
    """Mock all external dependencies for main() tests."""
    # Mock sys.argv to prevent argparse from picking up pytest arguments
    mocker.patch('sys.argv', ['paperweight'])

    # Mock configuration and logging
    mock_load_config = mocker.patch('paperweight.main.load_config')
    mock_load_config.return_value = {
        "logging": {"level": "INFO"},
        "processor": {},
        "analyzer": {"type": "abstract"},
        "notifier": {"email": {}},
        "db": {"enabled": False},
    }
    mock_setup_logging = mocker.patch('paperweight.main.setup_logging')

    # Mock paper fetching and processing
    mock_get_recent_papers = mocker.patch('paperweight.main.get_recent_papers')
    mock_get_recent_papers.return_value = [{"id": "1234.5678", "title": "Test Paper"}]

    mock_process_papers = mocker.patch('paperweight.main.process_papers')
    mock_process_papers.return_value = [
        {"id": "1234.5678", "title": "Test Paper", "relevance_score": 0.8}
    ]

    mock_get_abstracts = mocker.patch('paperweight.main.get_abstracts')
    mock_get_abstracts.return_value = ["Test summary"]

    # Mock notifications
    mock_notifications = mocker.patch(
        'paperweight.main.compile_and_send_notifications'
    )
    mock_notifications.return_value = True

    # Mock database functions
    mock_is_db_enabled = mocker.patch('paperweight.main.is_db_enabled')
    mock_is_db_enabled.return_value = False

    # Mock logger
    mock_logger = mocker.patch('paperweight.main.logger')

    return (
        mock_load_config,
        mock_setup_logging,
        mock_get_recent_papers,
        mock_process_papers,
        mock_get_abstracts,
        mock_notifications,
        mock_logger,
        mock_is_db_enabled,
    )


def test_main_function_error_handling(mock_main_dependencies):
    """Test that YAML errors are properly caught and logged."""
    mock_load_config, _, _, _, _, _, mock_logger, _ = mock_main_dependencies
    mock_load_config.side_effect = yaml.YAMLError("Invalid YAML")

    main()
    mock_logger.error.assert_called_with("Configuration error: Invalid YAML")


def test_main_function_notification_success(mock_main_dependencies):
    """Test successful notification sending."""
    (
        _,
        _,
        _,
        _,
        _,
        mock_notifications,
        mock_logger,
        _,
    ) = mock_main_dependencies
    mock_notifications.return_value = True

    main()
    mock_logger.info.assert_called_with("Notifications compiled and sent successfully")


def test_main_function_notification_failure(mock_main_dependencies):
    """Test failed notification sending."""
    (
        _,
        _,
        _,
        _,
        _,
        mock_notifications,
        mock_logger,
        _,
    ) = mock_main_dependencies
    mock_notifications.return_value = False

    main()
    mock_logger.warning.assert_called_with("Failed to send notifications")


def test_main_function_no_papers(mock_main_dependencies):
    """Test behavior when no papers are found."""
    (
        _,
        _,
        mock_get_recent_papers,
        _,
        _,
        mock_notifications,
        mock_logger,
        _,
    ) = mock_main_dependencies
    mock_get_recent_papers.return_value = []

    main()
    mock_notifications.assert_not_called()
    mock_logger.info.assert_any_call("No new papers to process. Exiting.")


def test_main_function_network_error(mock_main_dependencies):
    """Test that network errors are properly caught and logged."""
    import requests

    mock_load_config, _, _, _, _, _, mock_logger, _ = mock_main_dependencies
    mock_load_config.side_effect = requests.RequestException("Connection failed")

    main()
    mock_logger.error.assert_called_with("Network error occurred: Connection failed")


def test_main_function_missing_config_key(mock_main_dependencies):
    """Test that missing configuration keys are properly caught and logged."""
    mock_load_config, _, _, _, _, _, mock_logger, _ = mock_main_dependencies
    mock_load_config.side_effect = KeyError("missing_key")

    main()
    mock_logger.error.assert_called_with("Missing configuration key: 'missing_key'")


def test_main_function_db_unreachable(mock_main_dependencies, mocker):
    """Test that database connectivity errors are logged clearly."""
    _, _, _, _, _, _, mock_logger, _ = mock_main_dependencies
    mocker.patch(
        'paperweight.main.setup_and_get_papers',
        side_effect=DatabaseConnectionError("Database enabled but unreachable."),
    )

    main()
    mock_logger.error.assert_called_with(
        "Database error: Database enabled but unreachable."
    )
