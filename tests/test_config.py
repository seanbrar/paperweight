"""Tests for configuration loading and validation.

This file tests the configuration boundary: the interface between user-provided
YAML files, environment variables, and the validated configuration used by
the rest of the system.
"""

import os
import tempfile
from unittest.mock import patch

import pytest
import yaml

from paperweight.utils import (
    DEFAULT_CONFIG,
    _check_arxiv_section,
    apply_profile,
    check_config,
    expand_env_vars,
    load_config,
    override_with_env,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_base_config():
    """Minimal valid configuration for testing."""
    return {
        "arxiv": {"categories": ["cs.AI"]},
        "processor": {},
        "analyzer": {"type": "abstract"},
        "notifier": {
            "email": {
                "to": "test@example.com",
                "from": "sender@example.com",
                "password": "pass",
                "smtp_server": "smtp.example.com",
                "smtp_port": 587,
            }
        },
        "logging": {"level": "INFO"},
    }


@pytest.fixture
def sample_config():
    """Sample config for load_config tests."""
    return {
        "arxiv": {"categories": ["cs.AI"], "max_results": 50},
        "processor": {"keywords": ["AI"]},
        "analyzer": {"type": "summary", "llm_provider": "openai"},
        "notifier": {
            "email": {
                "to": "test@example.com",
                "from": "sender@example.com",
                "password": "pass",
                "smtp_server": "smtp.example.com",
                "smtp_port": 587,
            }
        },
        "logging": {"level": "INFO"},
    }


@pytest.fixture
def config_file(sample_config):
    """Write sample_config to a temp file for load_config tests."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(sample_config, f)
    yield f.name
    os.unlink(f.name)


# ---------------------------------------------------------------------------
# Config Loading Tests
# ---------------------------------------------------------------------------


class TestLoadConfig:
    """Tests for load_config function."""

    def test_missing_config_file(self, tmp_path, monkeypatch):
        """FileNotFoundError when config.yaml does not exist."""
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError):
            load_config()

    def test_invalid_yaml_syntax(self, tmp_path, monkeypatch):
        """YAMLError on malformed YAML."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("invalid: yaml: syntax:")
        with pytest.raises(yaml.YAMLError):
            load_config()

    def test_load_config_basic(self, config_file):
        """Successfully load a valid config file."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "dummy_key"}):
            config = load_config(config_path=config_file)
        assert isinstance(config, dict)
        assert "arxiv" in config
        assert config["arxiv"]["max_results"] == 50

    def test_env_var_override(self, config_file):
        """Environment variables override config file values."""
        with patch.dict(
            os.environ,
            {
                "PAPERWEIGHT_MAX_RESULTS": "100",
                "OPENAI_API_KEY": "test_api_key",
            },
        ):
            config = load_config(config_path=config_file)
        assert config["arxiv"]["max_results"] == 100
        assert config["analyzer"]["api_key"] == "test_api_key"

    def test_missing_api_key_raises(self, config_file):
        """ValueError when LLM provider requires API key that's missing."""
        with patch("paperweight.utils.load_dotenv", return_value=None):
            with patch.dict(os.environ, {}, clear=True):
                with pytest.raises(ValueError, match="Missing API key for openai"):
                    load_config(config_path=config_file)

    def test_abstract_type_no_api_key_required(self, config_file, sample_config):
        """Abstract analyzer type does not require API key."""
        sample_config["analyzer"]["type"] = "abstract"
        with open(config_file, "w") as f:
            yaml.dump(sample_config, f)

        with patch.dict(os.environ, {}, clear=True):
            config = load_config(config_path=config_file)
            assert "api_key" not in config["analyzer"]


# ---------------------------------------------------------------------------
# Config Validation Tests
# ---------------------------------------------------------------------------


class TestCheckConfig:
    """Tests for check_config validation."""

    def test_missing_required_section(self):
        """Missing top-level section raises ValueError."""
        config = {
            "arxiv": {},
            "processor": {},
            "analyzer": {},
            "notifier": {},
        }
        with pytest.raises(ValueError, match="Missing required section: 'logging'"):
            check_config(config)

    def test_missing_categories_subsection(self):
        """Missing categories in arxiv section raises ValueError."""
        config = {
            "arxiv": {},
            "processor": {},
            "analyzer": {},
            "notifier": {},
            "logging": {},
        }
        with pytest.raises(
            ValueError, match="Missing required subsection: 'categories' in 'arxiv'"
        ):
            check_config(config)

    def test_valid_config_passes(self, valid_base_config):
        """Valid configuration passes validation."""
        assert check_config(valid_base_config) is None

    def test_valid_multiple_categories(self, valid_base_config):
        """Multiple valid arXiv categories pass validation."""
        valid_base_config["arxiv"]["categories"] = ["cs.AI", "math.CO", "physics.APP"]
        assert check_config(valid_base_config) is None

    def test_notifier_is_optional(self, valid_base_config):
        """Notifier section can be omitted for stdout/atom delivery."""
        del valid_base_config["notifier"]
        assert check_config(valid_base_config) is None


class TestInvalidCategories:
    """Tests for invalid arXiv category validation."""

    @pytest.mark.parametrize(
        "invalid_category",
        [
            "invalid",  # No dot
            "cs.ai",  # Lowercase after dot
            "CS.AI",  # Uppercase before dot
            "cs.A",  # Only one letter after dot
            "cs.AI.ML",  # More than one dot
            "123.AI",  # Numbers before dot
            "cs.123",  # Numbers after dot
        ],
    )
    def test_invalid_category_formats(self, valid_base_config, invalid_category):
        """Invalid arXiv category format raises ValueError."""
        valid_base_config["arxiv"]["categories"] = [invalid_category]
        with pytest.raises(
            ValueError, match=f"Invalid arXiv category: {invalid_category}"
        ):
            check_config(valid_base_config)


class TestAnalyzerValidation:
    """Tests for analyzer configuration validation."""

    def test_invalid_analyzer_type(self, valid_base_config):
        """Invalid analyzer type raises ValueError."""
        valid_base_config["analyzer"]["type"] = "invalid_type"
        with pytest.raises(ValueError, match="Invalid analyzer type: 'invalid_type'"):
            check_config(valid_base_config)

    def test_invalid_llm_provider(self, valid_base_config):
        """Invalid LLM provider raises ValueError."""
        valid_base_config["analyzer"] = {
            "type": "summary",
            "llm_provider": "invalid_provider",
        }
        with pytest.raises(
            ValueError, match="Invalid LLM provider: 'invalid_provider'"
        ):
            check_config(valid_base_config)


class TestEmailValidation:
    """Tests for email configuration validation."""

    def test_missing_email_field(self, valid_base_config):
        """Missing required email field raises ValueError."""
        valid_base_config["notifier"]["email"] = {"to": "test@example.com"}
        with pytest.raises(ValueError, match="Missing required email field: 'from'"):
            check_config(valid_base_config)

    def test_no_auth_does_not_require_password(self, valid_base_config):
        """When use_auth=False, password is not required."""
        valid_base_config["notifier"]["email"] = {
            "to": "test@example.com",
            "from": "sender@example.com",
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
            "use_auth": False,
        }
        assert check_config(valid_base_config) is None

    def test_auth_requires_password(self, valid_base_config):
        """When use_auth is True (default), password is required."""
        del valid_base_config["notifier"]["email"]["password"]
        with pytest.raises(
            ValueError, match="Missing required email field: 'password'"
        ):
            check_config(valid_base_config)

    def test_email_disabled_skips_required_fields(self, valid_base_config):
        """Email requirements are skipped when explicitly disabled."""
        valid_base_config["notifier"] = {
            "type": "email",
            "email": {"enabled": False},
        }
        assert check_config(valid_base_config) is None


class TestLoggingValidation:
    """Tests for logging configuration validation."""

    def test_invalid_logging_level(self, valid_base_config):
        """Invalid logging level raises ValueError."""
        valid_base_config["logging"]["level"] = "INVALID_LEVEL"
        with pytest.raises(ValueError, match="Invalid logging level: 'INVALID_LEVEL'"):
            check_config(valid_base_config)


class TestDatabaseValidation:
    """Tests for database configuration validation."""

    def test_db_enabled_requires_integer_port(self, valid_base_config):
        """Database port must be integer when db is enabled."""
        valid_base_config["db"] = {
            "enabled": True,
            "host": "localhost",
            "port": None,
            "database": "paperweight",
            "user": "paperweight",
            "password": "pass",
            "sslmode": "prefer",
        }
        with pytest.raises(
            ValueError, match="'port' in 'db' section must be a valid integer"
        ):
            check_config(valid_base_config)


# ---------------------------------------------------------------------------
# Utility Function Tests
# ---------------------------------------------------------------------------


class TestEnvVarExpansion:
    """Tests for environment variable expansion."""

    def test_expand_env_vars(self):
        """Expand $VAR and ${VAR} syntax in config values."""
        with patch.dict(
            os.environ, {"TEST_VAR": "test_value", "NESTED_VAR": "nested_value"}
        ):
            config = {
                "simple": "$TEST_VAR",
                "nested": {
                    "key": "${NESTED_VAR}",
                    "list": ["$TEST_VAR", "${NESTED_VAR}"],
                },
                "untouched": 123,
            }
            expanded = expand_env_vars(config)
        assert expanded["simple"] == "test_value"
        assert expanded["nested"]["key"] == "nested_value"
        assert expanded["nested"]["list"] == ["test_value", "nested_value"]
        assert expanded["untouched"] == 123

    def test_override_with_env(self):
        """PAPERWEIGHT_* env vars override config values with type coercion."""
        config = {
            "max_results": 50,
            "enable_feature": False,
            "api_url": "https://api.example.com",
            "timeout": 30.5,
        }
        with patch.dict(
            os.environ,
            {
                "PAPERWEIGHT_MAX_RESULTS": "100",
                "PAPERWEIGHT_ENABLE_FEATURE": "true",
                "PAPERWEIGHT_API_URL": "https://new-api.example.com",
                "PAPERWEIGHT_TIMEOUT": "60.5",
            },
        ):
            overridden = override_with_env(config)
        assert overridden["max_results"] == 100
        assert overridden["enable_feature"] is True
        assert overridden["api_url"] == "https://new-api.example.com"
        assert overridden["timeout"] == 60.5


class TestArxivSectionValidation:
    """Tests for _check_arxiv_section helper."""

    def test_negative_max_results_raises(self):
        """Negative max_results raises ValueError."""
        with pytest.raises(
            ValueError,
            match="'max_results' in 'arxiv' section must be a non-negative integer",
        ):
            _check_arxiv_section({"categories": ["cs.AI"], "max_results": -1})


# ---------------------------------------------------------------------------
# Profile Tests
# ---------------------------------------------------------------------------


class TestProfiles:
    """Tests for profile switching."""

    def test_apply_profile_deep_merges(self):
        """Profile overlay deep-merges into base config."""
        config = {
            "arxiv": {"categories": ["cs.AI"], "max_results": 50},
            "profiles": {
                "fast": {"arxiv": {"max_results": 20}},
            },
        }
        merged = apply_profile(config, "fast")
        assert merged["arxiv"]["max_results"] == 20
        assert merged["arxiv"]["categories"] == ["cs.AI"]
        assert merged["active_profile"] == "fast"

    def test_apply_profile_unknown_name_raises(self):
        """Unknown profile name raises ValueError."""
        config = {"profiles": {"fast": {"arxiv": {"max_results": 20}}}}
        with pytest.raises(ValueError, match="Unknown profile: 'nope'"):
            apply_profile(config, "nope")

    def test_load_config_with_profile(self, tmp_path):
        """load_config applies profile when given."""
        cfg = {
            "arxiv": {"categories": ["cs.AI"], "max_results": 50},
            "processor": {"keywords": ["AI"]},
            "analyzer": {"type": "abstract"},
            "logging": {"level": "INFO"},
            "profiles": {
                "fast": {"arxiv": {"max_results": 10}},
            },
        }
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(cfg), encoding="utf-8")
        with patch.dict(os.environ, {}, clear=False):
            result = load_config(config_path=str(config_path), profile="fast")
        assert result["arxiv"]["max_results"] == 10
        assert result["active_profile"] == "fast"


# ---------------------------------------------------------------------------
# DEFAULT_CONFIG Merge Tests
# ---------------------------------------------------------------------------


class TestDefaultConfigMerge:
    """Tests for DEFAULT_CONFIG merge behavior in load_config."""

    def test_minimal_config_loads_without_crash(self, tmp_path):
        """A config with only arxiv.categories loads successfully via DEFAULT_CONFIG merge."""
        cfg = {"arxiv": {"categories": ["cs.AI"]}}
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(cfg), encoding="utf-8")
        with patch.dict(os.environ, {}, clear=False):
            result = load_config(config_path=str(config_path))
        assert result["analyzer"]["type"] == "abstract"
        assert result["processor"]["min_score"] == 3
        assert result["triage"]["enabled"] is False
        assert result["logging"]["level"] == "INFO"
        assert "file" not in result["logging"]

    def test_default_config_has_triage_disabled(self):
        """DEFAULT_CONFIG has triage.enabled set to False."""
        assert DEFAULT_CONFIG["triage"]["enabled"] is False

    def test_user_config_overrides_defaults(self, tmp_path):
        """User config values override DEFAULT_CONFIG."""
        cfg = {
            "arxiv": {"categories": ["cs.AI"]},
            "processor": {"min_score": 10, "keywords": ["test"]},
        }
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(cfg), encoding="utf-8")
        with patch.dict(os.environ, {}, clear=False):
            result = load_config(config_path=str(config_path))
        assert result["processor"]["min_score"] == 10
        assert result["processor"]["keywords"] == ["test"]
        # Defaults still fill in missing keys
        assert result["processor"]["title_keyword_weight"] == 3
