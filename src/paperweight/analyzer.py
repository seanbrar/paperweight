"""Module for analyzing and summarizing academic papers.

This module provides functionality for analyzing paper content using LLMs (Language Model Models)
and extracting relevant information. It supports different analysis types including abstract
extraction and paper summarization using various LLM providers.
"""

import logging
from typing import Any, Dict

from SimplerLLM.language.llm import (  # type: ignore
    LLM,
    LLMProvider,
)
from tenacity import retry, stop_after_attempt, wait_exponential

from paperweight.utils import count_tokens

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


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def summarize_paper(paper: Dict[str, Any], config: Dict[str, Any]) -> str:
    """Generate a summary of a paper using an LLM.

    Args:
        paper: Dictionary containing paper data including content and metadata.
        config: Configuration dictionary containing LLM settings.

    Returns:
        A string containing the generated summary.

    Raises:
        ValueError: If no valid LLM provider or API key is available.
    """
    llm_provider = config.get("analyzer", {}).get("llm_provider", "openai").lower()
    api_key = config.get("analyzer", {}).get("api_key")

    if llm_provider not in ["openai", "gemini"] or not api_key:
        logger.warning(
            f"No valid LLM provider or API key available for {llm_provider}. Falling back to abstract."
        )
        return paper["abstract"]

    try:
        provider = LLMProvider[llm_provider.upper()]
        model_name = (
            "gpt-4o-mini" if provider == LLMProvider.OPENAI else "gemini-1.5-flash"
        )
        llm_instance = LLM.create(
            provider=provider, model_name=model_name, api_key=api_key
        )
        prompt = f"Write a concise, accurate summary of the following paper's content in about 3-5 sentences:\n\n```{paper['content']}```"

        input_tokens = count_tokens(prompt)
        logger.info(f"Input token count: {input_tokens}")

        response = llm_instance.generate_response(prompt=prompt)

        output_tokens = count_tokens(response)
        logger.info(f"Output token count: {output_tokens}")

        return response
    except Exception as e:
        logger.error(f"Error summarizing paper: {e}", exc_info=True)
        return paper["abstract"]


def create_llm_instance(provider: str, api_key: str) -> LLM:
    """Create an instance of the specified LLM provider.

    Args:
        provider: The name of the LLM provider ('openai' or 'gemini').
        api_key: API key for the specified provider.

    Returns:
        An initialized LLM instance.

    Raises:
        ValueError: If an unsupported provider is specified.
    """
    if provider == "openai":
        return LLM.create(
            provider=LLMProvider.OPENAI, model_name="gpt-4o-mini", api_key=api_key
        )
    elif provider == "gemini":
        return LLM.create(
            provider=LLMProvider.GEMINI, model_name="gemini-1.5-flash", api_key=api_key
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
