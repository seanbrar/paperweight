"""Tests for the paper analyzer/summarization module.

This file tests the LLM boundary: how paperweight interacts with
external LLM providers to generate summaries, including fallback behavior.
"""

import pytest

from paperweight.analyzer import get_abstracts, summarize_paper


class TestSummarizePaper:
    """Tests for paper summarization with LLM providers."""

    @pytest.mark.parametrize("llm_provider, api_key, expected_result", [
        ('openai', 'fake_api_key', "This is a summary of the paper."),
        ('openai', None, "This is the abstract."),
        ('invalid_provider', 'fake_api_key', "This is the abstract."),
    ])
    def test_summarize_with_fallback(self, llm_provider, api_key, expected_result, mocker):
        """Summarization falls back to abstract when LLM unavailable."""
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


class TestGetAbstracts:
    """Tests for the get_abstracts function."""

    def test_invalid_analysis_type_raises(self):
        """Unknown analysis type raises ValueError."""
        config = {'type': 'invalid_type'}
        with pytest.raises(ValueError, match="Unknown analysis type: invalid_type"):
            get_abstracts([{'abstract': 'Test abstract'}], config)
