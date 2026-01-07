"""
Enhanced content extraction service with connection pooling,
retry logic, and rate limiting integration.
"""

import asyncio
import random
import re
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

from ..models.crawl import URLTask, PageResult, CrawlMode
from .timer import PageTimer
from .rate_limiter import rate_limiter
from .robots import robots_checker


# User agent pool for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]


def get_random_user_agent() -> str:
    """Get a random user agent from the pool."""
    return random.choice(USER_AGENTS)


class ScraperService:
    """
    Enhanced content extraction service with:
    - Connection pooling for better performance
    - DNS caching
    - Retry logic with exponential backoff
    - User-agent rotation
    - Rate limiting integration
    - Robots.txt compliance
    """

    def __init__(
        self,
        mode: CrawlMode,
        timeout: int = 30,
        max_retries: int = 3,
        respect_robots: bool = True,
        use_rate_limiting: bool = True,
    ):
        """
        Initialize the scraper service.

        Args:
            mode: Crawl execution mode
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
            respect_robots: Whether to check robots.txt
            use_rate_limiting: Whether to use rate limiting
        """
        self.mode = mode
        self.timeout = aiohttp.ClientTimeout(total=timeout, connect=10)
        self.max_retries = max_retries
        self.respect_robots = respect_robots
        self.use_rate_limiting = use_rate_limiting
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Get or create the aiohttp session with connection pooling.

        Connection pooling benefits:
        - Reuses TCP connections (avoids handshake overhead)
        - DNS caching (avoids repeated lookups)
        - Keep-alive connections
        """
        if self._session is None or self._session.closed:
            # Create connector with connection pooling
            self._connector = aiohttp.TCPConnector(
                limit=100,              # Total connection pool size
                limit_per_host=10,      # Connections per domain
                ttl_dns_cache=300,      # DNS cache TTL (5 minutes)
                keepalive_timeout=30,   # Keep connections alive
                enable_cleanup_closed=True,
            )

            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }

            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=self.timeout,
                headers=headers,
            )
        return self._session

    async def close(self):
        """Close the aiohttp session and connector."""
        if self._session and not self._session.closed:
            await self._session.close()
        if self._connector and not self._connector.closed:
            await self._connector.close()
        await robots_checker.close()

    async def fetch_page(self, task: URLTask) -> tuple[PageResult, list[str]]:
        """
        Fetch and process a single page with retries.

        Args:
            task: URL task to process

        Returns:
            Tuple of (PageResult, discovered_urls)
        """
        timer = PageTimer()
        timer.start()

        discovered_urls: list[str] = []
        result = PageResult(
            url=task.url,
            parent_url=task.parent_url,
            depth=task.depth,
        )

        # Check robots.txt
        if self.respect_robots:
            try:
                can_fetch = await robots_checker.can_fetch(task.url)
                if not can_fetch:
                    result.error = "Blocked by robots.txt"
                    result.timing_ms = timer.stop()
                    return result, discovered_urls

                # Set crawl delay from robots.txt
                crawl_delay = robots_checker.get_crawl_delay(task.url)
                if crawl_delay > 0:
                    domain = urlparse(task.url).netloc
                    rate_limiter.set_delay(domain, crawl_delay)
            except Exception:
                pass  # Continue if robots check fails

        # Apply rate limiting
        if self.use_rate_limiting:
            await rate_limiter.acquire(task.url)

        # Fetch with retries
        result, discovered_urls = await self._fetch_with_retry(task, result)
        result.timing_ms = timer.stop()

        return result, discovered_urls

    async def _fetch_with_retry(
        self,
        task: URLTask,
        result: PageResult,
    ) -> tuple[PageResult, list[str]]:
        """
        Fetch page with exponential backoff retry.

        Args:
            task: URL task to process
            result: PageResult to populate

        Returns:
            Tuple of (PageResult, discovered_urls)
        """
        discovered_urls: list[str] = []
        delays = [1, 2, 4]  # Exponential backoff delays
        last_error = None

        for attempt in range(self.max_retries):
            try:
                session = await self._get_session()

                # Rotate user agent per request
                headers = {"User-Agent": get_random_user_agent()}

                async with session.get(task.url, headers=headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'lxml')

                        # Extract links
                        discovered_urls = self._extract_links(soup, task.url)
                        result.links_found = len(discovered_urls)

                        # Extract content if scraping enabled
                        if self.mode in (CrawlMode.ONLY_SCRAPE, CrawlMode.CRAWL_SCRAPE):
                            result.title = self._extract_title(soup)
                            result.headings = self._extract_headings(soup)
                            result.content = self._extract_content(soup)

                        return result, discovered_urls

                    elif response.status == 429:
                        # Rate limited - wait longer
                        result.error = f"Rate limited (429)"
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(delays[attempt] * 2)
                            continue

                    elif response.status >= 500:
                        # Server error - retry
                        last_error = f"HTTP {response.status}"
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(delays[attempt])
                            continue

                    else:
                        # Client error - don't retry
                        result.error = f"HTTP {response.status}"
                        return result, discovered_urls

            except asyncio.TimeoutError:
                last_error = "Request timeout"
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(delays[attempt])

            except aiohttp.ClientError as e:
                last_error = f"Client error: {str(e)}"
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(delays[attempt])

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                break  # Don't retry on unexpected errors

        result.error = last_error
        return result, discovered_urls

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Extract all links from the page."""
        links = []
        for anchor in soup.find_all('a', href=True):
            href = anchor['href'].strip()

            # Skip invalid links
            if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
                continue

            # Resolve relative URLs
            absolute_url = urljoin(base_url, href)

            # Validate URL
            parsed = urlparse(absolute_url)
            if parsed.scheme in ('http', 'https'):
                # Clean URL (remove fragment)
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    clean_url += f"?{parsed.query}"
                links.append(clean_url)

        return list(set(links))  # Remove duplicates

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract page title."""
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True)

        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)

        return None

    def _extract_headings(self, soup: BeautifulSoup) -> list[str]:
        """Extract all headings (h1-h6)."""
        headings = []
        for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            for heading in soup.find_all(tag):
                text = heading.get_text(strip=True)
                if text:
                    headings.append(f"{tag.upper()}: {text}")
        return headings[:50]  # Limit to 50 headings

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from the page."""
        # Clone soup to avoid modifying original
        soup_copy = BeautifulSoup(str(soup), 'lxml')

        # Remove unwanted elements
        for element in soup_copy.find_all([
            'script', 'style', 'nav', 'header', 'footer',
            'aside', 'noscript', 'iframe', 'form'
        ]):
            element.decompose()

        # Try to find main content
        main_content = (
            soup_copy.find('main') or
            soup_copy.find('article') or
            soup_copy.find('div', {'class': re.compile(r'content|main|body', re.I)}) or
            soup_copy.find('div', {'id': re.compile(r'content|main|body', re.I)})
        )

        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
        else:
            body = soup_copy.find('body')
            text = body.get_text(separator='\n', strip=True) if body else soup_copy.get_text(separator='\n', strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        content = '\n'.join(lines)

        # Limit content length
        max_length = 50000
        if len(content) > max_length:
            content = content[:max_length] + '...[truncated]'

        return content


def create_scraper(
    mode: CrawlMode,
    respect_robots: bool = True,
    use_rate_limiting: bool = True,
) -> ScraperService:
    """
    Factory function to create scraper service.

    Args:
        mode: Crawl execution mode
        respect_robots: Whether to check robots.txt
        use_rate_limiting: Whether to use rate limiting

    Returns:
        ScraperService instance
    """
    return ScraperService(
        mode=mode,
        respect_robots=respect_robots,
        use_rate_limiting=use_rate_limiting,
    )
