from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore" # ignore unknown
    )

    # ----------------
    # Telegram
    # ----------------
    telegram_bot_token: str = ""

    # ----------------
    # Email (GreenMail)
    # ----------------
    smtp_host: str = "localhost"
    smtp_port: int = 3025
    imap_host: str = "localhost"
    imap_port: int = 3143
    email_user: str = "test@taskboard.local"
    email_password: str = "test"
    email_address: str = "test@taskboard.local"
    email_poll_interval: int = 5

    # ----------------
    # App
    # ----------------
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]


# ----------------
# Singleton
# ----------------
@lru_cache
def get_settings():
    return Settings()