"""
Knowledge Base crawler with isolated BFS state and path scope enforcement.

This module provides a crawler implementation specifically designed for
Knowledge Base-scoped crawling, where each KB has:
- Isolated BFS queue and visited set
- Path-based scope boundaries
- Independent progress tracking
- Tagged results
"""

import asyncio
import time
from collections import deque
from datetime import datetime
from typing import Optional, Callable, Awaitable

from ..models.crawl import (
    CrawlMode, PageStatus, PageTiming, FailureInfo, FailurePhase, URLTask
)
from ..models.knowledge_base import (
    KnowledgeBaseConfig, KBCrawlState, KnowledgeBaseCrawlStatus,
    KBPageResult, KBCrawlResult, KBDepthStats, KBURLTask
)
from ..utils.logger import get_crawler_logger
from .path_scope_filter import PathScopeFilter
from .scraper import ScraperService
from .timer import PageTimer

logger = get_crawler_logger()


# Type aliases for callbacks
ProgressCallback = Callable[[KnowledgeBaseCrawlStatus], Awaitable[None]]
PageCompleteCallback = Callable[[KBPageResult], Awaitable[None]]


class KnowledgeBaseCrawler:
    """
    Crawler that enforces path-based scope boundaries per Knowledge Base.

    Key features:
    - Isolated BFS queue, visited set, and results per KB
    - PathScopeFilter for URL boundary enforcement
    - Tags all results with kb_id and kb_name
    - Tracks out-of-scope URLs as a metric
    - Reports progress via callbacks

    Example:
        crawler = KnowledgeBaseCrawler(
            kb_config=kb_config,
            base_domain="gmu.edu",
            scraper=scraper,
            mode=CrawlMode.CRAWL_SCRAPE,
            max_depth=3,
        )
        result = await crawler.crawl(semaphore)
    """

    def __init__(
        self,
        kb_config: KnowledgeBaseConfig,
        base_domain: str,
        scraper: ScraperService,
        mode: CrawlMode,
        max_depth: int,
        allow_subdomains: bool = False,
        include_child_pages: bool = True,
        auto_discover_prefixes: bool = False,
        on_progress: Optional[ProgressCallback] = None,
        on_page_complete: Optional[PageCompleteCallback] = None,
    ):
        """
        Initialize the Knowledge Base crawler.

        Args:
            kb_config: Knowledge Base configuration
            base_domain: Base domain for URL validation
            scraper: ScraperService instance for fetching pages
            mode: Crawl execution mode
            max_depth: Maximum crawl depth (can be overridden by kb_config)
            allow_subdomains: Whether to allow subdomains within scope
            include_child_pages: Whether to scrape child pages (depth > 1)
            auto_discover_prefixes: Whether to auto-discover path prefixes from entry page links
            on_progress: Async callback for progress updates
            on_page_complete: Async callback when each page completes
        """
        self.kb_config = kb_config
        self.base_domain = base_domain
        self.scraper = scraper
        self.mode = mode
        self.max_depth = kb_config.max_depth or max_depth
        self.include_child_pages = include_child_pages
        self.auto_discover_prefixes = auto_discover_prefixes
        self.on_progress = on_progress
        self.on_page_complete = on_page_complete

        # Initialize scope filter
        self.scope_filter = PathScopeFilter(
            kb_id=kb_config.kb_id,
            kb_name=kb_config.name,
            base_domain=base_domain,
            allowed_prefixes=kb_config.get_allowed_path_prefixes(),
            allow_subdomains=allow_subdomains,
        )

        # Isolated BFS state
        self.queue: deque[KBURLTask] = deque()
        self.visited: set[str] = set()
        self.results: list[KBPageResult] = []
        self.urls_by_depth: dict[int, list[str]] = {}

        # Metrics
        self.urls_discovered = 0
        self.urls_processed = 0
        self.urls_out_of_scope = 0
        self.current_depth = 0
        self.pages_scraped = 0
        self.pages_crawled = 0
        self.pages_failed = 0

        # Timing
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self._total_crawl_ms = 0.0
        self._total_scrape_ms = 0.0

        # State
        self.state = KBCrawlState.PENDING
        self.error: Optional[str] = None

        logger.info(
            f"[KB:{kb_config.name}] Initialized crawler with "
            f"prefixes={kb_config.get_allowed_path_prefixes()}, "
            f"max_depth={self.max_depth}"
        )

    def _seed_queue(self) -> None:
        """Initialize queue with entry URLs."""
        for entry_url in self.kb_config.entry_urls:
            url_str = str(entry_url)

            # Validate entry URL is in scope (should always pass for entry URLs)
            is_allowed, matched_prefix, reason = self.scope_filter.is_in_scope(url_str)
            if not is_allowed:
                logger.warning(
                    f"[KB:{self.kb_config.name}] Entry URL {url_str} not in scope: {reason}"
                )
                continue

            normalized = self.scope_filter.normalize_url(url_str)
            if normalized and normalized not in self.visited:
                self.queue.append(KBURLTask(
                    url=normalized,
                    depth=1,
                    parent_url=None,
                    matched_prefix=matched_prefix or "",
                ))
                self.visited.add(normalized)
                self.urls_discovered += 1
                self._record_url_at_depth(normalized, 1)

                logger.debug(f"[KB:{self.kb_config.name}] Seeded queue with: {normalized}")

    def _record_url_at_depth(self, url: str, depth: int) -> None:
        """Track URLs by depth level."""
        if depth not in self.urls_by_depth:
            self.urls_by_depth[depth] = []
        self.urls_by_depth[depth].append(url)

    def _filter_discovered_urls(
        self,
        discovered_urls: list[str],
        parent_url: str,
        parent_depth: int,
    ) -> list[KBURLTask]:
        """
        Filter discovered URLs through scope filter.

        Only returns URLs that are:
        1. Within KB path scope
        2. Not already visited
        3. Within max_depth

        Args:
            discovered_urls: Raw URLs discovered from page
            parent_url: URL of the page that contained these links
            parent_depth: Depth of the parent page

        Returns:
            List of KBURLTask for new URLs to crawl
        """
        new_tasks = []
        new_depth = parent_depth + 1

        # Don't add more URLs if we've reached max depth
        if new_depth > self.max_depth:
            return new_tasks

        logger.debug(
            f"[KB:{self.kb_config.name}] Filtering {len(discovered_urls)} URLs from {parent_url} (depth {parent_depth})"
        )

        for url in discovered_urls:
            # Check scope
            is_allowed, matched_prefix, reason = self.scope_filter.is_in_scope(url, parent_url)

            if not is_allowed:
                self.urls_out_of_scope += 1
                # Log more details for path-based rejections
                if "path_out_of_scope" in reason:
                    logger.debug(
                        f"[KB:{self.kb_config.name}] Rejected (path): {url} - "
                        f"allowed prefixes: {self.scope_filter.allowed_prefixes}"
                    )
                else:
                    logger.debug(
                        f"[KB:{self.kb_config.name}] Out of scope: {url} ({reason})"
                    )
                continue

            # Normalize and check visited
            normalized = self.scope_filter.normalize_url(url, parent_url)
            if not normalized or normalized in self.visited:
                continue

            # Add to queue
            self.visited.add(normalized)
            self.urls_discovered += 1
            self._record_url_at_depth(normalized, new_depth)

            new_tasks.append(KBURLTask(
                url=normalized,
                depth=new_depth,
                parent_url=parent_url,
                matched_prefix=matched_prefix or "",
            ))

            logger.debug(
                f"[KB:{self.kb_config.name}] Discovered: {normalized} "
                f"(depth={new_depth}, prefix={matched_prefix})"
            )

        return new_tasks

    async def _process_url(
        self,
        task: KBURLTask,
        skip_scraping: bool = False,
    ) -> Optional[KBPageResult]:
        """
        Process a single URL and return KB-tagged result.

        Args:
            task: URL task to process
            skip_scraping: If True, only crawl without scraping content

        Returns:
            KBPageResult if successful, None if failed
        """
        try:
            # Create URLTask for scraper (it expects the base URLTask)
            url_task = URLTask(
                url=task.url,
                parent_url=task.parent_url,
                depth=task.depth,
            )

            # Use existing scraper
            page_result, discovered_urls = await self.scraper.fetch_page(url_task)

            # Handle skip_scraping for child pages
            if skip_scraping:
                page_result.content = None
                page_result.title = None
                page_result.headings = []
                page_result.status = PageStatus.SKIPPED

            # Convert to KB-tagged result
            kb_result = KBPageResult(
                url=page_result.url,
                parent_url=page_result.parent_url,
                depth=page_result.depth,
                title=page_result.title,
                content=page_result.content,
                headings=page_result.headings,
                links_found=page_result.links_found,
                timing_ms=page_result.timing_ms,
                page_timing=page_result.page_timing,
                error=page_result.error,
                failure=page_result.failure,
                is_same_domain=page_result.is_same_domain,
                is_subdomain=page_result.is_subdomain,
                status=page_result.status,
                skip_reason=page_result.skip_reason,
                kb_id=self.kb_config.kb_id,
                kb_name=self.kb_config.name,
                matched_prefix=task.matched_prefix,
            )

            # Update timing accumulators
            self._total_crawl_ms += page_result.page_timing.crawl_ms
            self._total_scrape_ms += page_result.page_timing.scrape_ms

            # Auto-discover prefixes from page links (depth 1 and 2)
            # This helps catch related paths that may use different prefixes
            if self.auto_discover_prefixes and task.depth <= 2 and discovered_urls:
                new_prefixes = self.scope_filter.discover_prefixes_from_urls(
                    discovered_urls,
                    self.base_domain,
                )
                for prefix in new_prefixes:
                    self.scope_filter.add_prefix(prefix)
                if new_prefixes:
                    logger.info(
                        f"[KB:{self.kb_config.name}] Auto-discovered {len(new_prefixes)} "
                        f"prefixes from depth {task.depth} page ({task.url}): {new_prefixes}"
                    )
                logger.debug(
                    f"[KB:{self.kb_config.name}] Current allowed prefixes: "
                    f"{self.scope_filter.allowed_prefixes}"
                )

            # Filter and queue discovered URLs
            new_tasks = self._filter_discovered_urls(
                discovered_urls,
                task.url,
                task.depth,
            )
            self.queue.extend(new_tasks)

            # Update metrics
            self.urls_processed += 1
            if kb_result.status == PageStatus.SCRAPED:
                self.pages_scraped += 1
            elif kb_result.status == PageStatus.CRAWLED:
                self.pages_crawled += 1
            elif kb_result.status == PageStatus.ERROR:
                self.pages_failed += 1

            self.results.append(kb_result)

            # Callback for real-time updates
            if self.on_page_complete:
                await self.on_page_complete(kb_result)

            logger.debug(
                f"[KB:{self.kb_config.name}] Processed: {task.url} "
                f"(status={kb_result.status.value}, links={kb_result.links_found})"
            )

            return kb_result

        except Exception as e:
            logger.error(f"[KB:{self.kb_config.name}] Error processing {task.url}: {e}")
            self.urls_processed += 1
            self.pages_failed += 1

            # Create error result
            error_result = KBPageResult(
                url=task.url,
                parent_url=task.parent_url,
                depth=task.depth,
                error=str(e),
                status=PageStatus.ERROR,
                failure=FailureInfo(
                    phase=FailurePhase.CRAWL,
                    reason=str(e),
                ),
                page_timing=PageTiming(),
                kb_id=self.kb_config.kb_id,
                kb_name=self.kb_config.name,
                matched_prefix=task.matched_prefix,
            )
            self.results.append(error_result)

            if self.on_page_complete:
                await self.on_page_complete(error_result)

            return error_result

    async def crawl(self, semaphore: asyncio.Semaphore) -> KBCrawlResult:
        """
        Execute BFS crawl for this Knowledge Base.

        Args:
            semaphore: Shared semaphore for worker pool concurrency control

        Returns:
            KBCrawlResult with all crawled pages and metrics
        """
        self.started_at = datetime.now()
        self.state = KBCrawlState.RUNNING

        logger.info(f"[KB:{self.kb_config.name}] Starting crawl")

        try:
            # Seed the queue with entry URLs
            self._seed_queue()

            if not self.queue:
                self.state = KBCrawlState.SKIPPED
                self.error = "No valid entry URLs in scope"
                logger.warning(f"[KB:{self.kb_config.name}] Skipped: no valid entry URLs")
                return self._build_result()

            # Handle ONLY_SCRAPE mode - just process seed URLs
            if self.mode == CrawlMode.ONLY_SCRAPE:
                # Process only the seed URLs
                seed_tasks = list(self.queue)
                self.queue.clear()

                async def process_with_semaphore(task: KBURLTask):
                    async with semaphore:
                        return await self._process_url(task, skip_scraping=False)

                await asyncio.gather(
                    *[process_with_semaphore(task) for task in seed_tasks],
                    return_exceptions=True,
                )

                self.state = KBCrawlState.COMPLETED
                self.completed_at = datetime.now()
                await self._report_progress()
                return self._build_result()

            # BFS loop
            while self.queue:
                # Get all tasks at current depth
                current_depth_tasks: list[KBURLTask] = []
                peek_depth = self.queue[0].depth if self.queue else 0

                while self.queue and self.queue[0].depth == peek_depth:
                    current_depth_tasks.append(self.queue.popleft())

                if not current_depth_tasks:
                    if self.queue:
                        continue
                    break

                self.current_depth = peek_depth
                logger.info(
                    f"[KB:{self.kb_config.name}] Processing depth {peek_depth}: "
                    f"{len(current_depth_tasks)} URLs"
                )

                # Report progress before processing
                await self._report_progress()

                # Determine if we should skip scraping for this depth
                skip_scraping = (
                    not self.include_child_pages and
                    peek_depth > 1 and
                    self.mode != CrawlMode.ONLY_CRAWL
                )

                # Process batch concurrently (with semaphore)
                async def process_with_semaphore(task: KBURLTask):
                    async with semaphore:
                        return await self._process_url(task, skip_scraping=skip_scraping)

                await asyncio.gather(
                    *[process_with_semaphore(task) for task in current_depth_tasks],
                    return_exceptions=True,
                )

                # Log queue state after processing this depth
                next_depth_count = len([t for t in self.queue if t.depth == peek_depth + 1])
                logger.info(
                    f"[KB:{self.kb_config.name}] After depth {peek_depth}: "
                    f"queued {next_depth_count} URLs for depth {peek_depth + 1}, "
                    f"total discovered: {self.urls_discovered}, "
                    f"out of scope: {self.urls_out_of_scope}, "
                    f"allowed prefixes: {self.scope_filter.allowed_prefixes}"
                )

                # Report progress after processing depth level
                await self._report_progress()

            self.state = KBCrawlState.COMPLETED
            logger.info(
                f"[KB:{self.kb_config.name}] Completed: "
                f"{self.urls_processed} URLs processed, "
                f"{self.urls_out_of_scope} out of scope"
            )

        except asyncio.CancelledError:
            self.state = KBCrawlState.FAILED
            self.error = "Crawl cancelled"
            logger.warning(f"[KB:{self.kb_config.name}] Crawl cancelled")
            raise

        except Exception as e:
            self.state = KBCrawlState.FAILED
            self.error = str(e)
            logger.error(f"[KB:{self.kb_config.name}] Crawl failed: {e}")

        finally:
            self.completed_at = datetime.now()
            await self._report_progress()

        return self._build_result()

    async def _report_progress(self) -> None:
        """Report progress via callback."""
        if self.on_progress:
            status = self.get_status()
            try:
                await self.on_progress(status)
            except Exception as e:
                logger.warning(f"[KB:{self.kb_config.name}] Progress callback failed: {e}")

    def get_status(self) -> KnowledgeBaseCrawlStatus:
        """Get current status for this KB."""
        duration_ms = 0.0
        if self.started_at:
            end_time = self.completed_at or datetime.now()
            duration_ms = (end_time - self.started_at).total_seconds() * 1000

        return KnowledgeBaseCrawlStatus(
            kb_id=self.kb_config.kb_id,
            kb_name=self.kb_config.name,
            state=self.state,
            entry_urls=[str(u) for u in self.kb_config.entry_urls],
            allowed_prefixes=self.scope_filter.allowed_prefixes,  # Include auto-discovered prefixes
            urls_discovered=self.urls_discovered,
            urls_processed=self.urls_processed,
            urls_queued=len(self.queue),
            urls_skipped_out_of_scope=self.urls_out_of_scope,
            current_depth=self.current_depth,
            max_depth=self.max_depth,
            started_at=self.started_at.isoformat() if self.started_at else None,
            completed_at=self.completed_at.isoformat() if self.completed_at else None,
            duration_ms=duration_ms,
            error=self.error,
            pages_scraped=self.pages_scraped,
            pages_crawled=self.pages_crawled,
            pages_failed=self.pages_failed,
        )

    def _build_result(self) -> KBCrawlResult:
        """Build final result object."""
        duration_ms = 0.0
        if self.started_at:
            end_time = self.completed_at or datetime.now()
            duration_ms = (end_time - self.started_at).total_seconds() * 1000

        # Build depth stats
        depth_stats = [
            KBDepthStats(
                depth=d,
                urls_count=len(urls),
                urls=urls,
            )
            for d, urls in sorted(self.urls_by_depth.items())
        ]

        return KBCrawlResult(
            kb_id=self.kb_config.kb_id,
            kb_name=self.kb_config.name,
            entry_urls=[str(u) for u in self.kb_config.entry_urls],
            allowed_prefixes=self.scope_filter.allowed_prefixes,  # Include auto-discovered prefixes
            state=self.state,
            pages=self.results,
            urls_by_depth=depth_stats,
            urls_discovered=self.urls_discovered,
            urls_processed=self.urls_processed,
            urls_out_of_scope=self.urls_out_of_scope,
            pages_scraped=self.pages_scraped,
            pages_crawled=self.pages_crawled,
            pages_failed=self.pages_failed,
            started_at=self.started_at.isoformat() if self.started_at else None,
            completed_at=self.completed_at.isoformat() if self.completed_at else None,
            duration_ms=duration_ms,
            error=self.error,
        )

    def get_scope_stats(self) -> dict:
        """Get scope filtering statistics."""
        return self.scope_filter.get_stats()
