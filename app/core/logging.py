"""
Logging configuration
"""

import logging
import sys

from loguru import logger


def setup_logging():
    """Setup logging configuration"""
    # Remove default handler
    logger.remove()

    # Add console handler
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )


# Create logger instance
log = logger
