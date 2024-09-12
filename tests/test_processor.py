import pytest

from paperweight.processor import (
    calculate_paper_score,
    normalize_scores,
    process_papers,
)


def test_calculate_paper_score():
    paper = {
        'title': 'Test Paper on AI',
        'abstract': 'This is a test abstract about artificial intelligence.',
        'content': 'This is the main content of the paper discussing AI techniques.'
    }
    config = {
        'keywords': ['AI', 'artificial intelligence'],
        'exclusion_keywords': ['biology'],
        'important_words': ['neural networks'],
        'title_keyword_weight': 3,
        'abstract_keyword_weight': 2,
        'content_keyword_weight': 1,
        'exclusion_keyword_penalty': 5,
        'important_words_weight': 0.5
    }

    score, breakdown = calculate_paper_score(paper, config)
    assert score > 0
    assert 'keyword_matching' in breakdown
    assert 'exclusion_penalty' in breakdown
    assert 'important_words' in breakdown

def test_process_papers():
    papers = [
        {
            'title': 'AI in Healthcare',
            'abstract': 'This paper discusses the applications of AI in healthcare.',
            'content': 'Artificial Intelligence has numerous applications in healthcare...'
        },
        {
            'title': 'Quantum Computing Advances',
            'abstract': 'Recent advancements in quantum computing are presented.',
            'content': 'Quantum computing has seen significant progress in recent years...'
        }
    ]
    processor_config = {
        'keywords': ['AI', 'healthcare', 'quantum', 'computing'],
        'exclusion_keywords': ['biology'],
        'important_words': ['artificial intelligence'],
        'title_keyword_weight': 3,
        'abstract_keyword_weight': 2,
        'content_keyword_weight': 1,
        'exclusion_keyword_penalty': 5,
        'important_words_weight': 0.5,
        'min_score': 5,
    }
    processed_papers = process_papers(papers, processor_config)

    assert len(processed_papers) == 2
    assert processed_papers[0]['relevance_score'] > processed_papers[1]['relevance_score']
    assert 'score_breakdown' in processed_papers[0]

def test_process_papers_empty_input():
    processor_config = {
        'keywords': ['AI'],
        'exclusion_keywords': ['biology'],
        'important_words': ['neural networks'],
        'title_keyword_weight': 3,
        'abstract_keyword_weight': 2,
        'content_keyword_weight': 1,
        'exclusion_keyword_penalty': 5,
        'important_words_weight': 0.5,
        'min_score': 5,
    }
    result = process_papers([], processor_config)
    assert result == []

def test_normalize_scores_edge_cases():
    papers = [
        {'relevance_score': 10},
        {'relevance_score': 10},
        {'relevance_score': 10}
    ]
    normalized_papers = normalize_scores(papers)
    assert all(paper['normalized_score'] == 1.0 for paper in normalized_papers)

def test_calculate_paper_score_various_inputs():
    paper = {
        'title': 'AI in Healthcare',
        'abstract': 'This paper discusses AI applications in healthcare.',
        'content': 'Artificial Intelligence has numerous applications in healthcare...'
    }
    config = {
        'keywords': ['AI', 'healthcare'],
        'exclusion_keywords': ['biology'],
        'important_words': ['artificial intelligence'],
        'title_keyword_weight': 3,
        'abstract_keyword_weight': 2,
        'content_keyword_weight': 1,
        'exclusion_keyword_penalty': 5,
        'important_words_weight': 0.5
    }
    score, breakdown = calculate_paper_score(paper, config)
    assert score > 0
    assert 'keyword_matching' in breakdown
    assert 'exclusion_penalty' in breakdown
    assert 'important_words' in breakdown

def test_normalize_scores():
    papers = [
        {'relevance_score': 10},
        {'relevance_score': 20},
        {'relevance_score': 30},
        {'relevance_score': 40},
    ]
    normalized_papers = normalize_scores(papers)

    assert normalized_papers[0]['normalized_score'] == 0.0
    assert normalized_papers[-1]['normalized_score'] == 1.0
    assert 0.0 < normalized_papers[1]['normalized_score'] < normalized_papers[2]['normalized_score'] < 1.0

def test_process_papers_with_normalization():
    papers = [
        {'title': 'Paper A', 'abstract': 'Abstract A', 'content': 'Content A'},
        {'title': 'Paper B', 'abstract': 'Abstract B', 'content': 'Content B'},
        {'title': 'Paper C', 'abstract': 'Abstract C', 'content': 'Content C'},
    ]
    processor_config = {
        'keywords': ['A', 'B', 'C'],
        'exclusion_keywords': [],
        'important_words': [],
        'title_keyword_weight': 3,
        'abstract_keyword_weight': 2,
        'content_keyword_weight': 1,
        'exclusion_keyword_penalty': 5,
        'important_words_weight': 0.5,
        'min_score': 0,
    }

    processed_papers = process_papers(papers, processor_config)

    assert len(processed_papers) == 3
    assert all('normalized_score' in paper for paper in processed_papers)
    assert processed_papers[0]['normalized_score'] >= processed_papers[1]['normalized_score'] >= processed_papers[2]['normalized_score']

@pytest.mark.parametrize("use_normalized_ranking", [True, False])
def test_process_papers_ranking_consistency(use_normalized_ranking):
    papers = [
        {'title': 'Paper A', 'abstract': 'Abstract A', 'content': 'Content A'},
        {'title': 'Paper B', 'abstract': 'Abstract B', 'content': 'Content B'},
        {'title': 'Paper C', 'abstract': 'Abstract C', 'content': 'Content C'},
    ]
    processor_config = {
        'keywords': ['A', 'B', 'C'],
        'exclusion_keywords': [],
        'important_words': [],
        'title_keyword_weight': 3,
        'abstract_keyword_weight': 2,
        'content_keyword_weight': 1,
        'exclusion_keyword_penalty': 5,
        'important_words_weight': 0.5,
        'min_score': 0,
    }

    processed_papers = process_papers(papers, processor_config)

    if use_normalized_ranking:
        assert all('normalized_score' in paper for paper in processed_papers)
        scores = [paper['normalized_score'] for paper in processed_papers]
    else:
        scores = [paper['relevance_score'] for paper in processed_papers]

    assert scores == sorted(scores, reverse=True)
