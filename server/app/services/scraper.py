import time
import asyncio
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

from ..models.crawl import URLTask, PageResult, CrawlMode
from .timer import PageTimer


class ScraperService:
    """
    Content extraction service using aiohttp and BeautifulSoup.

    Handles fetching pages, extracting links, and scraping content.
    """

    def __init__(self, mode: CrawlMode, timeout: int = 30):
        """
        Initialize the scraper service.

        Args:
            mode: Crawl execution mode
            timeout: Request timeout in seconds
        """
        self.mode = mode
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {
                "User-Agent": "ScrapeCrawlAI/1.0 (Web Crawler)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers=headers,
            )
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def fetch_page(self, task: URLTask) -> tuple[PageResult, list[str]]:
        """
        Fetch and process a single page.

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

        try:
            session = await self._get_session()
            async with session.get(task.url) as response:
                if response.status != 200:
                    result.error = f"HTTP {response.status}"
                    result.timing_ms = timer.stop()
                    return result, discovered_urls

                html = await response.text()

                # Parse with BeautifulSoup
                soup = BeautifulSoup(html, 'lxml')

                # Extract links for crawling
                discovered_urls = self._extract_links(soup, task.url)
                result.links_found = len(discovered_urls)

                # Extract content if scraping is enabled
                if self.mode in (CrawlMode.ONLY_SCRAPE, CrawlMode.CRAWL_SCRAPE):
                    result.title = self._extract_title(soup)
                    result.headings = self._extract_headings(soup)
                    result.content = self._extract_content(soup)

        except asyncio.TimeoutError:
            result.error = "Request timeout"
        except aiohttp.ClientError as e:
            result.error = f"Client error: {str(e)}"
        except Exception as e:
            result.error = f"Unexpected error: {str(e)}"

        result.timing_ms = timer.stop()
        return result, discovered_urls

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """
        Extract all links from the page.

        Args:
            soup: BeautifulSoup parsed HTML
            base_url: Base URL for resolving relative links

        Returns:
            List of absolute URLs
        """
        links = []
        for anchor in soup.find_all('a', href=True):
            href = anchor['href'].strip()

            # Skip empty, javascript, mailto, tel links
            if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
                continue

            # Resolve relative URLs
            absolute_url = urljoin(base_url, href)

            # Validate URL
            parsed = urlparse(absolute_url)
            if parsed.scheme in ('http', 'https'):
                links.append(absolute_url)

        return links

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract page title."""
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True)

        # Fallback to h1
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
        return headings

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """
        Extract main content from the page.

        Removes scripts, styles, and navigation elements.
        """
        # Remove unwanted elements
        for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript']):
            element.decompose()

        # Try to find main content
        main_content = soup.find('main') or soup.find('article') or soup.find('div', {'class': re.compile(r'content|main', re.I)})

        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
        else:
            # Fallback to body
            body = soup.find('body')
            text = body.get_text(separator='\n', strip=True) if body else soup.get_text(separator='\n', strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        content = '\n'.join(lines)

        # Limit content length
        max_length = 50000
        if len(content) > max_length:
            content = content[:max_length] + '...[truncated]'

        return content


class Crawl4AIScraperService:
    """
    Alternative scraper service using Crawl4AI library.

    Note: Requires crawl4ai to be installed and configured.
    """

    def __init__(self, mode: CrawlMode):
        """
        Initialize the Crawl4AI scraper service.

        Args:
            mode: Crawl execution mode
        """
        self.mode = mode
        self._crawler = None

    async def _get_crawler(self):
        """Get or create the Crawl4AI crawler."""
        if self._crawler is None:
            try:
                from crawl4ai import AsyncWebCrawler
                self._crawler = AsyncWebCrawler(verbose=False)
                await self._crawler.start()
            except ImportError:
                raise ImportError("crawl4ai is not installed. Run: pip install crawl4ai")
        return self._crawler

    async def close(self):
        """Close the Crawl4AI crawler."""
        if self._crawler:
            await self._crawler.close()
            self._crawler = None

    async def fetch_page(self, task: URLTask) -> tuple[PageResult, list[str]]:
        """
        Fetch and process a page using Crawl4AI.

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

        try:
            crawler = await self._get_crawler()
            crawl_result = await crawler.arun(url=task.url)

            if crawl_result.success:
                # Extract links
                discovered_urls = crawl_result.links.get("internal", [])
                result.links_found = len(discovered_urls)

                # Extract content if scraping
                if self.mode in (CrawlMode.ONLY_SCRAPE, CrawlMode.CRAWL_SCRAPE):
                    result.title = crawl_result.metadata.get("title")
                    result.content = crawl_result.markdown or crawl_result.cleaned_html

                    # Extract headings from markdown
                    if crawl_result.markdown:
                        headings = []
                        for line in crawl_result.markdown.split('\n'):
                            if line.startswith('#'):
                                headings.append(line.strip())
                        result.headings = headings[:20]  # Limit headings
            else:
                result.error = crawl_result.error_message or "Crawl failed"

        except Exception as e:
            result.error = f"Crawl4AI error: {str(e)}"

        result.timing_ms = timer.stop()
        return result, discovered_urls


def create_scraper(mode: CrawlMode, use_crawl4ai: bool = False) -> ScraperService | Crawl4AIScraperService:
    """
    Factory function to create appropriate scraper.

    Args:
        mode: Crawl execution mode
        use_crawl4ai: If True, use Crawl4AI; otherwise use basic scraper

    Returns:
        Scraper service instance
    """
    if use_crawl4ai:
        return Crawl4AIScraperService(mode)
    return ScraperService(mode)
