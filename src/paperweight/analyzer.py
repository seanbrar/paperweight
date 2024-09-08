import logging
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from SimplerLLM.language.llm import (  # type: ignore
    LLM,
    LLMProvider,
)

from paperweight.utils import count_tokens

load_dotenv()

logger = logging.getLogger(__name__)

def get_api_key(provider: str) -> Optional[str]:
    """Safely retrieve API key for the given provider."""
    key = os.getenv(f'{provider.upper()}_API_KEY')
    if not key:
        logger.debug(f"No API key found for {provider}. Some functionality may be limited.")
    return key

def get_abstracts(processed_papers, config):
    analysis_type = config.get('type', 'abstract')

    if analysis_type == 'abstract':
        return [paper['abstract'] for paper in processed_papers]
    elif analysis_type == 'summary':
        return [summarize_paper(paper, config) for paper in processed_papers]
    else:
        raise ValueError(f"Unknown analysis type: {analysis_type}")

def summarize_paper(paper: Dict[str, Any], config: Dict[str, Any]) -> str:
    llm_provider = config.get('analyzer', {}).get('llm_provider', 'openai').lower()

    if llm_provider not in ['openai', 'gemini']:
        logger.warning(f"Unsupported LLM provider: {llm_provider}. Falling back to abstract.")
        return paper['abstract']

    api_key = get_api_key(llm_provider)
    if not api_key:
        logger.warning(f"No API key available for {llm_provider}. Falling back to abstract.")
        return paper['abstract']

    try:
        llm_instance = create_llm_instance(llm_provider, api_key)
        prompt = f"Write a concise, accurate summary of the following paper's content in about 3-5 sentences:\n\n```{paper['content']}```"

        input_tokens = count_tokens(prompt)
        logger.info(f"Input token count: {input_tokens}")

        response = llm_instance.generate_response(prompt=prompt)

        output_tokens = count_tokens(response)
        logger.info(f"Output token count: {output_tokens}")

        return response
    except Exception as e:
        logger.error(f"Error summarizing paper: {e}", exc_info=True)
        return paper['abstract']

def create_llm_instance(provider: str, api_key: str) -> LLM:
    if provider == 'openai':
        return LLM.create(provider=LLMProvider.OPENAI, model_name="gpt-4o-mini", api_key=api_key)
    elif provider == 'gemini':
        return LLM.create(provider=LLMProvider.GEMINI, model_name="gemini-1.5-flash", api_key=api_key)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
