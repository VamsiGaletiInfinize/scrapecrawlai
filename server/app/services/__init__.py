"""
Services package for ScrapeCrawlAI.

This package contains business logic services:
- Job managers for crawl orchestration
- Scraper for content extraction
- Formatters for output generation
- Rate limiting and robots.txt compliance
"""

from .job_manager import job_manager, JobManager, DomainFilter
from .multi_kb_job_manager import multi_kb_job_manager, MultiKBJobManager
from .scraper import ScraperService, create_scraper
from .formatter import OutputFormatter
from .enhanced_formatter import enhanced_formatter, EnhancedFormatter
from .classifier import content_classifier, ContentClassifier
from .exporter import directory_exporter, DirectoryExporter
from .websocket import connection_manager, ConnectionManager
from .rate_limiter import rate_limiter, DomainRateLimiter, AdaptiveRateLimiter
from .robots import robots_checker, RobotsChecker
from .timer import TimerService, PageTimer

__all__ = [
    # Job managers
    "job_manager",
    "JobManager",
    "DomainFilter",
    "multi_kb_job_manager",
    "MultiKBJobManager",
    # Scraper
    "ScraperService",
    "create_scraper",
    # Formatters
    "OutputFormatter",
    "enhanced_formatter",
    "EnhancedFormatter",
    # Classifier
    "content_classifier",
    "ContentClassifier",
    # Exporter
    "directory_exporter",
    "DirectoryExporter",
    # WebSocket
    "connection_manager",
    "ConnectionManager",
    # Rate limiting
    "rate_limiter",
    "DomainRateLimiter",
    "AdaptiveRateLimiter",
    # Robots
    "robots_checker",
    "RobotsChecker",
    # Timer
    "TimerService",
    "PageTimer",
]
