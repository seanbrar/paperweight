"""Utility functions for the paperweight application.

This module provides various utility functions for configuration management,
environment variable handling, date tracking, and token counting. It includes
functions for loading and validating configuration, expanding environment variables,
and managing the last processed date for paper fetching.
"""

import logging
import os
import re
from datetime import datetime

import tiktoken
import yaml
from dotenv import load_dotenv

LAST_PROCESSED_DATE_FILE = "last_processed_date.txt"

logger = logging.getLogger(__name__)


def expand_env_vars(config):
    """Recursively expand environment variables in configuration values.

    Args:
        config: Configuration object (dict, list, or scalar value).

    Returns:
        Configuration object with environment variables expanded.
    """
    if isinstance(config, dict):
        return {k: expand_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [expand_env_vars(v) for v in config]
    elif isinstance(config, str):
        return os.path.expandvars(config)
    else:
        return config


def override_with_env(config):
    """Override configuration values with environment variables.

    Args:
        config: Configuration dictionary to override.

    Returns:
        Configuration dictionary with values overridden by environment variables.

    Environment variables should be prefixed with 'PAPERWEIGHT_' and use uppercase.
    Nested configuration keys are joined with underscores.
    """
    env_prefix = "PAPERWEIGHT_"
    for key, value in config.items():
        env_var = f"{env_prefix}{key.upper()}"
        if isinstance(value, dict):
            config[key] = override_with_env(value)
        elif env_var in os.environ:
            env_value = os.environ[env_var]
            if isinstance(value, bool):
                config[key] = env_value.lower() in ("true", "1", "yes")
            elif isinstance(value, int):
                config[key] = int(env_value)
            elif isinstance(value, float):
                config[key] = float(env_value)
            else:
                config[key] = env_value
    return config


def load_config(config_path="config.yaml"):
    """Load and validate the application configuration.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Dictionary containing the validated configuration.

    Raises:
        FileNotFoundError: If the configuration file doesn't exist.
        yaml.YAMLError: If the configuration file is invalid YAML.
        ValueError: If the configuration is invalid.
    """
    try:
        load_dotenv()

        with open(config_path, "r") as config_file:
            config = yaml.safe_load(config_file)
        if config is None:
            raise ValueError("Empty configuration file")

        config = expand_env_vars(config)
        config = override_with_env(config)

        # Handle API keys
        if config["analyzer"]["type"] == "summary":
            llm_provider = config["analyzer"].get("llm_provider")
            if not llm_provider:
                raise ValueError("LLM provider not specified for summary analyzer type")

            api_key_from_config = config["analyzer"].get("api_key")
            api_key_from_env = os.getenv(f"{llm_provider.upper()}_API_KEY")
            api_key = api_key_from_config or api_key_from_env
            if api_key:
                config["analyzer"]["api_key"] = api_key
            else:
                raise ValueError(f"Missing API key for {llm_provider}")
        else:
            pass

        if "arxiv" in config and "max_results" in config["arxiv"]:
            config["arxiv"]["max_results"] = int(config["arxiv"]["max_results"])

        check_config(config)
        logger.info("Configuration loaded and validated successfully")
        return config
    except FileNotFoundError:
        error_msg = f"Configuration error: {config_path} file not found in the current directory"
        logger.error(error_msg)
        raise
    except yaml.YAMLError as e:
        error_msg = f"Configuration error: Error parsing {config_path}: {e}"
        logger.error(error_msg)
        raise
    except ValueError as e:
        error_msg = f"Configuration validation error: {str(e)}"
        logger.error(error_msg)
        raise
    except Exception as e:
        logger.error(f"Exception in load_config: {str(e)}")
        raise


def check_config(config):
    """Check if the configuration is valid.

    Args:
        config: Configuration dictionary to validate.

    Returns:
        bool: True if configuration is valid.

    Raises:
        ValueError: If any required configuration is missing or invalid.
    """
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a dictionary")
    try:
        _check_required_sections(config)
        _check_arxiv_section(config["arxiv"])
        _check_analyzer_section(config["analyzer"])
        _check_notifier_section(config["notifier"])
        _check_logging_section(config["logging"])
    except KeyError as e:
        raise ValueError(f"Missing required section or key: {e}")


def _check_required_sections(config):
    """Check if all required configuration sections are present.

    Args:
        config: Configuration dictionary to check.

    Raises:
        ValueError: If any required section is missing.
    """
    required_sections = ["arxiv", "processor", "analyzer", "notifier", "logging"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required section: '{section}'")


def _check_arxiv_section(arxiv):
    """Validate the arXiv section of the configuration.

    Args:
        arxiv: arXiv configuration dictionary.

    Raises:
        ValueError: If arXiv configuration is invalid.
    """
    if "categories" not in arxiv:
        raise ValueError("Missing required subsection: 'categories' in 'arxiv'")
    invalid_categories = [
        cat for cat in arxiv["categories"] if not is_valid_arxiv_category(cat)
    ]
    if invalid_categories:
        raise ValueError(f"Invalid arXiv category: {', '.join(invalid_categories)}")
    if "max_results" in arxiv:
        try:
            max_results = int(arxiv["max_results"])
        except ValueError:
            raise ValueError("'max_results' in 'arxiv' section must be a valid integer")

        if max_results < 0:
            raise ValueError(
                "'max_results' in 'arxiv' section must be a non-negative integer"
            )


def _check_analyzer_section(analyzer):
    """Validate the analyzer section of the configuration.

    Args:
        analyzer: Analyzer configuration dictionary.

    Raises:
        ValueError: If analyzer configuration is invalid.
    """
    valid_analyzer_types = ["abstract", "summary"]
    if analyzer.get("type") not in valid_analyzer_types:
        raise ValueError(f"Invalid analyzer type: '{analyzer.get('type')}'")
    if analyzer.get("type") == "summary":
        valid_llm_providers = ["openai", "gemini"]
        if analyzer.get("llm_provider") not in valid_llm_providers:
            raise ValueError(f"Invalid LLM provider: '{analyzer.get('llm_provider')}'")


def _check_notifier_section(notifier):
    """Validate the notifier section of the configuration.

    Args:
        notifier: Notifier configuration dictionary.

    Raises:
        ValueError: If notifier configuration is invalid.
    """
    if "email" not in notifier:
        raise ValueError("Missing required subsection: 'email' in 'notifier'")
    required_email_fields = ["to", "from", "password", "smtp_server", "smtp_port"]
    for field in required_email_fields:
        if field not in notifier["email"]:
            raise ValueError(f"Missing required email field: '{field}'")


def _check_logging_section(logging):
    """Validate the logging section of the configuration.

    Args:
        logging: Logging configuration dictionary.

    Raises:
        ValueError: If logging configuration is invalid.
    """
    valid_logging_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
    if logging.get("level") not in valid_logging_levels:
        raise ValueError(f"Invalid logging level: '{logging.get('level')}'")


def is_valid_arxiv_category(category):
    """Check if an arXiv category string is valid.

    Args:
        category: arXiv category string to validate.

    Returns:
        bool: True if the category format is valid.
    """
    # A simple method to catch obviously invalid categories
    pattern = r"^[a-z]+\.[A-Z]{2,}$"
    return bool(re.match(pattern, category))


def get_last_processed_date():
    """Get the date when papers were last processed.

    Returns:
        datetime.date: The last processed date if available, None otherwise.
    """
    try:
        if os.path.exists(LAST_PROCESSED_DATE_FILE):
            with open(LAST_PROCESSED_DATE_FILE, "r") as f:
                date_str = f.read().strip()
                return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (IOError, ValueError) as e:
        logger.error(f"Error reading last processed date: {e}")
    return None


def save_last_processed_date(date):
    """Save the date when papers were last processed.

    Args:
        date: datetime.date object to save.
    """
    try:
        with open(LAST_PROCESSED_DATE_FILE, "w") as f:
            f.write(date.strftime("%Y-%m-%d"))
        logger.info(f"Saved last processed date: {date}")
    except IOError as e:
        logger.error(f"Error saving last processed date: {e}")


def count_tokens(text):
    """Count the number of tokens in a text string using tiktoken.

    Args:
        text: String to count tokens in.

    Returns:
        int: Number of tokens in the text.
    """
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    return len(encoding.encode(text, allowed_special={"<|endoftext|>"}))
