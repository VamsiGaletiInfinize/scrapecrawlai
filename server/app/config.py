"""
Centralized configuration for ScrapeCrawlAI.

This module consolidates all configuration values used throughout the application,
making it easier to manage, modify, and understand the system's behavior.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class HTTPConfig:
    """HTTP client configuration."""

    # Request timeouts (seconds)
    REQUEST_TIMEOUT: int = 30
    CONNECT_TIMEOUT: int = 10

    # Retry settings
    MAX_RETRIES: int = 3
    RETRY_DELAYS: tuple[int, ...] = (1, 2, 4)  # Exponential backoff delays

    # Connection pooling
    CONNECTION_POOL_SIZE: int = 100
    CONNECTIONS_PER_HOST: int = 10
    DNS_CACHE_TTL: int = 300  # 5 minutes
    KEEPALIVE_TIMEOUT: int = 30


@dataclass(frozen=True)
class RateLimitConfig:
    """Rate limiting configuration."""

    DEFAULT_DELAY: float = 0.25  # seconds between requests per domain
    MIN_DELAY: float = 0.1
    MAX_DELAY: float = 5.0
    RATE_LIMIT_429_MULTIPLIER: float = 2.0  # Extra wait on 429 response


@dataclass(frozen=True)
class ContentConfig:
    """Content extraction configuration."""

    MAX_CONTENT_LENGTH: int = 50000
    MAX_HEADINGS: int = 50
    CONTENT_PREVIEW_LENGTH: int = 500
    MIN_CONTENT_LENGTH: int = 50  # Minimum to consider page has content


@dataclass(frozen=True)
class CrawlLimits:
    """Crawling limits and constraints."""

    MIN_DEPTH: int = 1
    MAX_DEPTH: int = 5
    DEFAULT_DEPTH: int = 3

    MIN_WORKERS: int = 2
    MAX_WORKERS: int = 10
    DEFAULT_WORKERS: int = 4

    # KB crawling
    DEFAULT_PARALLEL_KBS: int = 2
    MAX_PARALLEL_KBS: int = 5


@dataclass(frozen=True)
class OutputConfig:
    """Output and export configuration."""

    DEFAULT_MAX_CONTENT_LENGTH: int = 5000
    MIN_CONTENT_LENGTH: int = 100
    MAX_CONTENT_LENGTH: int = 50000
    PAGES_PER_GROUP_LIMIT: int = 50  # For markdown output
    EXPORT_PAGES_LIMIT: int = 100  # For table views


@dataclass(frozen=True)
class CORSConfig:
    """CORS configuration for development."""

    ALLOWED_ORIGINS: tuple[str, ...] = (
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://localhost:3000",
    )


# User agent pool for rotation
USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
)


@dataclass
class AppConfig:
    """
    Main application configuration.

    Aggregates all configuration sections and provides environment-based overrides.
    """

    http: HTTPConfig = field(default_factory=HTTPConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    content: ContentConfig = field(default_factory=ContentConfig)
    crawl_limits: CrawlLimits = field(default_factory=CrawlLimits)
    output: OutputConfig = field(default_factory=OutputConfig)
    cors: CORSConfig = field(default_factory=CORSConfig)

    # Application info
    APP_NAME: str = "ScrapeCrawlAI"
    APP_VERSION: str = "2.0.0"
    APP_DESCRIPTION: str = "BFS-based web crawler and scraper with multi-worker architecture"

    # Environment
    DEBUG: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    @classmethod
    def from_env(cls) -> "AppConfig":
        """
        Create configuration from environment variables.

        Supports overrides via environment variables:
        - SCRAPECRAWL_REQUEST_TIMEOUT
        - SCRAPECRAWL_MAX_RETRIES
        - SCRAPECRAWL_DEFAULT_DELAY
        - etc.
        """
        config = cls()

        # Override HTTP config from env
        if timeout := os.getenv("SCRAPECRAWL_REQUEST_TIMEOUT"):
            object.__setattr__(config.http, "REQUEST_TIMEOUT", int(timeout))

        if retries := os.getenv("SCRAPECRAWL_MAX_RETRIES"):
            object.__setattr__(config.http, "MAX_RETRIES", int(retries))

        # Override rate limit from env
        if delay := os.getenv("SCRAPECRAWL_DEFAULT_DELAY"):
            object.__setattr__(config.rate_limit, "DEFAULT_DELAY", float(delay))

        return config


# Global configuration instance
config = AppConfig()


def get_random_user_agent() -> str:
    """Get a random user agent from the pool."""
    import random
    return random.choice(USER_AGENTS)
