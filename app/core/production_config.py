"""
Production configuration for LabelSquor API
"""

import os
from typing import List, Optional


class ProductionSettings:
    """Production-specific settings with security"""
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")
    API_KEY_HEADER: str = "X-API-Key"
    ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "admin-api-key-change-in-production")
    
    # CORS - Configure for your frontend domain
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://labelsquor.com")
    ALLOWED_ORIGINS: List[str] = [
        os.getenv("FRONTEND_URL", "https://labelsquor.com"),
        "https://www.labelsquor.com",
        "https://app.labelsquor.com",
        # Add your Netlify/Vercel domains here
        "https://labelsquor.netlify.app",
        "https://labelsquor.vercel.app",
    ]
    
    # For development, allow localhost
    if os.getenv("ENVIRONMENT") == "development":
        ALLOWED_ORIGINS.extend([
            "http://localhost:3000",    # React dev server
            "http://localhost:5173",    # Vite dev server
            "http://localhost:8080",    # Vue dev server
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ])
    
    # Rate limiting
    RATE_LIMIT_CONSUMER: str = "100/minute"  # Consumer endpoints
    RATE_LIMIT_ADMIN: str = "10/minute"      # Admin endpoints
    RATE_LIMIT_AI: str = "5/minute"          # AI analysis endpoints
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    DATABASE_POOL_SIZE: int = int(os.getenv("DATABASE_POOL_SIZE", "10"))
    DATABASE_MAX_OVERFLOW: int = int(os.getenv("DATABASE_MAX_OVERFLOW", "20"))
    
    # External APIs
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    
    # Monitoring
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    WORKERS: int = int(os.getenv("WORKERS", "4"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")
    
    # Feature flags
    ENABLE_AI_ANALYSIS: bool = os.getenv("ENABLE_AI_ANALYSIS", "true").lower() == "true"
    ENABLE_IMAGE_HOSTING: bool = os.getenv("ENABLE_IMAGE_HOSTING", "false").lower() == "true"
    
    @classmethod
    def validate_required_env_vars(cls):
        """Validate that required environment variables are set"""
        required_vars = [
            "DATABASE_URL",
            "GOOGLE_API_KEY",
            "SECRET_KEY",
            "ADMIN_API_KEY"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return True


# Create production settings instance
production_settings = ProductionSettings()
