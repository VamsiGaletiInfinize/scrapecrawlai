import asyncio
import time
from collections import deque
from typing import Optional, Callable, Awaitable
from urllib.parse import urljoin, urlparse

from ..models.crawl import (
    URLTask, PageResult, CrawlMode, TimingMetrics, DepthStats
)


class BFSCrawler:
    """
    Breadth-First Search crawler with queue-based URL frontier.

    The crawler processes URLs level by level, ensuring BFS ordering:
    - Depth 1: Seed URL
    - Depth 2: All immediate child URLs from depth 1
    - Depth 3: All children of depth 2 URLs
    - And so on until max_depth is reached
    """

    def __init__(
        self,
        seed_url: str,
        max_depth: int,
        mode: CrawlMode,
        fetch_callback: Callable[[URLTask], Awaitable[tuple[PageResult, list[str]]]],
    ):
        """
        Initialize the BFS crawler.

        Args:
            seed_url: Starting URL for the crawl
            max_depth: Maximum depth to crawl (1-5)
            mode: Crawl execution mode
            fetch_callback: Async function to fetch and process a URL
        """
        self.seed_url = seed_url
        self.max_depth = max_depth
        self.mode = mode
        self.fetch_callback = fetch_callback

        # URL frontier (queue for BFS)
        self.queue: deque[URLTask] = deque()

        # Visited URLs to avoid duplicates
        self.visited: set[str] = set()

        # Results storage
        self.results: list[PageResult] = []

        # URLs grouped by depth for reporting
        self.urls_by_depth: dict[int, list[str]] = {}

        # Timing metrics
        self.timing = TimingMetrics()

        # Base domain for same-domain filtering
        parsed = urlparse(seed_url)
        self.base_domain = parsed.netloc

    def _normalize_url(self, url: str, base_url: str) -> Optional[str]:
        """
        Normalize and validate a URL.

        Args:
            url: URL to normalize (may be relative)
            base_url: Base URL for resolving relative URLs

        Returns:
            Normalized absolute URL, or None if invalid
        """
        try:
            # Skip empty, javascript, mailto, tel links
            if not url or url.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
                return None

            # Resolve relative URLs
            absolute_url = urljoin(base_url, url)

            # Parse and validate
            parsed = urlparse(absolute_url)

            # Only allow http/https
            if parsed.scheme not in ('http', 'https'):
                return None

            # Same-domain filtering
            if parsed.netloc != self.base_domain:
                return None

            # Remove fragment
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean_url += f"?{parsed.query}"

            # Remove trailing slash for consistency
            clean_url = clean_url.rstrip('/')

            return clean_url
        except Exception:
            return None

    def _add_to_queue(self, url: str, parent_url: Optional[str], depth: int) -> bool:
        """
        Add a URL to the queue if not visited and within depth limit.

        Args:
            url: URL to add
            parent_url: Parent URL that discovered this URL
            depth: Depth level of this URL

        Returns:
            True if URL was added, False if skipped
        """
        # Check depth limit
        if depth > self.max_depth:
            return False

        # Check if already visited
        normalized = self._normalize_url(url, parent_url or self.seed_url)
        if not normalized or normalized in self.visited:
            return False

        # Mark as visited before adding to queue (avoid duplicates)
        self.visited.add(normalized)

        # Add to queue
        task = URLTask(url=normalized, parent_url=parent_url, depth=depth)
        self.queue.append(task)

        # Track URLs by depth
        if depth not in self.urls_by_depth:
            self.urls_by_depth[depth] = []
        self.urls_by_depth[depth].append(normalized)

        return True

    async def crawl(self) -> tuple[list[PageResult], TimingMetrics, list[DepthStats]]:
        """
        Execute the BFS crawl.

        Returns:
            Tuple of (results, timing_metrics, urls_by_depth)
        """
        total_start = time.perf_counter()

        # Initialize with seed URL at depth 1
        self._add_to_queue(self.seed_url, None, 1)

        # For only_scrape mode, just process the seed URL
        if self.mode == CrawlMode.ONLY_SCRAPE:
            if self.queue:
                task = self.queue.popleft()
                scrape_start = time.perf_counter()
                result, _ = await self.fetch_callback(task)
                self.timing.scraping_ms += (time.perf_counter() - scrape_start) * 1000
                self.results.append(result)
        else:
            # BFS crawl
            await self._bfs_crawl()

        # Calculate total time
        self.timing.total_ms = (time.perf_counter() - total_start) * 1000

        # Convert urls_by_depth to DepthStats list
        depth_stats = [
            DepthStats(depth=d, urls_count=len(urls), urls=urls)
            for d, urls in sorted(self.urls_by_depth.items())
        ]

        return self.results, self.timing, depth_stats

    async def _bfs_crawl(self):
        """
        Execute BFS traversal level by level.

        This processes URLs in strict BFS order by processing all URLs
        at each depth level before moving to the next.
        """
        current_depth = 1

        while self.queue:
            # Get all URLs at current depth
            current_level_tasks: list[URLTask] = []
            while self.queue and self.queue[0].depth == current_depth:
                current_level_tasks.append(self.queue.popleft())

            if not current_level_tasks:
                # No more tasks at current depth, check if queue has tasks at deeper levels
                if self.queue:
                    current_depth = self.queue[0].depth
                    continue
                break

            # Process current level and discover next level URLs
            discovery_start = time.perf_counter()
            crawl_start = time.perf_counter()

            for task in current_level_tasks:
                # Crawl/scrape the page
                result, discovered_urls = await self.fetch_callback(task)
                self.results.append(result)

                # Track crawling time
                self.timing.crawling_ms += result.timing_ms

                # Discover child URLs if not at max depth
                if task.depth < self.max_depth:
                    for url in discovered_urls:
                        self._add_to_queue(url, task.url, task.depth + 1)

            # Track discovery time for this level
            self.timing.url_discovery_ms += (time.perf_counter() - discovery_start) * 1000 - self.timing.crawling_ms

            # Move to next depth level
            current_depth += 1

    def get_progress(self) -> dict:
        """Get current crawl progress."""
        return {
            "urls_discovered": len(self.visited),
            "urls_processed": len(self.results),
            "current_depth": max(self.urls_by_depth.keys()) if self.urls_by_depth else 0,
            "queue_size": len(self.queue),
        }
