import logging
import math
import re
from collections import Counter
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

def process_papers(papers: List[Dict[str, Any]], processor_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    processed_papers = []
    for paper in papers:
        score, score_breakdown = calculate_paper_score(paper, processor_config)
        logger.debug(f"Paper '{paper['title']}' scored {score}")
        if score >= processor_config['min_score']:
            paper['relevance_score'] = score
            paper['score_breakdown'] = score_breakdown
            processed_papers.append(paper)
        else:
            logger.debug(f"Paper '{paper['title']}' filtered out. Score {score} < min_score {processor_config['min_score']}")

    logger.debug(f"Processed {len(processed_papers)} papers out of {len(papers)}")

    processed_papers = normalize_scores(processed_papers)
    return sorted(processed_papers, key=lambda x: x['normalized_score'], reverse=True)

def normalize_scores(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not papers:
        return papers

    max_score = max(paper['relevance_score'] for paper in papers)
    min_score = min(paper['relevance_score'] for paper in papers)

    for paper in papers:
        if max_score != min_score:
            paper['normalized_score'] = (paper['relevance_score'] - min_score) / (max_score - min_score)
        else:
            paper['normalized_score'] = 1.0

    logger.debug("Normalized scores calculated")
    return papers

def calculate_paper_score(paper, config):
    score = 0
    score_breakdown = {}
    # Keyword matching
    title_keywords = count_keywords(paper['title'], config['keywords'])
    abstract_keywords = count_keywords(paper['abstract'], config['keywords'])
    content_keywords = count_keywords(paper['content'], config['keywords'])

    max_title_score = 50
    max_abstract_score = 50
    max_content_score = 25

    title_score = min(title_keywords * config['title_keyword_weight'], max_title_score)
    abstract_score = min(abstract_keywords * config['abstract_keyword_weight'], max_abstract_score)
    content_score = min(content_keywords * config['content_keyword_weight'], max_content_score)

    score += title_score + abstract_score + content_score
    score_breakdown['keyword_matching'] = {
        'title': round(title_score, 2),
        'abstract': round(abstract_score, 2),
        'content': round(content_score, 2)
    }

    # Exclusion list
    exclusion_count = count_keywords(paper['content'], config['exclusion_keywords'])
    exclusion_score = min(exclusion_count * config['exclusion_keyword_penalty'], max_content_score)
    score -= exclusion_score
    score_breakdown['exclusion_penalty'] = -round(exclusion_score, 2)

    # Simple text analysis
    important_word_count = count_important_words(paper['content'], config['important_words'])
    important_word_score = min(important_word_count * config['important_words_weight'], max_content_score)
    score += important_word_score
    score_breakdown['important_words'] = round(important_word_score, 2)

    return max(score, 0), score_breakdown # Ensure score is not negative

def count_keywords(text, keywords):
    return sum(math.log(text.lower().count(keyword.lower()) + 1) for keyword in keywords)

def count_important_words(text, important_words):
    words = re.findall(r'\w+', text.lower())
    word_counts = Counter(words)
    return sum(math.log(word_counts[word.lower()] + 1) for word in important_words if word.lower() in word_counts)
