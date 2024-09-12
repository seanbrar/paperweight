from unittest.mock import patch

import pytest

from paperweight.analyzer import get_abstracts, summarize_paper


@pytest.mark.parametrize("llm_provider, api_key, expected_result", [
    ('openai', 'fake_api_key', "This is a summary of the paper."),
    ('openai', None, "This is the abstract."),
    ('invalid_provider', 'fake_api_key', "This is the abstract."),
])
def test_summarize_paper(llm_provider, api_key, expected_result, mocker):
    mock_llm = mocker.Mock()
    mock_llm.generate_response.return_value = "This is a summary of the paper."
    mocker.patch('paperweight.analyzer.LLM.create', return_value=mock_llm)

    paper = {
        'title': 'Test Paper',
        'abstract': 'This is the abstract.',
        'content': 'This is the full content of the paper.'
    }
    config = {
        'analyzer': {
            'type': 'summary',
            'llm_provider': llm_provider,
            'api_key': api_key
        }
    }

    result = summarize_paper(paper, config)
    assert result == expected_result

def test_get_abstracts_invalid_analysis_type():
    with pytest.raises(ValueError, match="Unknown analysis type: invalid_type"):
        config = {'type': 'invalid_type'}
        get_abstracts([{'abstract': 'Test abstract'}], config)

def test_summarize_paper_api_key_missing():
    paper = {
        'title': 'Test Paper',
        'abstract': 'This is a test abstract.',
        'content': 'This is the full content of the paper.'
    }
    config = {'analyzer': {'llm_provider': 'openai', 'api_key': None}}

    with patch('paperweight.analyzer.logger') as mock_logger:
        result = summarize_paper(paper, config)
        assert result == paper['abstract']
        mock_logger.warning.assert_called_with("No valid LLM provider or API key available for openai. Falling back to abstract.")

def test_summarize_paper_invalid_llm_provider():
    paper = {
        'title': 'Test Paper',
        'abstract': 'This is a test abstract.',
        'content': 'This is the full content of the paper.'
    }
    config = {'analyzer': {'llm_provider': 'invalid_provider', 'api_key': 'fake_api_key'}}

    with patch('paperweight.analyzer.logger') as mock_logger:
        result = summarize_paper(paper, config)
        assert result == paper['abstract']
        mock_logger.warning.assert_called_with("No valid LLM provider or API key available for invalid_provider. Falling back to abstract.")
