import pytest
import yaml

from paperweight.utils import check_config, load_config


def test_missing_config_file(tmp_path):
    import os
    os.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        load_config()

def test_invalid_yaml_syntax(tmp_path):
    import os
    os.chdir(tmp_path)
    with open('config.yaml', 'w') as f:
        f.write("invalid: yaml: syntax:")
    with pytest.raises(yaml.YAMLError):
        load_config()

def test_missing_required_sections():
    config = {
        'arxiv': {},
        'processor': {},
        'analyzer': {},
        'notifier': {},
    }
    with pytest.raises(ValueError, match="Missing required section: 'logging'"):
        check_config(config)

def test_missing_required_subsections():
    config = {
        'arxiv': {},
        'processor': {},
        'analyzer': {},
        'notifier': {},
        'logging': {}
    }
    with pytest.raises(ValueError, match="Missing required subsection: 'categories' in 'arxiv'"):
        check_config(config)

def test_invalid_category():
    config = {
        'arxiv': {'categories': ['invalid_category']},
        'processor': {},
        'analyzer': {'type': 'abstract'},
        'notifier': {'email': {'to': 'test@example.com', 'from': 'sender@example.com', 'password': 'pass', 'smtp_server': 'smtp.example.com', 'smtp_port': 587}},
        'logging': {'level': 'INFO'}
    }
    with pytest.raises(ValueError, match="Invalid arXiv category: invalid_category"):
        check_config(config)

def test_invalid_analyzer_type():
    config = {
        'arxiv': {'categories': ['cs.AI']},
        'processor': {},
        'analyzer': {'type': 'invalid_type'},
        'notifier': {'email': {'to': 'test@example.com', 'from': 'sender@example.com', 'password': 'pass', 'smtp_server': 'smtp.example.com', 'smtp_port': 587}},
        'logging': {'level': 'INFO'}
    }
    with pytest.raises(ValueError, match="Invalid analyzer type: 'invalid_type'"):
        check_config(config)

def test_invalid_llm_provider():
    config = {
        'arxiv': {'categories': ['cs.AI']},
        'processor': {},
        'analyzer': {'type': 'summary', 'llm_provider': 'invalid_provider'},
        'notifier': {'email': {'to': 'test@example.com', 'from': 'sender@example.com', 'password': 'pass', 'smtp_server': 'smtp.example.com', 'smtp_port': 587}},
        'logging': {'level': 'INFO'}
    }
    with pytest.raises(ValueError, match="Invalid LLM provider: 'invalid_provider'"):
        check_config(config)

def test_missing_email_fields():
    config = {
        'arxiv': {'categories': ['cs.AI']},
        'processor': {},
        'analyzer': {'type': 'abstract'},
        'notifier': {'email': {'to': 'test@example.com'}},
        'logging': {'level': 'INFO'}
    }
    with pytest.raises(ValueError, match="Missing required email field: 'from'"):
        check_config(config)

def test_invalid_logging_level():
    config = {
        'arxiv': {'categories': ['cs.AI']},
        'processor': {},
        'analyzer': {'type': 'abstract'},
        'notifier': {'email': {'to': 'test@example.com', 'from': 'sender@example.com', 'password': 'pass', 'smtp_server': 'smtp.example.com', 'smtp_port': 587}},
        'logging': {'level': 'INVALID_LEVEL'}
    }
    with pytest.raises(ValueError, match="Invalid logging level: 'INVALID_LEVEL'"):
        check_config(config)

def test_valid_config():
    config = {
        'arxiv': {'categories': ['cs.AI'], 'max_results': 100},
        'processor': {'keywords': ['ai'], 'min_score': 10},
        'analyzer': {'type': 'abstract'},
        'notifier': {'email': {'to': 'test@example.com', 'from': 'sender@example.com', 'password': 'pass', 'smtp_server': 'smtp.example.com', 'smtp_port': 587}},
        'logging': {'level': 'INFO', 'file': 'paperweight.log'}
    }
    assert check_config(config) is None

def test_valid_arxiv_categories():
    config = {
        'arxiv': {'categories': ['cs.AI', 'math.CO', 'physics.APP']},
        'processor': {},
        'analyzer': {'type': 'abstract'},
        'notifier': {'email': {'to': 'test@example.com', 'from': 'sender@example.com', 'password': 'pass', 'smtp_server': 'smtp.example.com', 'smtp_port': 587}},
        'logging': {'level': 'INFO'}
    }
    assert check_config(config) is None

def test_invalid_arxiv_category_formats():
    invalid_categories = [
        'invalid',  # No dot
        'cs.ai',    # Lowercase after dot
        'CS.AI',    # Uppercase before dot
        'cs.A',     # Only one letter after dot
        'cs.AI.ML', # More than one dot
        '123.AI',   # Numbers before dot
        'cs.123'    # Numbers after dot
    ]

    for invalid_category in invalid_categories:
        config = {
            'arxiv': {'categories': [invalid_category]},
            'processor': {},
            'analyzer': {'type': 'abstract'},
            'notifier': {'email': {'to': 'test@example.com', 'from': 'sender@example.com', 'password': 'pass', 'smtp_server': 'smtp.example.com', 'smtp_port': 587}},
            'logging': {'level': 'INFO'}
        }
        with pytest.raises(ValueError, match=f"Invalid arXiv category: {invalid_category}"):
            check_config(config)

def test_mixed_valid_and_invalid_categories():
    config = {
        'arxiv': {'categories': ['cs.AI', 'invalid_category', 'math.CO']},
        'processor': {},
        'analyzer': {'type': 'abstract'},
        'notifier': {'email': {'to': 'test@example.com', 'from': 'sender@example.com', 'password': 'pass', 'smtp_server': 'smtp.example.com', 'smtp_port': 587}},
        'logging': {'level': 'INFO'}
    }
    with pytest.raises(ValueError, match="Invalid arXiv category: invalid_category"):
        check_config(config)

def test_invalid_config_file():
    with pytest.raises(ValueError, match="Missing required section: 'logging'"):
        invalid_config = {
            'arxiv': {},
            'processor': {},
            'analyzer': {},
            'notifier': {}
        }
        check_config(invalid_config)
