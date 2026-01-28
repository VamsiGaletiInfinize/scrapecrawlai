"""
ScrapeCrawlAI Server Package

BFS-based web crawler and scraper with multi-worker architecture.
"""

from .config import config, AppConfig
from .exceptions import (
    ScrapeCrawlError,
    JobError,
    JobNotFoundError,
    JobNotCompletedError,
    JobFailedError,
    KBError,
    KBNotFoundError,
    NoActiveKBsError,
    CrawlError,
    ExportError,
    ValidationError,
)

__all__ = [
    # Config
    "config",
    "AppConfig",
    # Exceptions
    "ScrapeCrawlError",
    "JobError",
    "JobNotFoundError",
    "JobNotCompletedError",
    "JobFailedError",
    "KBError",
    "KBNotFoundError",
    "NoActiveKBsError",
    "CrawlError",
    "ExportError",
    "ValidationError",
]
