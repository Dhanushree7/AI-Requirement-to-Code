"""LLM health-check router."""

import logging
import re
from fastapi import APIRouter

from backend.app.services.llm.factory import get_llm_provider
from backend.app.services.llm.base import LLMProviderError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["llm"])

def _sanitize_error(msg: str) -> str:
    cleaned = re.sub(r'(Bearer\s+|key=|api_key=)[A-Za-z0-9_\-\.]{8,}', r'\1[REDACTED]', str(msg))
    cleaned = re.sub(r'sk-[A-Za-z0-9_\-\.]{10,}', '[REDACTED]', cleaned)
    cleaned = re.sub(r'AIza[A-Za-z0-9_\-\.]{10,}', '[REDACTED]', cleaned)
    return cleaned[:200]

@router.get("/health")
def llm_health():
    """One tiny test call to the configured provider.
    Returns {provider, model, success, error}.
    """
    try:
        provider = get_llm_provider()
        res = provider.health_check()
        if isinstance(res, dict) and res.get("error"):
            res["error"] = _sanitize_error(res["error"])
        return res
    except LLMProviderError as e:
        return {
            "provider": "unknown",
            "model": "unknown",
            "success": False,
            "error": _sanitize_error(str(e)),
        }
