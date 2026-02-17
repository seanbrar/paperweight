"""Tests for the paper scoring processor.

This file tests the scoring algorithm that ranks papers by relevance
based on keywords, exclusion criteria, and important words.
"""

import pytest

from paperweight.processor import (
    calculate_paper_score,
    count_keywords,
    normalize_scores,
    process_papers,
)


@pytest.fixture
def processor_config():
    """Standard processor configuration for tests."""
    return {
        "keywords": ["AI", "healthcare", "quantum", "computing"],
        "exclusion_keywords": ["biology"],
        "important_words": ["artificial intelligence"],
        "title_keyword_weight": 3,
        "abstract_keyword_weight": 2,
        "content_keyword_weight": 1,
        "exclusion_keyword_penalty": 5,
        "important_words_weight": 0.5,
        "min_score": 0,
    }


class TestCalculatePaperScore:
    """Tests for the calculate_paper_score function."""

    def test_score_breakdown_structure(self, processor_config):
        """Score calculation returns score and breakdown dict."""
        paper = {
            "title": "AI in Healthcare",
            "abstract": "This paper discusses AI applications in healthcare.",
            "content": "Artificial Intelligence has numerous applications in healthcare...",
        }

        score, breakdown = calculate_paper_score(paper, processor_config)

        assert score > 0
        assert "keyword_matching" in breakdown
        assert "exclusion_penalty" in breakdown
        assert "important_words" in breakdown


class TestProcessPapers:
    """Tests for the process_papers function."""

    def test_papers_sorted_by_relevance(self, processor_config):
        """Papers are sorted by relevance score, highest first."""
        papers = [
            {
                "title": "AI in Healthcare",
                "abstract": "This paper discusses the applications of AI in healthcare.",
                "content": "Artificial Intelligence has numerous applications in healthcare...",
            },
            {
                "title": "Quantum Computing Advances",
                "abstract": "Recent advancements in quantum computing are presented.",
                "content": "Quantum computing has seen significant progress in recent years...",
            },
        ]
        processor_config["min_score"] = 5

        processed = process_papers(papers, processor_config)

        assert len(processed) == 2
        assert processed[0]["relevance_score"] > processed[1]["relevance_score"]
        assert "score_breakdown" in processed[0]
        assert "normalized_score" in processed[0]

    def test_empty_input_returns_empty(self, processor_config):
        """Empty paper list returns empty result."""
        result = process_papers([], processor_config)
        assert result == []


class TestCountKeywords:
    """Tests for the count_keywords function."""

    def test_returns_tuple(self):
        """count_keywords returns (score, matched_list) tuple."""
        score, matched = count_keywords("AI in healthcare", ["AI", "healthcare"])
        assert score > 0
        assert set(matched) == {"AI", "healthcare"}

    def test_no_matches_returns_empty(self):
        """count_keywords with no matches returns zero score and empty list."""
        score, matched = count_keywords("nothing relevant here", ["quantum"])
        assert score == 0.0
        assert matched == []


class TestKeywordsMatched:
    """Tests for keywords_matched propagation in process_papers."""

    def test_keywords_matched_in_scored_papers(self, processor_config):
        """Scored papers include keywords_matched field."""
        papers = [
            {
                "title": "AI in Healthcare",
                "abstract": "This paper discusses AI applications in healthcare.",
                "content": "",
            }
        ]
        processed = process_papers(papers, processor_config)
        assert len(processed) >= 1
        assert "keywords_matched" in processed[0]
        assert "AI" in processed[0]["keywords_matched"]


class TestNormalizeScores:
    """Tests for the normalize_scores function."""

    def test_normalization_range(self):
        """Scores are normalized to 0-1 range."""
        papers = [
            {"relevance_score": 10},
            {"relevance_score": 20},
            {"relevance_score": 30},
            {"relevance_score": 40},
        ]
        normalized = normalize_scores(papers)

        assert normalized[0]["normalized_score"] == 0.0
        assert normalized[-1]["normalized_score"] == 1.0
        assert (
            0.0
            < normalized[1]["normalized_score"]
            < normalized[2]["normalized_score"]
            < 1.0
        )

    def test_equal_scores_normalize_to_one(self):
        """When all scores are equal, normalized scores are 1.0."""
        papers = [
            {"relevance_score": 10},
            {"relevance_score": 10},
            {"relevance_score": 10},
        ]
        normalized = normalize_scores(papers)

        assert all(paper["normalized_score"] == 1.0 for paper in normalized)
