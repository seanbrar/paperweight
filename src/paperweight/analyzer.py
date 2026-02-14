"""Analyze and summarize papers.

The pipeline passes the *analyzer section* of the config into this module
(i.e. ``config["analyzer"]``). Keep this module's API aligned with that shape.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Literal, cast

from pollux import Config, RetryPolicy, Source, run

from paperweight.utils import count_tokens

ProviderName = Literal["gemini", "openai"]

logger = logging.getLogger(__name__)


def get_abstracts(processed_papers, config):
    """Extract abstracts or summaries from processed papers based on configuration.

    Args:
        processed_papers: List of dictionaries containing paper data.
        config: Configuration dictionary specifying analysis type and parameters.

    Returns:
        List of strings containing either abstracts or summaries based on config type.

    Raises:
        ValueError: If an unknown analysis type is specified in config.
    """
    analysis_type = config.get("type", "abstract")

    if analysis_type == "abstract":
        return [paper["abstract"] for paper in processed_papers]
    elif analysis_type == "summary":
        return [summarize_paper(paper, config) for paper in processed_papers]
    else:
        raise ValueError(f"Unknown analysis type: {analysis_type}")


def _truncate_for_prompt(
    content: str,
    prompt_prefix: str,
    *,
    max_input_tokens: int,
    max_input_chars: int,
) -> str:
    """Best-effort keep prompt within a reasonable size.

    Pollux/providers have their own limits; this is just a guardrail.
    """
    content = (content or "").strip()
    if max_input_chars > 0 and len(content) > max_input_chars:
        content = content[:max_input_chars].rstrip() + "\n\n[TRUNCATED]\n"

    # Token-based trim (approx). We scale down the content length until the prompt fits.
    if max_input_tokens > 0:
        prompt = f"{prompt_prefix}{content}"
        tokens = count_tokens(prompt)
        if tokens > max_input_tokens and content:
            # Approximate proportional truncation to avoid slow iterative trimming.
            scale = max_input_tokens / max(tokens, 1)
            target_chars = max(1000, int(len(content) * scale * 0.9))
            content = content[:target_chars].rstrip() + "\n\n[TRUNCATED]\n"

    return content


def _default_model_for_provider(provider: str) -> str:
    provider = (provider or "").lower().strip()
    if provider == "openai":
        return "gpt-5-nano"
    if provider == "gemini":
        return "gemini-2.5-flash-lite"
    return ""


def _resolve_triage_model_config(
    full_config: Dict[str, Any],
) -> tuple[str, str, str, float, int]:
    """Resolve provider/model/key and thresholds for triage mode."""
    triage_cfg = full_config.get("triage", {})
    analyzer_cfg = full_config.get("analyzer", {})

    provider = (
        triage_cfg.get("llm_provider")
        or analyzer_cfg.get("llm_provider")
        or "openai"
    ).lower()
    model = triage_cfg.get("model") or _default_model_for_provider(provider)
    api_key = (
        triage_cfg.get("api_key")
        or analyzer_cfg.get("api_key")
        or os.getenv(f"{provider.upper()}_API_KEY")
        or ""
    )
    min_score = float(triage_cfg.get("min_score", 60.0))
    max_selected = int(triage_cfg.get("max_selected", 25))
    return provider, model, api_key, min_score, max_selected


def _heuristic_triage_score(paper: Dict[str, Any], profile_terms: List[str]) -> float:
    text = f"{paper.get('title', '')}\n{paper.get('abstract', '')}".lower()
    hits = 0
    for term in profile_terms:
        if term and term.lower() in text:
            hits += 1
    if not profile_terms:
        return 50.0
    return min(100.0, 100.0 * (hits / len(profile_terms)))


def _triage_one_paper(
    paper: Dict[str, Any],
    pollux_config: Config,
    profile: str,
    *,
    min_score: float,
) -> Dict[str, Any]:
    title = (paper.get("title") or "").strip()
    abstract = (paper.get("abstract") or "").strip()

    prompt = (
        "You are triaging arXiv papers for relevance.\n"
        "Return JSON only with keys: include (boolean), score (0-100 number), rationale (string).\n"
        "Be strict. Include only if likely useful to the profile.\n\n"
        f"Profile:\n{profile}\n\n"
        f"Title: {title}\n\n"
        f"Abstract:\n{abstract}\n"
    )

    result = asyncio.run(run(prompt, config=pollux_config))
    response = None
    if isinstance(result, dict):
        answers = result.get("answers")
        if isinstance(answers, list) and answers:
            response = answers[0]
    if not response:
        return {
            "include": False,
            "score": 0.0,
            "rationale": "No model response",
        }

    raw = str(response).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]

    parsed = json.loads(raw)
    score = float(parsed.get("score", 0.0))
    include = bool(parsed.get("include", score >= min_score))
    rationale = str(parsed.get("rationale", "")).strip()
    return {"include": include, "score": score, "rationale": rationale}


def triage_papers(
    papers: List[Dict[str, Any]],
    full_config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """AI-first triage using title+abstract before expensive content processing."""
    if not papers:
        return []

    triage_cfg = full_config.get("triage", {})
    if not triage_cfg.get("enabled", True):
        return papers

    provider, model, api_key, min_score, max_selected = _resolve_triage_model_config(
        full_config
    )
    profile_terms = full_config.get("processor", {}).get("keywords", [])
    profile_text = "\n".join(f"- {term}" for term in profile_terms if term)

    if provider not in ("openai", "gemini") or not api_key:
        logger.warning(
            "AI triage is enabled but provider/key is unavailable; using heuristic triage."
        )
        shortlisted = []
        for paper in papers:
            score = _heuristic_triage_score(paper, profile_terms)
            paper["triage_score"] = score
            paper["triage_rationale"] = "Keyword/abstract heuristic fallback"
            if score >= min_score:
                shortlisted.append(paper)
        return shortlisted[:max_selected]

    provider_name = cast(ProviderName, provider)
    pollux_config = Config(
        provider=provider_name,
        model=model,
        api_key=api_key,
        retry=RetryPolicy(max_attempts=2, initial_delay_s=1.0, max_delay_s=5.0),
    )

    shortlisted = []
    for paper in papers:
        try:
            decision = _triage_one_paper(
                paper,
                pollux_config,
                profile_text,
                min_score=min_score,
            )
        except Exception as e:
            logger.warning("AI triage failed for '%s': %s", paper.get("title", ""), e)
            score = _heuristic_triage_score(paper, profile_terms)
            decision = {
                "include": score >= min_score,
                "score": score,
                "rationale": "LLM error; keyword/abstract heuristic fallback",
            }

        paper["triage_score"] = float(decision["score"])
        paper["triage_rationale"] = decision["rationale"]
        if decision["include"] and float(decision["score"]) >= min_score:
            shortlisted.append(paper)

    logger.info("AI triage selected %s/%s papers", len(shortlisted), len(papers))
    return shortlisted[:max_selected]


def summarize_paper(paper: Dict[str, Any], config: Dict[str, Any]) -> str:
    """Generate a summary of a paper using an LLM.

    Uses Pollux for LLM interaction. Pollux handles retries internally
    via RetryPolicy (exponential backoff with jitter).

    Args:
        paper: Dictionary containing paper data including content and metadata.
        config: Configuration dictionary containing LLM settings.

    Returns:
        A string containing the generated summary.
    """
    llm_provider = (config.get("llm_provider") or "openai").lower().strip()
    api_key = config.get("api_key")

    if llm_provider not in ["openai", "gemini"] or not api_key:
        logger.warning(
            f"No valid LLM provider or API key available for {llm_provider}. Falling back to abstract."
        )
        return paper["abstract"]

    try:
        provider: ProviderName = llm_provider  # type: ignore[assignment]  # guarded above
        model_name = (config.get("model") or "").strip() or _default_model_for_provider(
            llm_provider
        )
        pollux_config = Config(
            provider=provider,
            model=model_name,
            api_key=api_key,
            retry=RetryPolicy(max_attempts=3, initial_delay_s=1.0, max_delay_s=10.0),
        )

        title = (paper.get("title") or "").strip()
        abstract = (paper.get("abstract") or "").strip()
        content = paper.get("content") or ""

        # Guardrails. Defaults intentionally conservative.
        max_input_tokens = int(config.get("max_input_tokens", 7000))
        max_input_chars = int(config.get("max_input_chars", 20_000))

        prompt = (
            "Summarize the paper for a busy researcher.\n"
            "Constraints:\n"
            "- Be accurate; do not invent results.\n"
            "- 4-6 sentences.\n"
            "- Include: problem, approach, key results/claims, and who should read it.\n\n"
            f"Title: {title}\n\n"
            f"Abstract:\n{abstract}\n\n"
        )

        content = _truncate_for_prompt(
            str(content),
            prompt,
            max_input_tokens=max_input_tokens,
            max_input_chars=max_input_chars,
        )
        source = Source.from_text(content, identifier=title or "paper-content")

        input_tokens = count_tokens(prompt) + count_tokens(content)
        logger.info(f"Input token count: {input_tokens}")

        result = asyncio.run(run(prompt, source=source, config=pollux_config))
        response = None
        if isinstance(result, dict):
            answers = result.get("answers")
            if isinstance(answers, list) and answers:
                response = answers[0]
        if not response:
            logger.warning("LLM returned no answers; falling back to abstract.")
            return paper.get("abstract", "")

        output_tokens = count_tokens(response)
        logger.info(f"Output token count: {output_tokens}")

        return response
    except Exception as e:
        logger.error(f"Error summarizing paper: {e}", exc_info=True)
        return paper["abstract"]
