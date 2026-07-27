from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.1.0"


class Settings(BaseSettings):
    """Application configuration, entirely driven by environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "revly-budgeting"
    version: str = APP_VERSION

    # sqlite default keeps a single container self-contained; any SQLAlchemy URL works.
    database_url: str = "sqlite+aiosqlite:///./data/revly.db"
    data_dir: Path = Path("./data")
    upload_dir: Path | None = None

    secret_key: str | None = None
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    allowed_origins: str = ""
    default_locale: str = "de"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "revly@localhost"
    smtp_use_tls: bool = True

    scheduler_interval_seconds: int = 3600

    @property
    def sqlalchemy_url(self) -> str:
        """Normalize the URL to an async driver so plain postgres:// / sqlite:// URLs work."""
        url = self.database_url
        if url.startswith("sqlite://"):
            url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def uploads_path(self) -> Path:
        return self.upload_dir if self.upload_dir else self.data_dir / "uploads"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    def resolve_secret_key(self) -> str:
        """Use SECRET_KEY from env, otherwise persist a generated key under the data dir
        so sessions survive container restarts."""
        if self.secret_key:
            return self.secret_key
        self.data_dir.mkdir(parents=True, exist_ok=True)
        key_file = self.data_dir / ".secret_key"
        if key_file.exists():
            return key_file.read_text(encoding="utf-8").strip()
        key = secrets.token_urlsafe(48)
        key_file.write_text(key, encoding="utf-8")
        return key


@lru_cache
def get_settings() -> Settings:
    return Settings()
