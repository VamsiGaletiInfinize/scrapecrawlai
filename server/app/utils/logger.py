"""
Centralized logging configuration for ScrapeCrawlAI.
"""

import logging
import sys
from typing import Optional


def setup_logger(
    name: str = "scrapecrawlai",
    level: int = logging.INFO,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Setup and return a configured logger.

    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path to write logs

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Format: timestamp - level - module - message
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Optional file handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Pre-configured loggers for different modules
def get_scraper_logger() -> logging.Logger:
    """Logger for scraper service."""
    return setup_logger("scraper", logging.DEBUG)


def get_crawler_logger() -> logging.Logger:
    """Logger for crawler/job manager."""
    return setup_logger("crawler", logging.DEBUG)


def get_api_logger() -> logging.Logger:
    """Logger for API routes."""
    return setup_logger("api", logging.INFO)


def get_robots_logger() -> logging.Logger:
    """Logger for robots.txt checker."""
    return setup_logger("robots", logging.DEBUG)


def get_rate_limiter_logger() -> logging.Logger:
    """Logger for rate limiter."""
    return setup_logger("rate_limiter", logging.DEBUG)
