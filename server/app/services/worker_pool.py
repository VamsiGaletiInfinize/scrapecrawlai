import asyncio
import time
from typing import Callable, Awaitable
from collections import deque

from ..models.crawl import URLTask, PageResult, CrawlMode, TimingMetrics, DepthStats, PageStatus, SkipReason


class WorkerPool:
    """
    Async worker pool for processing URLs concurrently.

    Uses a semaphore to limit concurrent workers and processes
    URLs in batches per depth level for proper BFS ordering.
    """

    def __init__(
        self,
        num_workers: int,
        process_callback: Callable[[URLTask], Awaitable[tuple[PageResult, list[str]]]],
        progress_callback: Callable[[dict], Awaitable[None]] | None = None,
    ):
        """
        Initialize the worker pool.

        Args:
            num_workers: Maximum number of concurrent workers (2-10)
            process_callback: Async function to process a single URL
            progress_callback: Optional async function to report progress
        """
        self.num_workers = max(2, min(10, num_workers))
        self.process_callback = process_callback
        self.progress_callback = progress_callback
        self.semaphore = asyncio.Semaphore(self.num_workers)

        # Shared state
        self.results: list[PageResult] = []
        self.visited: set[str] = set()
        self.urls_by_depth: dict[int, list[str]] = {}
        self.lock = asyncio.Lock()

        # Progress tracking
        self._total_to_process = 0
        self._current_depth = 0
        self._queue_size = 0

        # Timing metrics
        self.timing = TimingMetrics()
        self._crawl_time_accumulated = 0.0
        self._scrape_time_accumulated = 0.0

        # Failure tracking
        self._crawl_failures = 0
        self._scrape_failures = 0

    async def _process_url(
        self,
        task: URLTask,
        results_list: list[tuple[PageResult, list[str]]],
        on_url_complete: Callable[[], Awaitable[None]] | None = None,
        skip_scraping: bool = False,
    ) -> None:
        """
        Process a single URL with semaphore-controlled concurrency.

        Args:
            task: URL task to process
            results_list: Shared list to append results
            on_url_complete: Optional callback when URL processing completes
            skip_scraping: If True, only discover URLs without extracting content
        """
        async with self.semaphore:
            start_time = time.perf_counter()
            try:
                result, discovered_urls = await self.process_callback(task)

                # If skipping scraping for child pages, clear content and mark as skipped
                if skip_scraping:
                    result.content = None
                    result.title = None
                    result.headings = []
                    result.status = PageStatus.SKIPPED
                    result.skip_reason = SkipReason.CHILD_PAGES_DISABLED
                    # Clear any scrape timing since we're not counting it
                    result.page_timing.scrape_ms = 0.0
                else:
                    # Set appropriate status based on content
                    if result.content:
                        result.status = PageStatus.SCRAPED
                    elif result.error:
                        result.status = PageStatus.ERROR
                    else:
                        result.status = PageStatus.CRAWLED

                # Store result
                async with self.lock:
                    results_list.append((result, discovered_urls))

                # Notify completion
                if on_url_complete:
                    await on_url_complete()

            except Exception as e:
                # Create error result
                result = PageResult(
                    url=task.url,
                    parent_url=task.parent_url,
                    depth=task.depth,
                    error=str(e),
                    timing_ms=(time.perf_counter() - start_time) * 1000,
                    status=PageStatus.ERROR,
                )
                async with self.lock:
                    results_list.append((result, []))

                # Notify completion even on error
                if on_url_complete:
                    await on_url_complete()

    async def process_batch(
        self,
        tasks: list[URLTask],
        on_url_complete: Callable[[], Awaitable[None]] | None = None,
        skip_scraping_for_depth: int | None = None,
    ) -> list[tuple[PageResult, list[str]]]:
        """
        Process a batch of URLs concurrently using the worker pool.

        Args:
            tasks: List of URL tasks to process
            on_url_complete: Optional callback when each URL completes
            skip_scraping_for_depth: If set, skip scraping for pages at this depth or deeper

        Returns:
            List of (PageResult, discovered_urls) tuples
        """
        results_list: list[tuple[PageResult, list[str]]] = []

        # Create tasks for all URLs
        async_tasks = [
            asyncio.create_task(
                self._process_url(
                    task,
                    results_list,
                    on_url_complete,
                    skip_scraping=(skip_scraping_for_depth is not None and task.depth >= skip_scraping_for_depth),
                )
            )
            for task in tasks
        ]

        # Wait for all tasks to complete
        if async_tasks:
            await asyncio.gather(*async_tasks, return_exceptions=True)

        return results_list

    async def crawl_bfs(
        self,
        seed_url: str,
        max_depth: int,
        mode: CrawlMode,
        base_domain: str,
        normalize_url_func: Callable[[str, str], str | None],
        include_child_pages: bool = True,
    ) -> tuple[list[PageResult], TimingMetrics, list[DepthStats]]:
        """
        Execute BFS crawl using worker pool.

        Args:
            seed_url: Starting URL
            max_depth: Maximum depth to crawl
            mode: Crawl execution mode
            base_domain: Base domain for same-domain filtering
            normalize_url_func: Function to normalize URLs
            include_child_pages: Whether to scrape child pages (depth > 1)

        Returns:
            Tuple of (results, timing_metrics, depth_stats)
        """
        self._include_child_pages = include_child_pages
        total_start = time.perf_counter()

        # Initialize queue with seed
        queue: deque[URLTask] = deque()
        queue.append(URLTask(url=seed_url, parent_url=None, depth=1))
        self.visited.add(seed_url)
        self.urls_by_depth[1] = [seed_url]

        # Handle only_scrape mode - just process seed
        if mode == CrawlMode.ONLY_SCRAPE:
            scrape_start = time.perf_counter()
            task = queue.popleft()
            results = await self.process_batch([task])
            self.timing.scraping_ms = (time.perf_counter() - scrape_start) * 1000

            for result, _ in results:
                self.results.append(result)

            self.timing.total_ms = (time.perf_counter() - total_start) * 1000
            depth_stats = [DepthStats(depth=1, urls_count=1, urls=[seed_url])]
            return self.results, self.timing, depth_stats

        # BFS traversal with worker pool
        current_depth = 1
        # Track total URLs to process for progress calculation
        self._total_to_process = len(queue)
        self._current_depth = current_depth

        while queue:
            # Collect all tasks at current depth
            current_level_tasks: list[URLTask] = []
            while queue and queue[0].depth == current_depth:
                current_level_tasks.append(queue.popleft())

            if not current_level_tasks:
                if queue:
                    current_depth = queue[0].depth
                    self._current_depth = current_depth
                    continue
                break

            # Update progress tracking
            self._current_depth = current_depth
            self._queue_size = len(queue)

            # Create per-URL progress callback using instance variables
            async def on_url_complete():
                if self.progress_callback:
                    await self.progress_callback({
                        "urls_discovered": self._total_to_process,
                        "urls_processed": len(self.results),
                        "current_depth": self._current_depth,
                        "queue_size": self._queue_size,
                    })

            # Process current level with worker pool
            # Skip scraping for child pages (depth >= 2) if include_child_pages is False
            skip_depth = 2 if not include_child_pages else None
            batch_start = time.perf_counter()
            batch_results = await self.process_batch(
                current_level_tasks,
                on_url_complete,
                skip_scraping_for_depth=skip_depth,
            )
            batch_time = (time.perf_counter() - batch_start) * 1000

            # Track timing from individual page results (more accurate)
            batch_crawl_ms = 0.0
            batch_scrape_ms = 0.0

            # Process results and discover new URLs
            discovery_start = time.perf_counter()
            for result, discovered_urls in batch_results:
                # Aggregate timing from page results
                batch_crawl_ms += result.page_timing.crawl_ms
                batch_scrape_ms += result.page_timing.scrape_ms

                # Track failures by phase (skipped pages are NOT failures)
                if result.status != PageStatus.SKIPPED:
                    if result.failure.phase.value == "crawl":
                        self._crawl_failures += 1
                    elif result.failure.phase.value == "scrape":
                        self._scrape_failures += 1
                self.results.append(result)

                # Add discovered URLs to queue if within depth limit
                if current_depth < max_depth and mode != CrawlMode.ONLY_CRAWL:
                    for url in discovered_urls:
                        normalized = normalize_url_func(url, result.url)
                        if normalized and normalized not in self.visited:
                            self.visited.add(normalized)
                            queue.append(URLTask(
                                url=normalized,
                                parent_url=result.url,
                                depth=current_depth + 1
                            ))

                            # Track by depth
                            next_depth = current_depth + 1
                            if next_depth not in self.urls_by_depth:
                                self.urls_by_depth[next_depth] = []
                            self.urls_by_depth[next_depth].append(normalized)

                # Also add for only_crawl mode (discovery without scraping)
                if mode == CrawlMode.ONLY_CRAWL and current_depth < max_depth:
                    for url in discovered_urls:
                        normalized = normalize_url_func(url, result.url)
                        if normalized and normalized not in self.visited:
                            self.visited.add(normalized)
                            queue.append(URLTask(
                                url=normalized,
                                parent_url=result.url,
                                depth=current_depth + 1
                            ))

                            next_depth = current_depth + 1
                            if next_depth not in self.urls_by_depth:
                                self.urls_by_depth[next_depth] = []
                            self.urls_by_depth[next_depth].append(normalized)

            discovery_time = (time.perf_counter() - discovery_start) * 1000
            self.timing.url_discovery_ms += discovery_time

            # Update accumulated timing (crawl/scrape from page results)
            self.timing.crawling_ms += batch_crawl_ms
            self.timing.scraping_ms += batch_scrape_ms
            self._crawl_time_accumulated += batch_crawl_ms
            self._scrape_time_accumulated += batch_scrape_ms

            # Update total to process with newly discovered URLs
            self._total_to_process = len(self.results) + len(queue)
            self._queue_size = len(queue)

            # Report progress after depth completion
            if self.progress_callback:
                await self.progress_callback({
                    "urls_discovered": self._total_to_process,
                    "urls_processed": len(self.results),
                    "current_depth": current_depth,
                    "queue_size": len(queue),
                })

            # Move to next depth
            current_depth += 1

        # Calculate total time
        self.timing.total_ms = (time.perf_counter() - total_start) * 1000

        # Build depth stats
        depth_stats = [
            DepthStats(depth=d, urls_count=len(urls), urls=urls)
            for d, urls in sorted(self.urls_by_depth.items())
        ]

        return self.results, self.timing, depth_stats

    def get_worker_stats(self) -> dict:
        """Get worker pool statistics."""
        return {
            "num_workers": self.num_workers,
            "urls_processed": len(self.results),
            "urls_visited": len(self.visited),
            "crawl_failures": self._crawl_failures,
            "scrape_failures": self._scrape_failures,
            "total_crawl_time_ms": self._crawl_time_accumulated,
            "total_scrape_time_ms": self._scrape_time_accumulated,
        }

    def get_timing_breakdown(self) -> dict:
        """Get detailed timing breakdown."""
        return {
            "url_discovery_ms": round(self.timing.url_discovery_ms, 2),
            "crawling_ms": round(self.timing.crawling_ms, 2),
            "scraping_ms": round(self.timing.scraping_ms, 2),
            "total_ms": round(self.timing.total_ms, 2),
            "avg_crawl_per_page_ms": round(
                self._crawl_time_accumulated / len(self.results) if self.results else 0, 2
            ),
            "avg_scrape_per_page_ms": round(
                self._scrape_time_accumulated / len(self.results) if self.results else 0, 2
            ),
        }

    def get_failure_stats(self) -> dict:
        """Get failure statistics."""
        total_failed = self._crawl_failures + self._scrape_failures
        return {
            "total_failures": total_failed,
            "crawl_failures": self._crawl_failures,
            "scrape_failures": self._scrape_failures,
            "success_rate": round(
                (len(self.results) - total_failed) / len(self.results) * 100 if self.results else 0, 2
            ),
        }
