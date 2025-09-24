"""
Application configuration using Pydantic settings
"""

import os
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables"""

    # Application
    app_name: str = "LabelSquor API"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql://postgres:Z9f%2BhP%24E8-r%23DdU@db.snjmkslhsyesshixytfw.supabase.co:5432/postgres"
    )
    database_pool_url: Optional[str] = os.getenv("DATABASE_POOL_URL")
    db_echo: bool = False

    # Connection pool settings
    db_pool_size: int = 20
    db_max_overflow: int = 0
    db_pool_pre_ping: bool = True

    # Redis Cache
    redis_url: Optional[str] = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    cache_ttl: int = 300  # 5 minutes

    # Security
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Add missing config attributes for main.py
    PROJECT_NAME: str = "LabelSquor API"
    VERSION: str = "1.0.1"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    SENTRY_DSN: Optional[str] = None
    BACKEND_CORS_ORIGINS: List[str] = ["*"]
    ENABLE_GRAPHQL: bool = False

    # External APIs
    google_api_key: Optional[str] = os.getenv("GOOGLE_API_KEY")
    supabase_anon_key: Optional[str] = os.getenv("SUPABASE_ANON_KEY")

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
