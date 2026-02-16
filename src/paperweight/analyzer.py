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

# Keep fanout modest for provider stability and local predictability.
SUMMARY_CONCURRENCY = 3
TRIAGE_CONCURRENCY = 3
LLM_TIMEOUT_S = 45.0
RATIONALE_MAX_CHARS = 160


def _int_setting(value: Any, default: int, *, minimum: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, parsed)


def _float_setting(value: Any, default: float, *, minimum: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, parsed)


def _compact_rationale(text, *, max_chars=RATIONALE_MAX_CHARS):
    """Whitespace-normalize and truncate a triage rationale."""
    text = " ".join((text or "").split())
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "\u2026"
    return text or "No rationale"


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
    if analysis_type == "summary":
        return summarize_papers(processed_papers, config)
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
    min_score = _float_setting(triage_cfg.get("min_score"), 60.0, minimum=0.0)
    max_selected = _int_setting(triage_cfg.get("max_selected"), 25, minimum=1)
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


def _heuristic_triage(
    papers: List[Dict[str, Any]],
    profile_terms: List[str],
    *,
    min_score: float,
    max_selected: int,
    rationale: str,
) -> List[Dict[str, Any]]:
    shortlisted = []
    for paper in papers:
        score = _heuristic_triage_score(paper, profile_terms)
        paper["triage_score"] = score
        paper["triage_rationale"] = rationale
        if score >= min_score:
            shortlisted.append(paper)
    return shortlisted[:max_selected]


def _build_triage_prompt(paper: Dict[str, Any], profile: str) -> str:
    title = (paper.get("title") or "").strip()
    abstract = (paper.get("abstract") or "").strip()
    return (
        "You are triaging arXiv papers for relevance.\n"
        "Return JSON only with keys: include (boolean), score (0-100 number), rationale (string).\n"
        "Rationale must be a compact one-liner (max 20 words).\n"
        "Be strict. Include only if likely useful to the profile.\n\n"
        f"Profile:\n{profile}\n\n"
        f"Title: {title}\n\n"
        f"Abstract:\n{abstract}\n"
    )


def _parse_triage_decision(response: Any, *, min_score: float) -> Dict[str, Any]:
    if not response:
        raise ValueError("No model response")

    raw = str(response).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]

    parsed = json.loads(raw)
    score = float(parsed.get("score", 0.0))
    include = bool(parsed.get("include", score >= min_score))
    rationale = _compact_rationale(str(parsed.get("rationale", "")))
    return {"include": include, "score": score, "rationale": rationale}


async def _triage_one_paper_async(prompt, pollux_config, *, min_score):
    """Call `run` for a single triage prompt with a timeout."""
    result = await asyncio.wait_for(
        run(prompt, config=pollux_config), timeout=LLM_TIMEOUT_S
    )
    answer = None
    if isinstance(result, dict):
        answers = result.get("answers")
        if isinstance(answers, list) and answers:
            answer = answers[0]
    return _parse_triage_decision(answer, min_score=min_score)


async def _run_triage_async(prompts, pollux_config, *, min_score):
    """Run triage prompts concurrently with a semaphore, returning decisions in order."""
    semaphore = asyncio.Semaphore(TRIAGE_CONCURRENCY)
    total = len(prompts)
    completed = 0

    async def _worker(index, prompt):
        nonlocal completed
        async with semaphore:
            decision = await _triage_one_paper_async(
                prompt, pollux_config, min_score=min_score
            )
            completed += 1
            logger.info("Triage: %d/%d", completed, total)
            return index, decision

    tasks = [asyncio.create_task(_worker(i, p)) for i, p in enumerate(prompts)]
    results = [None] * total
    for coro in asyncio.as_completed(tasks):
        index, decision = await coro
        results[index] = decision
    return results


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
        return _heuristic_triage(
            papers,
            profile_terms,
            min_score=min_score,
            max_selected=max_selected,
            rationale="Keyword/abstract heuristic fallback",
        )

    provider_name = cast(ProviderName, provider)
    pollux_config = Config(
        provider=provider_name,
        model=model,
        api_key=api_key,
        retry=RetryPolicy(
            max_attempts=2,
            initial_delay_s=1.0,
            max_delay_s=5.0,
            max_elapsed_s=20.0,
        ),
    )

    prompts = [_build_triage_prompt(paper, profile_text) for paper in papers]

    try:
        decisions = asyncio.run(
            _run_triage_async(prompts, pollux_config, min_score=min_score)
        )
    except Exception as exc:
        logger.warning(
            "AI triage failed; using heuristic triage for entire batch: %s",
            exc,
        )
        return _heuristic_triage(
            papers,
            profile_terms,
            min_score=min_score,
            max_selected=max_selected,
            rationale="LLM unavailable; keyword/abstract heuristic fallback",
        )

    shortlisted = []
    for paper, decision in zip(papers, decisions):
        paper["triage_score"] = float(decision["score"])
        paper["triage_rationale"] = decision["rationale"]
        if decision["include"] and float(decision["score"]) >= min_score:
            shortlisted.append(paper)

    logger.info("AI triage selected %s/%s papers", len(shortlisted), len(papers))
    return shortlisted[:max_selected]


async def _summarize_one_paper_async(
    paper: Dict[str, Any],
    pollux_config: Config,
    *,
    max_input_tokens: int,
    max_input_chars: int,
) -> str:
    title = (paper.get("title") or "").strip()
    abstract = (paper.get("abstract") or "").strip()
    content = paper.get("content") or ""

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
    logger.debug("Summary input tokens title=%r count=%s", title[:60], input_tokens)

    result = await asyncio.wait_for(
        run(prompt, source=source, config=pollux_config), timeout=LLM_TIMEOUT_S
    )
    response = None
    if isinstance(result, dict):
        answers = result.get("answers")
        if isinstance(answers, list) and answers:
            response = answers[0]
    if not response:
        raise RuntimeError(f"LLM returned no answers for '{title[:80]}'")

    output_tokens = count_tokens(response)
    logger.debug("Summary output tokens title=%r count=%s", title[:60], output_tokens)
    return str(response)


def _resolve_summary_model_config(config: Dict[str, Any]) -> tuple[ProviderName, str, str]:
    llm_provider = (config.get("llm_provider") or "openai").lower().strip()
    api_key = config.get("api_key") or os.getenv(f"{llm_provider.upper()}_API_KEY") or ""
    if llm_provider not in ("openai", "gemini") or not api_key:
        raise ValueError(
            "Summary analyzer requires a valid llm_provider (openai|gemini) and api_key."
        )
    model_name = (config.get("model") or "").strip() or _default_model_for_provider(
        llm_provider
    )
    return cast(ProviderName, llm_provider), model_name, api_key


def summarize_papers(  # noqa: C901
    papers: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> List[str]:
    """Summarize papers with abstract fallback on runtime LLM errors."""
    if not papers:
        return []

    provider, model_name, api_key = _resolve_summary_model_config(config)
    max_input_tokens = _int_setting(config.get("max_input_tokens"), 7000, minimum=500)
    max_input_chars = _int_setting(config.get("max_input_chars"), 20_000, minimum=1000)

    pollux_config = Config(
        provider=provider,
        model=model_name,
        api_key=api_key,
        retry=RetryPolicy(
            max_attempts=3,
            initial_delay_s=1.0,
            max_delay_s=10.0,
            max_elapsed_s=30.0,
        ),
    )

    async def _run_summary_batch() -> tuple[List[str | None], List[tuple[int, BaseException]]]:
        semaphore = asyncio.Semaphore(SUMMARY_CONCURRENCY)
        results: List[str | None] = [None] * len(papers)
        failures: List[tuple[int, BaseException]] = []
        completed = 0
        total = len(papers)

        async def _worker(index: int, paper: Dict[str, Any]):
            async with semaphore:
                try:
                    summary = await _summarize_one_paper_async(
                        paper,
                        pollux_config,
                        max_input_tokens=max_input_tokens,
                        max_input_chars=max_input_chars,
                    )
                    return index, summary, None
                except Exception as exc:
                    return index, None, exc

        tasks = [
            asyncio.create_task(_worker(index, paper))
            for index, paper in enumerate(papers)
        ]

        for task in asyncio.as_completed(tasks):
            index, summary, exc = await task
            completed += 1
            logger.info("Summary: %d/%d", completed, total)
            if exc is not None:
                failures.append((index, exc))
                continue
            results[index] = summary

        return results, failures

    raw_summaries, failures = asyncio.run(_run_summary_batch())

    summaries: List[str] = []
    for index, summary in enumerate(raw_summaries):
        if summary is not None:
            summaries.append(summary)
            continue
        fallback = str(papers[index].get("abstract") or "")
        summaries.append(fallback)

    if failures:
        logger.warning(
            "Summary fallback used for %s/%s papers.",
            len(failures),
            len(papers),
        )
        for index, exc in failures:
            logger.warning(
                "Summary failed for '%s': %s",
                papers[index].get("title", ""),
                exc,
            )

    return summaries


def summarize_paper(paper: Dict[str, Any], config: Dict[str, Any]) -> str:
    """Generate a summary of a single paper using the same batch engine."""
    summaries = summarize_papers([paper], config)
    if summaries:
        return summaries[0]
    return str(paper.get("abstract") or "")
