"""Module for configuring logging in the paperweight application.

This module provides functionality for setting up logging with both file and console
handlers, configurable log levels, and standardized formatting. It ensures log directories
exist and handles invalid logging level configurations gracefully.
"""

import logging
import logging.config
import os


def setup_logging(logging_config):
    """Set up logging configuration for the application.

    Args:
        logging_config: Dictionary containing logging configuration parameters including
                       'level' and optional 'file' settings.

    The function configures handlers with the following features:
    - Console handler with WARNING and above levels
    - File handler with the configured level (defaults to INFO) when 'file' is set
    - Standard format: timestamp - logger_name - level - message
    - Automatic creation of log directory if it doesn't exist
    """
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    logging_level = logging_config.get("level", "INFO").upper()
    if logging_level not in valid_levels:
        logging_level = "INFO"

    log_file = logging_config.get("file")

    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "WARNING",
        },
    }
    active_handlers = ["console"]

    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        handlers["file"] = {
            "class": "logging.FileHandler",
            "filename": log_file,
            "formatter": "standard",
            "level": logging_level,
        }
        active_handlers.append("file")

    dict_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": handlers,
        "root": {
            "handlers": active_handlers,
            "level": logging_level,
        },
    }
    logging.config.dictConfig(dict_config)

    logging.getLogger().setLevel(logging_level)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging setup completed with level: {logging_level}")
