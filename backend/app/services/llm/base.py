"""Base LLM provider interface with retry, backoff, Pydantic validation, and caching."""

import hashlib
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory LRU-style cache: (project_id, artifact_type, input_hash) -> result
# ---------------------------------------------------------------------------
_result_cache: Dict[str, Any] = {}
_CACHE_MAX = 256


def _cache_key(project_id: str, artifact_type: str, prompt: str) -> str:
    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    return f"{project_id}:{artifact_type}:{h}"


def cache_get(project_id: str, artifact_type: str, prompt: str) -> Optional[Dict[str, Any]]:
    return _result_cache.get(_cache_key(project_id, artifact_type, prompt))


def cache_put(project_id: str, artifact_type: str, prompt: str, value: Dict[str, Any]) -> None:
    if len(_result_cache) >= _CACHE_MAX:
        # evict oldest quarter
        keys = list(_result_cache.keys())
        for k in keys[: _CACHE_MAX // 4]:
            _result_cache.pop(k, None)
    _result_cache[_cache_key(project_id, artifact_type, prompt)] = value


def cache_invalidate_project(project_id: str) -> None:
    """Remove all cached results for a project."""
    to_remove = [k for k in _result_cache if k.startswith(f"{project_id}:")]
    for k in to_remove:
        _result_cache.pop(k, None)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------
class LLMProviderError(Exception):
    """Raised when the LLM provider fails after retries.  NEVER silently fall back to mock."""
    pass


class LLMRateLimitError(LLMProviderError):
    """Raised on 429 / quota errors."""
    pass


class LLMValidationError(LLMProviderError):
    """Raised when JSON output fails Pydantic validation after retries."""
    pass


class LLMTokenLimitError(LLMProviderError):
    """Raised when the LLM output reaches the maximum token limit and is truncated."""
    pass


# ---------------------------------------------------------------------------
# Base provider
# ---------------------------------------------------------------------------
class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None,
                      temperature: Optional[float] = None,
                      max_tokens: Optional[int] = None) -> str:
        """Generate raw text response from prompt."""
        pass

    @abstractmethod
    def generate_json(self, prompt: str, system_prompt: Optional[str] = None,
                      schema: Optional[Dict[str, Any]] = None,
                      temperature: Optional[float] = None,
                      max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """Generate structured JSON response adhering to optional schema."""
        pass

    def health_check(self) -> Dict[str, Any]:
        """One tiny test call to verify the provider is reachable.
        Returns {"provider": str, "model": str, "success": bool, "error": str|None}
        """
        try:
            result = self.generate_text("Respond with exactly: OK", temperature=0.0)
            return {"provider": self.provider_name, "model": self.model_name,
                    "success": bool(result), "error": None}
        except Exception as e:
            return {"provider": self.provider_name, "model": self.model_name,
                    "success": False, "error": str(e)}

    @property
    def provider_name(self) -> str:
        return self.__class__.__name__.replace("Provider", "").lower()

    @property
    def model_name(self) -> str:
        return getattr(self, "model", "unknown")

    # ------------------------------------------------------------------
    # Validated JSON generation with Pydantic + retry
    # ------------------------------------------------------------------
    def generate_validated_json(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_retries: int = 2,
    ) -> BaseModel:
        """Call generate_json, validate with Pydantic model, retry up to
        max_retries times including JSON parsing (ValueError) or schema validation
        errors (ValidationError) in the retry prompt."""
        last_error: Optional[str] = None
        for attempt in range(1 + max_retries):
            retry_prompt = prompt
            if last_error and attempt > 0:
                retry_prompt += (
                    f"\n\n--- PREVIOUS ATTEMPT FAILED ---\n"
                    f"Error: {last_error}\n"
                    f"Ensure the output is strictly valid JSON conforming to the schema and try again."
                )
            try:
                raw = self.generate_json(
                    retry_prompt,
                    system_prompt=system_prompt,
                    schema=response_model,
                    temperature=temperature,
                )
                if isinstance(raw, str):
                    from backend.app.services.llm.factory import robust_json_parse
                    raw = robust_json_parse(raw)
                return response_model.model_validate(raw)
            except (ValidationError, ValueError, LLMTokenLimitError) as err:
                err_str = str(err)
                # Keep error message concise and safe (sanitize sensitive credential/token patterns)
                first_line = err_str.split("\n")[0] if "\n" in err_str else err_str
                clean_err = re.sub(r"(AIza[0-9A-Za-z-_]{35}|sk-[0-9A-Za-z]{20,})", "[REDACTED]", first_line)
                if len(clean_err) > 300:
                    clean_err = clean_err[:300] + "..."
                last_error = clean_err
                logger.warning(
                    f"JSON validation/parsing/token-limit failed (attempt {attempt + 1}/{1 + max_retries}): {last_error}"
                )

        raise LLMValidationError(
            f"JSON validation/parsing failed after {1 + max_retries} attempts: {last_error}"
        )


# ---------------------------------------------------------------------------
# Retry decorator with exponential backoff for rate limits / timeouts
# ---------------------------------------------------------------------------
RATE_LIMIT_KEYWORDS = ("429", "rate limit", "quota", "resource exhausted",
                       "too many requests", "overloaded")


def with_retries(func):
    """Decorator for provider generate_* methods.
    On rate-limit / timeout: exponential backoff up to 3 retries.
    On other errors: raise LLMProviderError immediately (NO mock fallback).
    """
    def wrapper(*args, **kwargs):
        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                err_lower = str(e).lower()
                is_rate_limit = any(kw in err_lower for kw in RATE_LIMIT_KEYWORDS)
                is_timeout = "timeout" in err_lower or "timed out" in err_lower

                if (is_rate_limit or is_timeout) and attempt < max_retries:
                    wait = (2 ** attempt) * 1.5  # 1.5, 3, 6 seconds
                    logger.warning(f"Rate limit / timeout on attempt {attempt+1}, "
                                   f"retrying in {wait:.1f}s: {e}")
                    time.sleep(wait)
                    continue

                if is_rate_limit:
                    raise LLMRateLimitError(
                        f"Rate limit exceeded after {max_retries} retries: {e}"
                    ) from e
                if isinstance(e, LLMProviderError):
                    raise e
                raise LLMProviderError(f"LLM provider error: {e}") from e
    return wrapper
