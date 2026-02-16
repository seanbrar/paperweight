"""Utility functions for the paperweight application.

This module provides various utility functions for configuration management,
environment variable handling, date tracking, and token counting. It includes
functions for loading and validating configuration, expanding environment variables,
and managing the last processed date for paper fetching.
"""

import hashlib
import json
import logging
import os
import re
from copy import deepcopy
from datetime import datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version

import tiktoken
import yaml
from dotenv import load_dotenv

LAST_PROCESSED_DATE_FILE = "last_processed_date.txt"
DEFAULT_ARXIV_VERSION = "v0"

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


def override_with_env(config, *, _path=()):
    """Override configuration values with environment variables.

    Environment variables use the prefix ``PAPERWEIGHT_`` and uppercase keys.

    Canonical nested form is fully-qualified:
    ``PAPERWEIGHT_ARXIV_MAX_RESULTS=50``.

    Backwards-compat: also accept the legacy leaf-only form (e.g.
    ``PAPERWEIGHT_MAX_RESULTS``). Fully-qualified wins if both are present.
    """

    def _coerce(env_value: str, current_value):
        if isinstance(current_value, bool):
            return env_value.lower() in ("true", "1", "yes")
        if isinstance(current_value, int):
            return int(env_value)
        if isinstance(current_value, float):
            return float(env_value)
        return env_value

    env_prefix = "PAPERWEIGHT_"
    for key, value in config.items():
        if isinstance(value, dict):
            config[key] = override_with_env(value, _path=_path + (key,))
            continue

        qualified = f"{env_prefix}{'_'.join([p.upper() for p in (_path + (key,))])}"
        legacy_leaf = f"{env_prefix}{key.upper()}"

        if qualified in os.environ:
            config[key] = _coerce(os.environ[qualified], value)
        elif legacy_leaf in os.environ:
            config[key] = _coerce(os.environ[legacy_leaf], value)

    return config


def _deep_merge_dicts(base, override):
    """Recursively merge *override* into a deep copy of *base*."""
    merged = deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def apply_profile(config, profile_name):
    """Apply a named profile on top of *config* and return the merged result."""
    profiles = config.get("profiles", {})
    if profile_name not in profiles:
        raise ValueError(f"Unknown profile: '{profile_name}'")
    overlay = profiles[profile_name]
    merged = _deep_merge_dicts(config, overlay)
    merged["active_profile"] = profile_name
    return merged


def load_config(config_path="config.yaml", profile=None):  # noqa: C901
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

        # Profile switching: CLI flag > env var > none
        profile_name = profile or os.environ.get("PAPERWEIGHT_PROFILE")
        if profile_name:
            config = apply_profile(config, profile_name)

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
        _check_logging_section(config["logging"])
        if "notifier" in config:
            _check_notifier_section(config["notifier"])
        if "db" in config and config["db"].get("enabled"):
            _check_db_section(config["db"])
        if "storage" in config:
            _check_storage_section(config["storage"])
        if "metadata_cache" in config:
            _check_metadata_cache_section(config["metadata_cache"])
        if "concurrency" in config:
            _check_concurrency_section(config["concurrency"])
        if "profiles" in config:
            _check_profiles_section(config["profiles"])
    except KeyError as e:
        raise ValueError(f"Missing required section or key: {e}")


def _check_required_sections(config):
    """Check if all required configuration sections are present.

    Args:
        config: Configuration dictionary to check.

    Raises:
        ValueError: If any required section is missing.
    """
    # Notifier is optional (stdout-only runs should not require SMTP config).
    required_sections = ["arxiv", "processor", "analyzer", "logging"]
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
    # Support stdout-only configs: notifier can be omitted or empty.
    if not notifier:
        return

    notifier_type = (notifier.get("type") or "").strip().lower()
    email_cfg = notifier.get("email") or {}
    email_enabled = email_cfg.get("enabled")

    # Backwards-compat: older configs had only notifier.email.* and were implicitly enabled.
    if email_enabled is None and "email" in notifier:
        email_enabled = True

    # Non-email notifiers have no SMTP requirements.
    if notifier_type and notifier_type != "email":
        return

    if not email_enabled:
        return

    if "email" not in notifier:
        raise ValueError("Missing required subsection: 'email' in 'notifier'")
    required_email_fields = ["to", "from", "smtp_server", "smtp_port"]
    for field in required_email_fields:
        if field not in notifier["email"]:
            raise ValueError(f"Missing required email field: '{field}'")
    use_auth = notifier["email"].get("use_auth", True)
    if use_auth and not notifier["email"].get("password"):
        raise ValueError("Missing required email field: 'password'")


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


def _check_db_section(db):
    """Validate the database section of the configuration.

    Args:
        db: Database configuration dictionary.

    Raises:
        ValueError: If database configuration is invalid.
    """
    required_fields = ["host", "port", "database", "user", "password", "sslmode"]
    for field in required_fields:
        if field not in db:
            raise ValueError(f"Missing required db field: '{field}'")
    try:
        int(db["port"])
    except (ValueError, TypeError) as e:
        raise ValueError("'port' in 'db' section must be a valid integer") from e
    valid_sslmodes = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
    if db["sslmode"] not in valid_sslmodes:
        raise ValueError(
            f"Invalid sslmode '{db['sslmode']}'. Must be one of: {', '.join(sorted(valid_sslmodes))}"
        )


def _check_storage_section(storage):
    """Validate the storage section of the configuration."""
    if "base_dir" not in storage:
        raise ValueError("Missing required storage field: 'base_dir'")


def _check_metadata_cache_section(mc):
    """Validate the metadata_cache section of the configuration."""
    if not isinstance(mc, dict):
        raise ValueError("'metadata_cache' must be a mapping")
    if "ttl_hours" in mc:
        try:
            val = int(mc["ttl_hours"])
        except (TypeError, ValueError):
            raise ValueError("'ttl_hours' in 'metadata_cache' must be a valid integer")
        if val < 0:
            raise ValueError("'ttl_hours' in 'metadata_cache' must be non-negative")


def _check_concurrency_section(concurrency):
    """Validate the concurrency section of the configuration."""
    if not isinstance(concurrency, dict):
        raise ValueError("'concurrency' must be a mapping")
    limits = {
        "content_fetch": (1, 20),
        "triage": (1, 10),
        "summary": (1, 10),
    }
    for key, (lo, hi) in limits.items():
        if key in concurrency:
            try:
                val = int(concurrency[key])
            except (TypeError, ValueError):
                raise ValueError(f"'{key}' in 'concurrency' must be a valid integer")
            if val < lo or val > hi:
                raise ValueError(f"'{key}' in 'concurrency' must be between {lo} and {hi}")


def _check_profiles_section(profiles):
    """Validate the profiles section of the configuration."""
    if not isinstance(profiles, dict):
        raise ValueError("'profiles' must be a mapping")
    for name, overlay in profiles.items():
        if not isinstance(overlay, dict):
            raise ValueError(f"Profile '{name}' must be a mapping")


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


def hash_config(config):
    """Create a stable hash of configuration values with secrets removed.

    Args:
        config: Configuration dictionary.

    Returns:
        Hex-encoded SHA-256 hash.
    """
    sanitized = _redact_config(config)
    payload = json.dumps(sanitized, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _redact_config(value):
    """Remove sensitive keys before hashing configuration data."""
    if isinstance(value, dict):
        redacted = {}
        for key, val in value.items():
            if _is_sensitive_key(key):
                continue
            redacted[key] = _redact_config(val)
        return redacted
    if isinstance(value, list):
        return [_redact_config(item) for item in value]
    return value


def _is_sensitive_key(key):
    key_lower = key.lower()
    sensitive_substrings = ("password", "api_key", "apikey", "secret")
    return any(s in key_lower for s in sensitive_substrings)


def get_package_version():
    """Get the installed version of the paperweight package.

    Returns:
        Version string, or 'unknown' if the package is not installed.
    """
    try:
        return pkg_version("paperweight")
    except PackageNotFoundError:
        return "unknown"


def split_arxiv_id(raw_id):
    """Parse an arXiv identifier into base ID and version components.

    Handles both new-style (YYMM.NNNNN) and legacy (archive/NNNNNNN) formats,
    as well as full URLs.

    Args:
        raw_id: Raw arXiv ID string, possibly including URL prefix or version suffix.

    Returns:
        Tuple of (arxiv_id, version) where version defaults to DEFAULT_ARXIV_VERSION
        if not specified.
    """
    raw = (raw_id or "").strip()
    if "/abs/" in raw:
        raw = raw.split("/abs/")[-1]
    raw = raw.replace("http://arxiv.org/abs/", "").replace(
        "https://arxiv.org/abs/", ""
    )
    new_style = re.match(r"^(?P<id>\d{4}\.\d{4,5})(?P<version>v\d+)?$", raw)
    if new_style:
        return new_style.group("id"), new_style.group("version") or DEFAULT_ARXIV_VERSION
    legacy_style = re.match(r"^(?P<id>[a-z\-]+/\d{7})(?P<version>v\d+)?$", raw)
    if legacy_style:
        return legacy_style.group("id"), legacy_style.group("version") or DEFAULT_ARXIV_VERSION
    return raw, DEFAULT_ARXIV_VERSION
