from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    POSTGRES_DSN: str = os.environ.get("DATABASE_URL")

    # Security
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALG: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # SaaS defaults
    DEFAULT_PLAN: str = "free"
    DEFAULT_SUB_STATUS: str = "active"

    # Analysis defaults (MVP)
    DEFAULT_MODEL_NAME: str = "rubert-tiny2"
    DEFAULT_MODEL_VERSION: str = "v1"

settings = Settings()