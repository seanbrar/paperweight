"""Tests for the paper analyzer/summarization module.

This file tests the LLM boundary: how paperweight interacts with
external LLM providers to generate summaries.
"""

from unittest.mock import AsyncMock

import pytest

from paperweight.analyzer import get_abstracts, summarize_paper, triage_papers


class TestSummarizePaper:
    """Tests for paper summarization with LLM providers."""

    def test_summarize_success(self, mocker):
        """Summarization returns model output with valid provider/key."""
        # Mock Pollux's async run() function
        mock_result = {"answers": ["This is a summary of the paper."], "status": "ok"}
        mocker.patch("pollux.run", new=AsyncMock(return_value=mock_result))

        paper = {
            "title": "Test Paper",
            "abstract": "This is the abstract.",
            "content": "This is the full content of the paper.",
        }
        config = {
            "type": "summary",
            "llm_provider": "openai",
            "api_key": "fake_api_key",
        }

        result = summarize_paper(paper, config)
        assert result == "This is a summary of the paper."

    @pytest.mark.parametrize(
        "llm_provider, api_key",
        [
            ("openai", None),
            ("invalid_provider", "fake_api_key"),
        ],
    )
    def test_summarize_requires_valid_provider_and_key(
        self, llm_provider, api_key, mocker, monkeypatch
    ):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        mock_result = {"answers": ["This is a summary of the paper."], "status": "ok"}
        mocker.patch("pollux.run", new=AsyncMock(return_value=mock_result))

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

        with pytest.raises(ValueError, match="Summary analyzer requires"):
            summarize_paper(paper, config)

    def test_summarize_falls_back_to_abstract_when_model_returns_no_answers(self, mocker):
        mocker.patch("pollux.run", new=AsyncMock(return_value={"answers": []}))

        paper = {
            "title": "Test Paper",
            "abstract": "This is the abstract.",
            "content": "This is the full content of the paper.",
        }
        config = {
            "type": "summary",
            "llm_provider": "openai",
            "api_key": "fake_api_key",
        }

        result = summarize_paper(paper, config)
        assert result == "This is the abstract."


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
            "pollux.run",
            new=AsyncMock(
                return_value={
                    "answers": [
                        '{"include": true, "score": 92, "rationale": "Strong profile match"}'
                    ]
                }
            ),
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

    def test_triage_falls_back_for_entire_batch_when_llm_errors(self, mocker):
        mocker.patch(
            "pollux.run",
            new=AsyncMock(side_effect=RuntimeError("provider unavailable")),
        )
        papers = [
            {
                "title": "Transformers for Agents",
                "abstract": "A paper about language agents and planning.",
                "link": "http://arxiv.org/abs/2401.12345",
            },
            {
                "title": "Graph Theory for Chemistry",
                "abstract": "A paper about graph properties in molecules.",
                "link": "http://arxiv.org/abs/2401.67890",
            },
        ]
        config = {
            "triage": {"enabled": True, "llm_provider": "openai", "api_key": "key"},
            "processor": {"keywords": ["agents", "planning"]},
            "analyzer": {},
        }
        shortlisted = triage_papers(papers, config)
        assert len(shortlisted) == 1
        assert shortlisted[0]["title"] == "Transformers for Agents"
        assert all(
            "heuristic fallback" in paper["triage_rationale"].lower() for paper in papers
        )

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

    def test_triage_invalid_threshold_values_do_not_crash(self):
        papers = [
            {
                "title": "Transformers for Agents",
                "abstract": "A paper about language agents and planning.",
                "link": "http://arxiv.org/abs/2401.12345",
            }
        ]
        config = {
            "triage": {
                "enabled": True,
                "llm_provider": "openai",
                "min_score": "invalid",
                "max_selected": "invalid",
            },
            "processor": {"keywords": ["agents"]},
            "analyzer": {"type": "abstract"},
        }
        shortlisted = triage_papers(papers, config)
        assert len(shortlisted) == 1
