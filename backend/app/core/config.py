import logging
from pathlib import Path
from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("req-to-code.config")

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "Req-to-Code"
    APP_SUBTITLE: str = "AI Assistant"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = "development"
    
    # Storage Paths
    BASE_DIR: Path = BASE_DIR
    STORAGE_DIR: Path = BASE_DIR / "storage"
    UPLOAD_DIR: Path = BASE_DIR / "storage" / "uploads"
    CHROMA_DIR: Path = BASE_DIR / "storage" / "chroma_db"
    GENERATED_DIR: Path = BASE_DIR / "storage" / "generated_code"

    # Database (explicit string takes precedence; None defaults to SQLite inside STORAGE_DIR)
    DATABASE_URL: Optional[str] = None
    
    # LLM Settings
    LLM_PROVIDER: str = "gemini"  # mock | gemini | openai | anthropic | ollama
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: Optional[str] = "gemini-3.5-flash-lite"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 8192
    LLM_EXTRACTION_MODEL: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"
    
    # Knowledge Graph Neo4j (optional)
    NEO4J_URI: Optional[str] = None
    NEO4J_USER: Optional[str] = None
    NEO4J_PASSWORD: Optional[str] = None
    
    # Max file upload size in MB (e.g., 25MB)
    MAX_UPLOAD_SIZE_MB: int = 25

    @classmethod
    def _canonicalize_sqlite_url(cls, v: str, storage_dir: Path) -> str:
        """Resolve file-based SQLite database paths to canonical absolute paths independent of cwd."""
        if not v or not v.startswith("sqlite"):
            return v

        # Preserve in-memory databases used by tests
        if ":memory:" in v or v in ("sqlite://", "sqlite:///"):
            return v

        # Extract path part
        prefix = "sqlite:///"
        if v.startswith(prefix):
            raw_path = v[len(prefix):]
        elif v.startswith("sqlite://"):
            raw_path = v[len("sqlite://"):]
        else:
            return v

        p = Path(raw_path)
        if p.is_absolute():
            return f"sqlite:///{p.as_posix()}"

        # Relative SQLite path: resolve canonically regardless of cwd
        project_root = BASE_DIR.parent
        # 1. Try relative to project root (e.g., 'backend/storage/req_to_code.db')
        resolved = (project_root / p).resolve()

        # 2. Try relative to backend dir (e.g., 'storage/req_to_code.db')
        if not resolved.exists():
            backend_resolved = (BASE_DIR / p).resolve()
            if backend_resolved.exists():
                resolved = backend_resolved
            else:
                # 3. Direct match in effective storage_dir
                storage_resolved = (storage_dir / p.name).resolve()
                if storage_resolved.exists():
                    resolved = storage_resolved

        return f"sqlite:///{resolved.as_posix()}"

    @model_validator(mode="after")
    def resolve_paths_and_database(self) -> "Settings":
        """Resolve effective storage directories and database URL consistently."""
        # 1. Resolve effective STORAGE_DIR
        self.STORAGE_DIR = Path(self.STORAGE_DIR).resolve()

        # 2. Derive storage subdirectories strictly from effective STORAGE_DIR
        self.UPLOAD_DIR = (self.STORAGE_DIR / "uploads").resolve()
        self.CHROMA_DIR = (self.STORAGE_DIR / "chroma_db").resolve()
        self.GENERATED_DIR = (self.STORAGE_DIR / "generated_code").resolve()

        # Ensure all storage directories exist (fail fast if uncreatable)
        for d in [self.STORAGE_DIR, self.UPLOAD_DIR, self.CHROMA_DIR, self.GENERATED_DIR]:
            try:
                d.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise RuntimeError(
                    f"Failed to create required storage directory '{d}': {e}. "
                    f"Please verify permissions and that STORAGE_DIR is writable."
                ) from e

        # 3. Resolve DATABASE_URL
        if not self.DATABASE_URL:
            # Default SQLite database derived directly from effective STORAGE_DIR
            self.DATABASE_URL = f"sqlite:///{(self.STORAGE_DIR / 'req_to_code.db').as_posix()}"
        else:
            url = self.DATABASE_URL.strip()
            # Normalize Render PostgreSQL scheme (postgres:// -> postgresql://)
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            # Canonicalize SQLite paths
            if url.startswith("sqlite"):
                url = self._canonicalize_sqlite_url(url, self.STORAGE_DIR)
            self.DATABASE_URL = url

        return self

    # JWT Authentication & Security
    JWT_SECRET_KEY: str = "req-to-code-dev-secret-key-32-chars-replace-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
    
    # SMTP / Password Reset Settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_FROM_NAME: str = "ReqToCode AI"
    SMTP_TLS: bool = True
    FRONTEND_URL: str = "http://localhost:5173"
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 15
    PASSWORD_RESET_COOLDOWN_SECONDS: int = 60
    ALLOW_DEV_EMAIL_LOG: bool = True

    @property
    def clean_smtp_user(self) -> Optional[str]:
        if not self.SMTP_USER:
            return None
        return self.SMTP_USER.strip().strip("'\"")

    @property
    def clean_smtp_password(self) -> Optional[str]:
        if not self.SMTP_PASSWORD:
            return None
        pwd = self.SMTP_PASSWORD.strip().strip("'\"")
        # Google App Passwords are 16 chars generated with spaces like 'abcd efgh ijkl mnop'
        return pwd.replace(" ", "")

    @property
    def effective_from_email(self) -> str:
        user = self.clean_smtp_user
        if self.SMTP_FROM_EMAIL:
            clean_from = self.SMTP_FROM_EMAIL.strip().strip("'\"")
            if clean_from and not any(p in clean_from.lower() for p in ["your-sender", "your_email", "example.com"]):
                return clean_from
        if user and not any(p in user.lower() for p in ["your-sender", "your_email", "example.com"]):
            return user
        return "noreply@reqtocode.ai"
    
    @property
    def allowed_cors_origins(self) -> list[str]:
        if not self.CORS_ORIGINS:
            return ["http://localhost:5173", "http://127.0.0.1:5173"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
    
    model_config = SettingsConfigDict(
        env_file=[
            str(BASE_DIR / ".env"),
            str(BASE_DIR.parent / ".env"),
            str(BASE_DIR.parent / "backend" / ".env")
        ],
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Module-level exports for backward compatibility (synchronized with effective settings)
STORAGE_DIR = settings.STORAGE_DIR
UPLOAD_DIR = settings.UPLOAD_DIR
CHROMA_DIR = settings.CHROMA_DIR
GENERATED_DIR = settings.GENERATED_DIR

def reload_settings() -> Settings:
    """Reload settings from disk to dynamically capture .env changes without server restart."""
    global settings, STORAGE_DIR, UPLOAD_DIR, CHROMA_DIR, GENERATED_DIR
    settings = Settings()
    STORAGE_DIR = settings.STORAGE_DIR
    UPLOAD_DIR = settings.UPLOAD_DIR
    CHROMA_DIR = settings.CHROMA_DIR
    GENERATED_DIR = settings.GENERATED_DIR
    return settings
