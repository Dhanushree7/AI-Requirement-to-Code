"""
Secure key storage service.
Encrypts API keys at rest using Fernet symmetric encryption and stores them in storage/secrets/.
Never exposes raw keys in responses or logs.
"""
import os
import json
import base64
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

SECRETS_DIR = settings.STORAGE_DIR / "secrets"
SECRETS_DIR.mkdir(parents=True, exist_ok=True)
KEY_FILE = SECRETS_DIR / "provider_key.enc"
SALT_FILE = SECRETS_DIR / ".salt"

def _get_or_create_salt() -> bytes:
    if not SALT_FILE.exists():
        salt = os.urandom(16)
        SALT_FILE.write_bytes(salt)
        return salt
    return SALT_FILE.read_bytes()

def _get_cipher() -> Fernet:
    salt = _get_or_create_salt()
    # Derives encryption key from machine/app seed
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    derived_key = base64.urlsafe_b64encode(kdf.derive(b"req_to_code_secret_store_v1"))
    return Fernet(derived_key)

def mask_key(key: Optional[str]) -> str:
    """Mask key for UI display (e.g., sk-...a3f9)."""
    if not key or len(key) < 8:
        return "••••••••"
    prefix = key[:3] if key.startswith("sk-") or key.startswith("AI") else key[:4]
    suffix = key[-4:]
    return f"{prefix}...{suffix}"

class KeyStorageService:
    @staticmethod
    def save_key(provider: str, model: str, api_key: str):
        """Encrypt and save key at rest."""
        cipher = _get_cipher()
        data = {
            "provider": provider.lower().strip(),
            "model": model.strip(),
            "api_key": api_key.strip()
        }
        encrypted = cipher.encrypt(json.dumps(data).encode("utf-8"))
        KEY_FILE.write_bytes(encrypted)

    @staticmethod
    def get_config() -> Optional[Dict[str, str]]:
        """Retrieve decrypted configuration for internal LLM calls only."""
        if not KEY_FILE.exists():
            return None
        try:
            cipher = _get_cipher()
            decrypted = cipher.decrypt(KEY_FILE.read_bytes())
            return json.loads(decrypted.decode("utf-8"))
        except Exception as e:
            logger.error("Failed to decrypt API key store.")
            return None

    @staticmethod
    def get_public_status() -> Dict[str, Any]:
        """Return provider configuration status without exposing credentials or key fragments."""
        config = KeyStorageService.get_config()
        if not config:
            # Check environment variables fallback
            env_provider = getattr(settings, "LLM_PROVIDER", "mock")
            has_env_key = bool(
                getattr(settings, "GEMINI_API_KEY", None)
                or getattr(settings, "OPENAI_API_KEY", None)
            )
            return {
                "configured": has_env_key or env_provider == "mock",
                "provider": env_provider,
                "model": getattr(settings, "GEMINI_MODEL", "gemini-1.5-pro"),
                "is_mock": env_provider == "mock"
            }

        return {
            "configured": True,
            "provider": config.get("provider"),
            "model": config.get("model"),
            "is_mock": False
        }

    @staticmethod
    def delete_key():
        """Remove key from storage."""
        if KEY_FILE.exists():
            KEY_FILE.unlink()
