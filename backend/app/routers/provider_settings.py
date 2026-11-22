"""
Provider credentials configuration and verification router.
Saves and tests keys securely without exposing them in responses.
Modifications are restricted to administrators (is_superuser=True).
"""
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.core.security import get_current_user, get_current_admin_user
from backend.app.models.user import User
from backend.app.services.key_storage_service import KeyStorageService

router = APIRouter(prefix="/settings/provider", tags=["settings"])

class ProviderConfigRequest(BaseModel):
    provider: str
    model: str
    api_key: str

@router.get("/status")
def get_provider_status(current_user: User = Depends(get_current_user)):
    """Return provider configuration status with masked key (accessible to authenticated users)."""
    return KeyStorageService.get_public_status()

@router.post("/test-and-save")
def test_and_save_provider(
    payload: ProviderConfigRequest,
    admin_user: User = Depends(get_current_admin_user)
):
    """Test the API key with a minimal call, then securely persist it at rest (admin only)."""
    provider_name = payload.provider.lower().strip()
    model = payload.model.strip()
    key = payload.api_key.strip()

    if not key:
        raise HTTPException(status_code=400, detail="API key is required.")

    # 1. Verification test call
    try:
        if provider_name == "gemini":
            from backend.app.services.llm.gemini_provider import GeminiProvider
            p = GeminiProvider(api_key=key, model=model)
            res = p.health_check()
            if not res["success"]:
                raise HTTPException(status_code=400, detail=f"Gemini connection failed: {res.get('error')}")

        elif provider_name == "openai":
            from backend.app.services.llm.openai_provider import OpenAIProvider
            p = OpenAIProvider(api_key=key, model=model)
            res = p.health_check()
            if not res["success"]:
                raise HTTPException(status_code=400, detail=f"OpenAI connection failed: {res.get('error')}")

        elif provider_name == "anthropic":
            from backend.app.services.llm.anthropic_provider import AnthropicProvider
            p = AnthropicProvider(api_key=key, model=model)
            res = p.health_check()
            if not res["success"]:
                raise HTTPException(status_code=400, detail=f"Anthropic connection failed: {res.get('error')}")
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider_name}")

    except HTTPException:
        raise
    except Exception as e:
        err_msg = str(e)
        if "quota" in err_msg.lower() or "429" in err_msg:
            detail = "Quota exceeded or rate limit reached on provider."
        elif "invalid" in err_msg.lower() or "auth" in err_msg.lower() or "401" in err_msg:
            detail = "Invalid API key or unauthorized access."
        else:
            detail = f"Connection failed: {err_msg[:200]}"
        raise HTTPException(status_code=400, detail=detail)

    # 2. Persist encrypted
    KeyStorageService.save_key(provider=provider_name, model=model, api_key=key)

    return {
        "success": True,
        "message": f"Successfully connected and verified {provider_name} ({model})",
        "status": KeyStorageService.get_public_status()
    }

@router.delete("")
def delete_provider_key(admin_user: User = Depends(get_current_admin_user)):
    """Remove stored key (admin only)."""
    KeyStorageService.delete_key()
    return {"success": True, "message": "API key deleted"}
