"""
Anthropic Claude Provider implementation.
"""
import json
import logging
from typing import Any, Dict, Optional
import httpx

from backend.app.services.llm.base import BaseLLMProvider, LLMProviderError, with_retries
from backend.app.services.llm.factory import robust_json_parse
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "ANTHROPIC_API_KEY", None)
        self.model = model or getattr(settings, "ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        if not self.api_key:
            raise LLMProviderError("Anthropic API key is required.")

    @with_retries
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None,
                      temperature: Optional[float] = None,
                      max_tokens: Optional[int] = None) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        body = {
            "model": self.model,
            "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
            "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
            "messages": [{"role": "user", "content": prompt}]
        }
        if system_prompt:
            body["system"] = system_prompt

        with httpx.Client(timeout=120.0) as client:
            resp = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
            if resp.status_code != 200:
                raise LLMProviderError(f"Anthropic error {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            return data["content"][0]["text"]

    @with_retries
    def generate_json(self, prompt: str, system_prompt: Optional[str] = None,
                      schema: Optional[Dict[str, Any]] = None,
                      temperature: Optional[float] = None,
                      max_tokens: Optional[int] = None) -> Dict[str, Any]:
        json_prompt = prompt + "\n\nCRITICAL: Respond ONLY with valid JSON. Do not include markdown code block formatting."
        raw_text = self.generate_text(json_prompt, system_prompt=system_prompt, temperature=temperature, max_tokens=max_tokens)
        return robust_json_parse(raw_text)
