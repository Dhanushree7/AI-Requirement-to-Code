"""LLM provider factory and JSON parsing utilities."""

import re
import json
import logging
from typing import Any, Dict, Optional

from backend.app.core.config import settings
from backend.app.services.llm.base import BaseLLMProvider, LLMProviderError
from backend.app.services.key_storage_service import KeyStorageService

logger = logging.getLogger(__name__)


def get_llm_provider(provider_name: Optional[str] = None) -> BaseLLMProvider:
    """Factory to retrieve the configured or requested LLM provider.
    Priority:
    1. Saved key configuration from secure storage (UI)
    2. Environment variable settings
    """
    saved_cfg = KeyStorageService.get_config()
    
    if saved_cfg and not provider_name:
        provider = saved_cfg.get("provider", "mock").lower().strip()
        model = saved_cfg.get("model")
        api_key = saved_cfg.get("api_key")

        if provider == "gemini":
            from backend.app.services.llm.gemini_provider import GeminiProvider
            return GeminiProvider(api_key=api_key, model=model)
        elif provider == "openai":
            from backend.app.services.llm.openai_provider import OpenAIProvider
            return OpenAIProvider(api_key=api_key, model=model)
        elif provider == "anthropic":
            from backend.app.services.llm.anthropic_provider import AnthropicProvider
            return AnthropicProvider(api_key=api_key, model=model)
        elif provider == "ollama":
            from backend.app.services.llm.ollama_provider import OllamaProvider
            return OllamaProvider(model=model)
        elif provider == "mock":
            from backend.app.services.llm.mock_provider import MockProvider
            return MockProvider()

    provider = (provider_name or settings.LLM_PROVIDER).lower().strip()

    if provider == "gemini":
        from backend.app.services.llm.gemini_provider import GeminiProvider
        return GeminiProvider()
    elif provider == "openai":
        from backend.app.services.llm.openai_provider import OpenAIProvider
        return OpenAIProvider()
    elif provider == "anthropic":
        from backend.app.services.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    elif provider == "ollama":
        from backend.app.services.llm.ollama_provider import OllamaProvider
        return OllamaProvider()
    elif provider == "mock":
        from backend.app.services.llm.mock_provider import MockProvider
        return MockProvider()
    else:
        raise LLMProviderError(
            f"Unknown LLM provider '{provider}'. "
            f"Set LLM_PROVIDER to one of: mock, gemini, openai, anthropic, ollama."
        )


def get_extraction_provider() -> BaseLLMProvider:
    """Return a cheaper model for extraction if LLM_EXTRACTION_MODEL is set,
    otherwise fall back to the main provider."""
    extraction_model = settings.LLM_EXTRACTION_MODEL
    if not extraction_model:
        return get_llm_provider()

    provider_name = settings.LLM_PROVIDER.lower().strip()
    if provider_name == "gemini":
        from backend.app.services.llm.gemini_provider import GeminiProvider
        return GeminiProvider(model=extraction_model)
    elif provider_name == "openai":
        from backend.app.services.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(model=extraction_model)
    elif provider_name == "ollama":
        from backend.app.services.llm.ollama_provider import OllamaProvider
        return OllamaProvider(model=extraction_model)
    else:
        return get_llm_provider()


def robust_json_parse(text: str) -> Dict[str, Any]:
    """Clean markdown artifacts, strip trailing commas, and parse JSON robustly."""
    if not text or not text.strip():
        return {}

    cleaned = text.strip()

    # Strip markdown code fences
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Extract first outer curly braces or brackets
    match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # Strip trailing commas
    repaired = re.sub(r",\s*([\]}])", r"\1", cleaned)
    try:
        return json.loads(repaired)
    except Exception as e:
        logger.error(f"Failed to parse JSON: {e}. Raw text snippet: {cleaned[:200]}")
        raise ValueError(f"Invalid JSON response: {e}")
