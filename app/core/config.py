"""
Application configuration using Pydantic Settings V2
"""
from typing import Optional, List, Literal, Set
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, PostgresDsn, Field, field_validator
from functools import lru_cache
import secrets


class Settings(BaseSettings):
    # API Configuration
    PROJECT_NAME: str = "LabelSquor API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    
    # Database
    DATABASE_URL: PostgresDsn
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_PRE_PING: bool = True
    DB_ECHO: bool = False
    
    # Supabase
    SUPABASE_URL: AnyHttpUrl
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    
    # Security
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # seconds
    
    # External Services
    GOOGLE_AI_STUDIO_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    # Storage
    STORAGE_TYPE: Literal["s3", "supabase", "local"] = "supabase"
    S3_BUCKET_NAME: Optional[str] = None
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    S3_REGION: Optional[str] = "us-east-1"
    LOCAL_STORAGE_PATH: str = "./storage"
    
    # Redis (for caching)
    REDIS_URL: Optional[str] = None
    CACHE_TTL: int = 300  # 5 minutes default
    
    # Feature Flags
    ENABLE_OCR: bool = False
    ENABLE_BARCODE_SCAN: bool = False
    ENABLE_GRAPHQL: bool = False
    ENABLE_WEBHOOKS: bool = False
    
    # Observability
    SENTRY_DSN: Optional[str] = None
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "pretty"] = "json"
    ENABLE_OPENTELEMETRY: bool = False
    OTLP_ENDPOINT: Optional[str] = None
    
    # Task Queue
    TASK_QUEUE_TYPE: Literal["celery", "dramatiq", "none"] = "none"
    BROKER_URL: Optional[str] = None
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    @field_validator("DATABASE_URL", mode="after")
    def validate_database_url(cls, v: PostgresDsn) -> PostgresDsn:
        """Ensure DATABASE_URL is properly formatted"""
        return v
    
    @property
    def async_database_url(self) -> str:
        """Convert sync PostgreSQL URL to async"""
        return str(self.DATABASE_URL).replace("postgresql://", "postgresql+asyncpg://")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # Ignore extra env vars
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Create settings instance with caching.
    This ensures we only load environment variables once.
    """
    return Settings()


settings = get_settings()