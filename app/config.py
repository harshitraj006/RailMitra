"""Application configuration module using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """RailMitra application settings loaded from environment or .env file."""

    APP_NAME: str = "RailMitra"
    APP_VERSION: str = "0.1.0"
    DEMO_MODE: bool = True
    TTE_KEY: str = "tte-demo-key"
    OTP_EXPIRY_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 3
    OTP_LOCK_MINUTES: int = 10
    REQUEST_LIMIT: int = 3
    DATABASE_URL: str = "sqlite+aiosqlite:///./railmitra.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_async_db_url(cls, v: str) -> str:
        """Ensure database URL uses async driver compatible with SQLAlchemy 2.x async engine."""
        if not v:
            return "sqlite+aiosqlite:///./railmitra.db"
        if v.startswith("sqlite:///") and not v.startswith("sqlite+aiosqlite:///"):
            return v.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        if v.startswith("postgresql://") and not v.startswith("postgresql+asyncpg://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


settings = Settings()
