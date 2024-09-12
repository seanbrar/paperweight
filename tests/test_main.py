import pytest
import yaml

from paperweight.main import main


@pytest.fixture
def mock_main_dependencies(mocker):
    return (
        mocker.patch('paperweight.main.load_config'),
        mocker.patch('paperweight.main.setup_logging'),
        mocker.patch('paperweight.main.get_recent_papers'),
        mocker.patch('paperweight.main.process_papers'),
        mocker.patch('paperweight.main.get_abstracts'),
        mocker.patch('paperweight.main.compile_and_send_notifications'),
        mocker.patch('paperweight.main.logger')
    )

def test_main_function_error_handling(mock_main_dependencies):
    mock_load_config, _, _, _, _, _, mock_logger = mock_main_dependencies
    mock_load_config.side_effect = yaml.YAMLError("Invalid YAML")

    main()
    mock_logger.error.assert_called_with("Configuration error: Invalid YAML")

def test_main_function_notification_success(mock_main_dependencies):
    _, _, _, _, _, mock_notifications, mock_logger = mock_main_dependencies
    mock_notifications.return_value = True

    main()
    mock_logger.info.assert_called_with("Notifications compiled and sent successfully")

def test_main_function_notification_failure(mock_main_dependencies):
    _, _, _, _, _, mock_notifications, mock_logger = mock_main_dependencies
    mock_notifications.return_value = False

    main()
    mock_logger.warning.assert_called_with("Failed to send notifications")

