"""Tests for the paper analyzer/summarization module.

This file tests the LLM boundary: how paperweight interacts with
external LLM providers to generate summaries, including fallback behavior.
"""

import pytest

from paperweight.analyzer import get_abstracts, summarize_paper, triage_papers


class TestSummarizePaper:
    """Tests for paper summarization with LLM providers."""

    @pytest.mark.parametrize(
        "llm_provider, api_key, expected_result",
        [
            ("openai", "fake_api_key", "This is a summary of the paper."),
            ("openai", None, "This is the abstract."),
            ("invalid_provider", "fake_api_key", "This is the abstract."),
        ],
    )
    def test_summarize_with_fallback(
        self, llm_provider, api_key, expected_result, mocker
    ):
        """Summarization falls back to abstract when LLM unavailable."""
        # Mock Pollux's async run() function
        mock_result = {"answers": ["This is a summary of the paper."], "status": "ok"}
        mocker.patch("paperweight.analyzer.run", return_value=mock_result)

        paper = {
            "title": "Test Paper",
            "abstract": "This is the abstract.",
            "content": "This is the full content of the paper.",
        }
        config = {
            "type": "summary",
            "llm_provider": llm_provider,
            "api_key": api_key,
        }

        result = summarize_paper(paper, config)
        assert result == expected_result


class TestGetAbstracts:
    """Tests for the get_abstracts function."""

    def test_invalid_analysis_type_raises(self):
        """Unknown analysis type raises ValueError."""
        config = {"type": "invalid_type"}
        with pytest.raises(ValueError, match="Unknown analysis type: invalid_type"):
            get_abstracts([{"abstract": "Test abstract"}], config)


class TestTriagePapers:
    """Tests for AI triage stage."""

    def test_triage_uses_llm_decision(self, mocker):
        mocker.patch(
            "paperweight.analyzer.run",
            return_value={
                "answers": [
                    '{"include": true, "score": 92, "rationale": "Strong profile match"}'
                ]
            },
        )
        papers = [
            {
                "title": "Transformers for Agents",
                "abstract": "A paper about language agents and planning.",
                "link": "http://arxiv.org/abs/2401.12345",
            }
        ]
        config = {
            "triage": {"enabled": True, "llm_provider": "openai", "api_key": "key"},
            "processor": {"keywords": ["agents", "planning"]},
            "analyzer": {},
        }
        shortlisted = triage_papers(papers, config)
        assert len(shortlisted) == 1
        assert shortlisted[0]["triage_score"] == 92
        assert "Strong profile match" in shortlisted[0]["triage_rationale"]

    def test_triage_falls_back_without_api_key(self):
        papers = [
            {
                "title": "Transformers for Agents",
                "abstract": "A paper about language agents and planning.",
                "link": "http://arxiv.org/abs/2401.12345",
            }
        ]
        config = {
            "triage": {"enabled": True, "llm_provider": "openai", "min_score": 10},
            "processor": {"keywords": ["agents"]},
            "analyzer": {"type": "abstract"},
        }
        shortlisted = triage_papers(papers, config)
        assert len(shortlisted) == 1
        assert shortlisted[0]["triage_score"] >= 10
