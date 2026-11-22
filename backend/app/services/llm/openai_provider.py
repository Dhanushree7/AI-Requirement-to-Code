"""OpenAI LLM provider — NO silent fallback to mock.  Raises on failure."""

import json
import logging
from typing import Any, Dict, Optional

from backend.app.core.config import settings
from backend.app.services.llm.base import BaseLLMProvider, LLMProviderError, with_retries
from backend.app.services.llm.factory import robust_json_parse

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL
        if not self.api_key:
            raise LLMProviderError(
                "OpenAI API key not configured. Set OPENAI_API_KEY in .env "
                "or switch LLM_PROVIDER to 'mock'."
            )

    @with_retries
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None,
                      temperature: Optional[float] = None,
                      max_tokens: Optional[int] = None) -> str:
        import openai

        client = openai.OpenAI(api_key=self.api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature if temperature is not None else settings.LLM_TEMPERATURE,
            max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
        )
        return response.choices[0].message.content or ""

    @with_retries
    def generate_json(self, prompt: str, system_prompt: Optional[str] = None,
                      schema: Optional[Dict[str, Any]] = None,
                      temperature: Optional[float] = None,
                      max_tokens: Optional[int] = None) -> Dict[str, Any]:
        import openai

        client = openai.OpenAI(api_key=self.api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=temperature if temperature is not None else settings.LLM_TEMPERATURE,
            max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
        )
        raw = response.choices[0].message.content or "{}"
        return robust_json_parse(raw)
