from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    POSTGRES_DSN: str = os.environ.get("DATABASE_URL")

    # Security
    JWT_SECRET: str = os.environ.get("JWT_SECRET")
    JWT_ALG: str = os.environ.get("JWT_ALG")
    JWT_EXPIRE_MINUTES: int = os.environ.get("JWT_EXPIRE_MINUTES")

    # SaaS defaults
    DEFAULT_PLAN: str = "free"
    DEFAULT_SUB_STATUS: str = "active"

settings = Settings()