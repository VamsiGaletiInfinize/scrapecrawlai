"""
Robots.txt compliance service.

Fetches, caches, and parses robots.txt files to ensure
ethical crawling behavior.
"""

import asyncio
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from typing import Optional
import aiohttp

from ..utils.logger import get_robots_logger

# Initialize logger
logger = get_robots_logger()


class RobotsChecker:
    """
    Async robots.txt checker with caching.

    Fetches and parses robots.txt files for each domain,
    caching the results to avoid repeated fetches.
    """

    def __init__(self, user_agent: str = "ScrapeCrawlAI/1.0"):
        """
        Initialize the robots checker.

        Args:
            user_agent: User agent string for robots.txt matching
        """
        self.user_agent = user_agent
        self._parsers: dict[str, RobotFileParser] = {}
        self._crawl_delays: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            # 5 second timeout for robots.txt (fast fail)
            timeout = aiohttp.ClientTimeout(total=5, connect=3)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def _load_robots(self, domain: str) -> None:
        """
        Fetch and parse robots.txt for a domain.

        Args:
            domain: Domain URL (e.g., https://example.com)
        """
        robots_url = f"{domain}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)

        start_time = time.perf_counter()

        try:
            session = await self._get_session()
            async with session.get(robots_url) as response:
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                if response.status == 200:
                    content = await response.text()
                    # Parse the robots.txt content
                    parser.parse(content.splitlines())
                    logger.info(f"[ROBOTS] Loaded {robots_url} in {elapsed_ms:.1f}ms (status=200)")

                    # Extract crawl-delay if present
                    for line in content.splitlines():
                        line = line.strip().lower()
                        if line.startswith('crawl-delay:'):
                            try:
                                delay = float(line.split(':', 1)[1].strip())
                                self._crawl_delays[domain] = delay
                                logger.debug(f"[ROBOTS] Crawl-delay={delay}s for {domain}")
                            except (ValueError, IndexError):
                                pass
                else:
                    # If robots.txt doesn't exist or error, allow all
                    parser.allow_all = True
                    logger.debug(f"[ROBOTS] No robots.txt for {domain} (status={response.status}) in {elapsed_ms:.1f}ms")
        except asyncio.TimeoutError:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            parser.allow_all = True
            logger.warning(f"[ROBOTS] Timeout for {domain} after {elapsed_ms:.1f}ms - allowing all")
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            # On any error, allow all (fail open)
            parser.allow_all = True
            logger.debug(f"[ROBOTS] Error for {domain}: {e} ({elapsed_ms:.1f}ms) - allowing all")

        self._parsers[domain] = parser

    async def can_fetch(self, url: str) -> bool:
        """
        Check if URL is allowed by robots.txt.

        Args:
            url: URL to check

        Returns:
            True if allowed, False if disallowed
        """
        domain = self._get_domain(url)

        async with self._lock:
            if domain not in self._parsers:
                await self._load_robots(domain)

        parser = self._parsers.get(domain)
        if parser is None:
            return True

        # Handle parsers with allow_all attribute (our fallback)
        if hasattr(parser, 'allow_all') and parser.allow_all:
            return True

        try:
            return parser.can_fetch(self.user_agent, url)
        except Exception:
            return True  # Allow on error

    def get_crawl_delay(self, url: str) -> float:
        """
        Get the crawl delay for a URL's domain.

        Args:
            url: URL to get delay for

        Returns:
            Crawl delay in seconds, or 0 if not specified
        """
        domain = self._get_domain(url)
        return self._crawl_delays.get(domain, 0)

    async def is_loaded(self, url: str) -> bool:
        """Check if robots.txt is already loaded for URL's domain."""
        domain = self._get_domain(url)
        return domain in self._parsers


# Global instance
robots_checker = RobotsChecker()
