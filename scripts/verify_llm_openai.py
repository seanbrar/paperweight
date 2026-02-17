#!/usr/bin/env python3
"""Smoke + latency checks for OpenAI-backed LLM features in paperweight.

This script validates:
1) direct Pollux->OpenAI connectivity for tiny prompts
2) paperweight summary path latency for a tiny synthetic paper
3) paperweight triage path latency for a tiny synthetic shortlist
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pollux import Config, RetryPolicy, run

# Keep local script runnable without package install.
sys.path.append(str(Path(__file__).parent.parent / "src"))

from paperweight.analyzer import summarize_paper, triage_papers

logger = logging.getLogger("verify_llm_openai")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    if not verbose:
        # Keep default output concise and focused on probe results.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("openai").setLevel(logging.WARNING)
        logging.getLogger("pollux").setLevel(logging.WARNING)
        logging.getLogger("paperweight.analyzer").setLevel(logging.WARNING)


def _safe_mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _safe_p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95))))
    return ordered[idx]


def _run_direct_probe(model: str, api_key: str, repeats: int) -> dict[str, Any]:
    durations: list[float] = []
    failures: list[str] = []
    answers: list[str] = []
    logger.info("Direct probe model=%s repeats=%s", model, repeats)

    for idx in range(1, repeats + 1):
        config = Config(
            provider="openai",
            model=model,
            api_key=api_key,
            retry=RetryPolicy(max_attempts=1, max_elapsed_s=15.0),
        )
        start = time.perf_counter()
        try:
            result = asyncio.run(run("Reply with exactly: pong", config=config))
            elapsed = time.perf_counter() - start
            response = ""
            if isinstance(result, dict):
                answers_blob = result.get("answers")
                if isinstance(answers_blob, list) and answers_blob:
                    response = str(answers_blob[0]).strip()
            durations.append(elapsed)
            answers.append(response)
            logger.info(
                "  run=%s status=ok elapsed=%.2fs response=%r",
                idx,
                elapsed,
                response[:60],
            )
        except Exception as exc:  # pragma: no cover - integration behavior
            elapsed = time.perf_counter() - start
            durations.append(elapsed)
            err = f"{type(exc).__name__}: {exc}"
            failures.append(err)
            logger.error("  run=%s status=error elapsed=%.2fs error=%s", idx, elapsed, err)

    return {
        "model": model,
        "durations": durations,
        "mean_s": _safe_mean(durations),
        "p95_s": _safe_p95(durations),
        "failures": failures,
        "answers": answers,
    }


def _run_summary_probe(model: str, api_key: str) -> dict[str, Any]:
    paper = {
        "title": "Toy study of efficient transformer routing",
        "abstract": (
            "We propose a compact routing mechanism for transformer blocks and "
            "evaluate quality and speed tradeoffs."
        ),
        "content": (
            "Introduction. We study efficient routing in transformer models. "
            "Method. We prune low-value experts and share projections. "
            "Results. We report quality parity with reduced compute. "
        )
        * 60,
    }
    config = {
        "type": "summary",
        "llm_provider": "openai",
        "api_key": api_key,
        "model": model,
        "max_input_tokens": 1500,
        "max_input_chars": 6000,
    }

    logger.info("Summary probe model=%s", model)
    start = time.perf_counter()
    try:
        summary = summarize_paper(paper, config)
        elapsed = time.perf_counter() - start
        logger.info(
            "  status=ok elapsed=%.2fs summary_len=%s",
            elapsed,
            len(summary or ""),
        )
        return {"model": model, "elapsed_s": elapsed, "error": None}
    except Exception as exc:  # pragma: no cover - defensive
        elapsed = time.perf_counter() - start
        err = f"{type(exc).__name__}: {exc}"
        logger.error("  status=error elapsed=%.2fs error=%s", elapsed, err)
        return {"model": model, "elapsed_s": elapsed, "error": err}


def _run_triage_probe(model: str, api_key: str) -> dict[str, Any]:
    papers = [
        {
            "title": "Transformer sparsification for long-context NLP",
            "abstract": "We compress attention with sparse expert routing.",
        },
        {
            "title": "Cataloging graph invariants in chemistry",
            "abstract": "This paper studies graph properties and molecules.",
        },
    ]
    full_config = {
        "triage": {
            "enabled": True,
            "llm_provider": "openai",
            "api_key": api_key,
            "model": model,
            "min_score": 50,
            "max_selected": 10,
        },
        "analyzer": {"llm_provider": "openai", "api_key": api_key},
        "processor": {"keywords": ["transformer", "nlp", "reasoning"]},
    }

    logger.info("Triage probe model=%s papers=%s", model, len(papers))
    start = time.perf_counter()
    try:
        shortlisted = triage_papers(papers, full_config)
        elapsed = time.perf_counter() - start
        logger.info(
            "  status=ok elapsed=%.2fs selected=%s",
            elapsed,
            len(shortlisted),
        )
        return {"model": model, "elapsed_s": elapsed, "error": None}
    except Exception as exc:  # pragma: no cover - defensive
        elapsed = time.perf_counter() - start
        err = f"{type(exc).__name__}: {exc}"
        logger.error("  status=error elapsed=%.2fs error=%s", elapsed, err)
        return {"model": model, "elapsed_s": elapsed, "error": err}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify OpenAI LLM integration and latency for paperweight.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gpt-5-nano", "gpt-5-mini"],
        help="Model IDs to test.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Direct tiny-prompt probes per model.",
    )
    parser.add_argument(
        "--dotenv-path",
        default=".env",
        help="Dotenv file to load before checking OPENAI_API_KEY.",
    )
    parser.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable containing the OpenAI API key.",
    )
    parser.add_argument(
        "--warn-threshold-seconds",
        type=float,
        default=6.0,
        help="Warn if direct-probe mean latency exceeds this value.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logs.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    _setup_logging(args.verbose)

    dotenv_path = Path(args.dotenv_path)
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path)
        logger.info("Loaded dotenv file: %s", dotenv_path)
    else:
        logger.info("Dotenv file not found at %s; using current environment", dotenv_path)

    api_key = os.getenv(args.api_key_env, "")
    if not api_key:
        logger.error("Missing API key: %s", args.api_key_env)
        return 2

    logger.info("Starting OpenAI verification models=%s", ",".join(args.models))
    had_failure = False

    for model in args.models:
        direct = _run_direct_probe(model, api_key, args.repeats)
        summary = _run_summary_probe(model, api_key)
        triage = _run_triage_probe(model, api_key)

        logger.info(
            "RESULT model=%s direct_mean=%.2fs direct_p95=%.2fs summary=%.2fs triage=%.2fs",
            model,
            direct["mean_s"],
            direct["p95_s"],
            float(summary["elapsed_s"]),
            float(triage["elapsed_s"]),
        )

        if direct["failures"] or summary["error"] or triage["error"]:
            had_failure = True

        if float(direct["mean_s"]) > float(args.warn_threshold_seconds):
            logger.warning(
                "Direct probe mean latency %.2fs exceeded threshold %.2fs for model=%s",
                direct["mean_s"],
                args.warn_threshold_seconds,
                model,
            )

    return 1 if had_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
