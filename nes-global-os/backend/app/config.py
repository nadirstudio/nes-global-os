"""Runtime configuration. Everything sensitive comes from the environment (never the frontend)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    env: str = os.getenv("NES_ENV", "development")
    database_url: str = os.getenv(
        "NES_DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:5432/nesos"
    )
    redis_url: str = os.getenv("NES_REDIS_URL", "redis://127.0.0.1:6379/0")
    # Signs session tokens. MUST be a long random value in production.
    jwt_secret: str = os.getenv("NES_JWT_SECRET", "dev-only-change-me-" + "x" * 32)
    jwt_ttl_minutes: int = int(os.getenv("NES_JWT_TTL_MINUTES", "720"))
    # Fernet key used to encrypt secrets (AI API keys, MFA seeds) at rest in PostgreSQL.
    master_key: str | None = os.getenv("NES_MASTER_KEY")
    cookie_secure: bool = _bool("NES_COOKIE_SECURE", False)
    timezone: str = os.getenv("NES_TIMEZONE", "Asia/Karachi")
    default_currency: str = os.getenv("NES_DEFAULT_CURRENCY", "PKR")
    login_rate_limit_per_15m: int = int(os.getenv("NES_LOGIN_RATE_LIMIT", "10"))
    api_rate_limit_per_min: int = int(os.getenv("NES_API_RATE_LIMIT", "600"))
    site_role: str = os.getenv("NES_SITE_ROLE", "local")  # local | cloud
    files_dir: str = os.getenv("NES_FILES_DIR", "/data/files")
    max_upload_mb: int = int(os.getenv("NES_MAX_UPLOAD_MB", "20"))
    cors_origins: list[str] = field(
        default_factory=lambda: [o for o in os.getenv("NES_CORS_ORIGINS", "https://localhost").split(",") if o]
    )

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


settings = Settings()
