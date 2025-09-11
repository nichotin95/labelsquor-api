"""
Structured logging configuration using loguru
"""
import sys
import json
from typing import Any, Dict
from loguru import logger
from starlette_context import context

from app.core.config import settings


class ContextFilter:
    """Add request context to log records"""
    
    def __call__(self, record: Dict[str, Any]) -> bool:
        """Add context data to log record"""
        try:
            # Add correlation ID if available
            record["extra"]["correlation_id"] = context.get("correlation_id", "no-context")
            record["extra"]["request_id"] = context.get("request_id", "no-context")
            record["extra"]["user_id"] = context.get("user_id", "anonymous")
        except Exception:
            # Context not available (e.g., outside request)
            pass
        return True


def serialize(record: Dict[str, Any]) -> str:
    """Serialize log record to JSON"""
    subset = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
        "correlation_id": record.get("extra", {}).get("correlation_id"),
        "request_id": record.get("extra", {}).get("request_id"),
        "user_id": record.get("extra", {}).get("user_id"),
    }
    
    # Add exception info if present
    if record.get("exception"):
        subset["exception"] = {
            "type": record["exception"].type.__name__,
            "value": str(record["exception"].value),
            "traceback": record["exception"].traceback.raw
        }
    
    # Add any extra fields
    if "extra" in record:
        subset["extra"] = record["extra"]
    
    return json.dumps(subset, default=str)


def setup_logging() -> None:
    """Configure structured logging"""
    # Remove default handler
    logger.remove()
    
    # Console logging
    if settings.LOG_FORMAT == "json":
        # JSON format for production
        logger.add(
            sys.stdout,
            format=serialize,
            filter=ContextFilter(),
            level=settings.LOG_LEVEL,
            enqueue=True  # Thread-safe
        )
    else:
        # Pretty format for development
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <cyan>{extra[correlation_id]}</cyan> - <level>{message}</level>",
            filter=ContextFilter(),
            level=settings.LOG_LEVEL,
            colorize=True,
            enqueue=True
        )
    
    # File logging (always JSON)
    if settings.ENVIRONMENT != "development":
        logger.add(
            "logs/app_{time}.log",
            rotation="1 day",
            retention="30 days",
            format=serialize,
            filter=ContextFilter(),
            level=settings.LOG_LEVEL,
            enqueue=True,
            compression="gz"
        )
    
    # Log configuration
    logger.info(
        "Logging configured",
        environment=settings.ENVIRONMENT,
        level=settings.LOG_LEVEL,
        format=settings.LOG_FORMAT
    )


# Create a logger instance for import
log = logger
