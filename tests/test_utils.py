import os
import tempfile
from unittest.mock import patch

import pytest
import yaml

from paperweight.utils import expand_env_vars, load_config, override_with_env


@pytest.fixture
def sample_config():
    return {
        'arxiv': {'categories': ['cs.AI'], 'max_results': 50},
        'processor': {'keywords': ['AI']},
        'analyzer': {'type': 'summary', 'llm_provider': 'openai'},
        'notifier': {'email': {'to': 'test@example.com', 'from': 'sender@example.com', 'password': 'pass', 'smtp_server': 'smtp.example.com', 'smtp_port': 587}},
        'logging': {'level': 'INFO'}
    }

@pytest.fixture
def config_file(sample_config):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_config:
        yaml.dump(sample_config, temp_config)
    yield temp_config.name
    os.unlink(temp_config.name)

def test_load_config_basic(config_file):
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'dummy_key'}):
        config = load_config(config_path=config_file)
    assert isinstance(config, dict)
    assert 'arxiv' in config
    assert 'processor' in config
    assert 'notifier' in config
    assert config['arxiv']['max_results'] == 50

def test_load_config_env_vars(config_file):
    with patch.dict(os.environ, {
        'PAPERWEIGHT_MAX_RESULTS': '100',
        'OPENAI_API_KEY': 'test_api_key'
    }):
        config = load_config(config_path=config_file)
    assert config['arxiv']['max_results'] == 100
    assert config['analyzer']['api_key'] == 'test_api_key'

def test_load_config_missing_env_vars(config_file, sample_config):
    sample_config['notifier']['email']['password'] = '$MISSING_VAR'
    with open(config_file, 'w') as f:
        yaml.dump(sample_config, f)
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'dummy_key'}):
        config = load_config(config_path=config_file)
    assert config['notifier']['email']['password'] == '$MISSING_VAR'

def test_load_config_logging(config_file):
    with patch('paperweight.utils.logger') as mock_logger:
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'dummy_key'}):
            load_config(config_path=config_file)
    mock_logger.info.assert_called_with("Configuration loaded and validated successfully")

def test_load_config_missing_api_key(config_file):
    with patch('paperweight.utils.load_dotenv', return_value=None):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Missing API key for openai"):
                load_config(config_path=config_file)

def test_load_config_with_api_key(config_file, sample_config):
    sample_config['analyzer']['type'] = 'summary'
    sample_config['analyzer']['llm_provider'] = 'openai'
    with open(config_file, 'w') as f:
        yaml.dump(sample_config, f)

    with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_api_key'}):
        config = load_config(config_path=config_file)
        assert config['analyzer']['api_key'] == 'test_api_key'

def test_load_config_non_summary_type(config_file, sample_config):
    sample_config['analyzer']['type'] = 'abstract'
    with open(config_file, 'w') as f:
        yaml.dump(sample_config, f)

    with patch.dict(os.environ, {}, clear=True):
        config = load_config(config_path=config_file)
        assert 'api_key' not in config['analyzer']

def test_expand_env_vars():
    with patch.dict(os.environ, {'TEST_VAR': 'test_value', 'NESTED_VAR': 'nested_value'}):
        config = {
            'simple': '$TEST_VAR',
            'nested': {'key': '${NESTED_VAR}', 'list': ['$TEST_VAR', '${NESTED_VAR}']},
            'untouched': 123
        }
        expanded = expand_env_vars(config)
    assert expanded['simple'] == 'test_value'
    assert expanded['nested']['key'] == 'nested_value'
    assert expanded['nested']['list'] == ['test_value', 'nested_value']
    assert expanded['untouched'] == 123

def test_override_with_env():
    config = {
        'max_results': 50,
        'enable_feature': False,
        'api_url': 'https://api.example.com',
        'timeout': 30.5
    }
    with patch.dict(os.environ, {
        'PAPERWEIGHT_MAX_RESULTS': '100',
        'PAPERWEIGHT_ENABLE_FEATURE': 'true',
        'PAPERWEIGHT_API_URL': 'https://new-api.example.com',
        'PAPERWEIGHT_TIMEOUT': '60.5'
    }):
        overridden = override_with_env(config)
    assert overridden['max_results'] == 100
    assert overridden['enable_feature']
    assert overridden['api_url'] == 'https://new-api.example.com'
    assert overridden['timeout'] == 60.5

def test_check_arxiv_section():
    from paperweight.utils import _check_arxiv_section
    valid_config = {'categories': ['cs.AI'], 'max_results': 50}
    _check_arxiv_section(valid_config)  # Should not raise an exception

    with pytest.raises(ValueError, match="'max_results' in 'arxiv' section must be a non-negative integer"):
        _check_arxiv_section({'categories': ['cs.AI'], 'max_results': -1})

def test_load_config_env_expansion_and_override(config_file, sample_config):
    sample_config['arxiv']['max_results'] = '$ENV_MAX_RESULTS'
    with open(config_file, 'w') as f:
        yaml.dump(sample_config, f)
    with patch.dict(os.environ, {
        'ENV_MAX_RESULTS': '50',
        'PAPERWEIGHT_MAX_RESULTS': '100'
    }):
        config = load_config(config_path=config_file)
    assert config['arxiv']['max_results'] == 100
