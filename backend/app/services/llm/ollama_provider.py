"""Ollama LLM provider — NO silent fallback to mock.  Raises on failure."""

import json
import logging
from typing import Any, Dict, Optional

import httpx

from backend.app.core.config import settings
from backend.app.services.llm.base import BaseLLMProvider, LLMProviderError, with_retries
from backend.app.services.llm.factory import robust_json_parse

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL

    @with_retries
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None,
                      temperature: Optional[float] = None,
                      max_tokens: Optional[int] = None) -> str:
        with httpx.Client(timeout=120.0) as client:
            res = client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": system_prompt or "",
                    "stream": False,
                    "options": {
                        "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
                        "num_predict": max_tokens or settings.LLM_MAX_TOKENS,
                    },
                },
            )
            if res.status_code != 200:
                raise LLMProviderError(f"Ollama returned HTTP {res.status_code}: {res.text[:300]}")
            return res.json().get("response", "")

    @with_retries
    def generate_json(self, prompt: str, system_prompt: Optional[str] = None,
                      schema: Optional[Dict[str, Any]] = None,
                      temperature: Optional[float] = None,
                      max_tokens: Optional[int] = None) -> Dict[str, Any]:
        with httpx.Client(timeout=120.0) as client:
            res = client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt + "\nRespond with valid JSON only.",
                    "system": system_prompt or "",
                    "format": "json",
                    "stream": False,
                    "options": {
                        "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
                        "num_predict": max_tokens or settings.LLM_MAX_TOKENS,
                    },
                },
            )
            if res.status_code != 200:
                raise LLMProviderError(f"Ollama returned HTTP {res.status_code}: {res.text[:300]}")
            raw = res.json().get("response", "{}")
            return robust_json_parse(raw)
