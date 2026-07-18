"""
Application configuration, loaded from environment variables.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Financial Workflow Automation Platform"
    ENV: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/workflow_db"

    # Auth / JWT
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_use_a_random_64_char_string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Approval workflow thresholds (amount in USD -> required approval levels)
    APPROVAL_THRESHOLD_LEVEL_1: float = 1000.0      # Manager only
    APPROVAL_THRESHOLD_LEVEL_2: float = 10000.0     # Manager + Finance
    APPROVAL_THRESHOLD_LEVEL_3: float = 50000.0     # Manager + Finance + Admin/CFO

    # Notifications
    SMTP_HOST: str = "smtp.example.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "notifications@example.com"
    SMTP_PASSWORD: str = "changeme"
    SMTP_FROM: str = "Financial Workflow <notifications@example.com>"
    NOTIFICATIONS_ENABLED: bool = False  # set True once SMTP is configured

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
