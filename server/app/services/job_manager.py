"""
Job manager for crawl job orchestration.

Handles job creation, execution, status tracking, and result retrieval
with support for subdomain crawling and domain filtering.
"""

import uuid
import asyncio
from typing import Optional, Callable
from urllib.parse import urlparse, urljoin

from ..models.crawl import (
    CrawlRequest, CrawlResult, CrawlStatus, CrawlState, CrawlMode,
    TimingMetrics, DepthStats, PageResult, URLTask
)
from ..utils.logger import get_crawler_logger
from .timer import TimerService
from .scraper import ScraperService
from .worker_pool import WorkerPool
from .formatter import OutputFormatter
from .websocket import connection_manager

# Initialize logger
logger = get_crawler_logger()


def get_root_domain(netloc: str) -> str:
    """
    Extract the root domain from a netloc.

    Examples:
        www.example.com -> example.com
        sub.domain.example.com -> example.com
        example.co.uk -> example.co.uk (simplified)
    """
    parts = netloc.split('.')
    if len(parts) <= 2:
        return netloc
    # Simple heuristic: take last 2 parts
    # For more accuracy, use tldextract library
    return '.'.join(parts[-2:])


def is_subdomain_of(domain: str, root_domain: str) -> bool:
    """
    Check if domain is a subdomain of root_domain.

    Examples:
        sub.example.com is subdomain of example.com -> True
        other.com is subdomain of example.com -> False
    """
    domain = domain.lower()
    root_domain = root_domain.lower()

    if domain == root_domain:
        return True
    if domain.endswith('.' + root_domain):
        return True
    return False


class DomainFilter:
    """
    URL domain filter with subdomain and allowed domain support.
    """

    def __init__(
        self,
        seed_url: str,
        allow_subdomains: bool = False,
        allowed_domains: list[str] = None,
    ):
        """
        Initialize domain filter.

        Args:
            seed_url: The seed URL to derive base domain from
            allow_subdomains: Whether to allow all subdomains
            allowed_domains: Additional explicitly allowed domains
        """
        parsed = urlparse(seed_url)
        self.seed_domain = parsed.netloc.lower()
        self.root_domain = get_root_domain(self.seed_domain)
        self.allow_subdomains = allow_subdomains
        self.allowed_domains = set(d.lower() for d in (allowed_domains or []))

        # Always allow the seed domain
        self.allowed_domains.add(self.seed_domain)

    def is_allowed(self, url: str) -> bool:
        """
        Check if URL's domain is allowed.

        Args:
            url: URL to check

        Returns:
            True if domain is allowed
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Check exact match with allowed domains
            if domain in self.allowed_domains:
                return True

            # Check subdomain matching
            if self.allow_subdomains:
                if is_subdomain_of(domain, self.root_domain):
                    return True

            return False
        except Exception:
            return False

    def normalize_url(self, url: str, base_url: str) -> Optional[str]:
        """
        Normalize URL and check if allowed.

        Args:
            url: URL to normalize (may be relative)
            base_url: Base URL for resolving relative URLs

        Returns:
            Normalized URL if allowed, None otherwise
        """
        try:
            # Resolve relative URLs
            absolute_url = urljoin(base_url, url)
            parsed = urlparse(absolute_url)

            # Only allow http/https
            if parsed.scheme not in ('http', 'https'):
                return None

            # Check domain filtering
            if not self.is_allowed(absolute_url):
                return None

            # Build clean URL (remove fragment)
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean_url += f"?{parsed.query}"

            return clean_url.rstrip('/')
        except Exception:
            return None


class JobManager:
    """
    Manages crawl jobs with in-memory storage.

    Features:
    - Job creation and execution
    - Status tracking with real-time updates
    - Subdomain and domain filtering
    - Result retrieval and export
    """

    def __init__(self):
        """Initialize the job manager."""
        self._jobs: dict[str, CrawlStatus] = {}
        self._results: dict[str, CrawlResult] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._domain_filters: dict[str, DomainFilter] = {}

    def create_job(self, request: CrawlRequest) -> str:
        """
        Create a new crawl job.

        Args:
            request: Crawl request parameters

        Returns:
            Unique job ID
        """
        job_id = str(uuid.uuid4())[:8]

        status = CrawlStatus(
            job_id=job_id,
            state=CrawlState.PENDING,
            seed_url=str(request.seed_url),
            mode=request.mode,
            max_depth=request.max_depth,
            worker_count=request.worker_count,
            allow_subdomains=request.allow_subdomains,
            allowed_domains=request.allowed_domains,
            include_child_pages=request.include_child_pages,
        )

        # Create domain filter for this job
        self._domain_filters[job_id] = DomainFilter(
            seed_url=str(request.seed_url),
            allow_subdomains=request.allow_subdomains,
            allowed_domains=request.allowed_domains,
        )

        self._jobs[job_id] = status
        logger.info(f"[JOB] Created job {job_id}: {request.seed_url} (mode={request.mode.value}, depth={request.max_depth}, workers={request.worker_count})")
        return job_id

    def get_status(self, job_id: str) -> Optional[CrawlStatus]:
        """Get current status of a job."""
        return self._jobs.get(job_id)

    def get_result(self, job_id: str) -> Optional[CrawlResult]:
        """Get complete results of a finished job."""
        return self._results.get(job_id)

    async def start_job(self, job_id: str) -> None:
        """
        Start executing a crawl job.

        Args:
            job_id: Job ID to start
        """
        status = self._jobs.get(job_id)
        if not status:
            raise ValueError(f"Job {job_id} not found")

        # Create async task for the job
        task = asyncio.create_task(self._execute_job(job_id))
        self._tasks[job_id] = task

    async def _execute_job(self, job_id: str) -> None:
        """
        Execute the crawl job with domain filtering.

        Args:
            job_id: Job ID to execute
        """
        status = self._jobs[job_id]
        timer = TimerService()
        domain_filter = self._domain_filters.get(job_id)

        try:
            # Update state to running
            status.state = CrawlState.RUNNING
            timer.start_total()
            logger.info(f"[JOB] Starting job {job_id}: {status.seed_url}")

            # Broadcast job started
            await connection_manager.broadcast_status_update(job_id, {
                "state": status.state.value,
                "urls_discovered": 0,
                "urls_processed": 0,
                "current_depth": 0,
            })

            # Create scraper service with enhancements
            scraper = ScraperService(
                mode=status.mode,
                respect_robots=True,
                use_rate_limiting=True,
            )

            # Progress callback for real-time updates
            async def on_progress(progress: dict):
                await connection_manager.broadcast_status_update(job_id, {
                    "state": status.state.value,
                    "urls_discovered": progress["urls_discovered"],
                    "urls_processed": progress["urls_processed"],
                    "current_depth": progress["current_depth"],
                    "queue_size": progress.get("queue_size", 0),
                })

            # Create worker pool with progress callback
            worker_pool = WorkerPool(
                num_workers=status.worker_count,
                process_callback=scraper.fetch_page,
                progress_callback=on_progress,
            )

            # Get base domain for BFS
            parsed = urlparse(status.seed_url)
            base_domain = parsed.netloc

            # URL normalization function using domain filter
            def normalize_url(url: str, base_url: str) -> Optional[str]:
                if domain_filter:
                    return domain_filter.normalize_url(url, base_url)
                # Fallback to simple same-domain filtering
                try:
                    absolute_url = urljoin(base_url, url)
                    parsed_url = urlparse(absolute_url)

                    if parsed_url.scheme not in ('http', 'https'):
                        return None
                    if parsed_url.netloc != base_domain:
                        return None

                    clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                    if parsed_url.query:
                        clean_url += f"?{parsed_url.query}"
                    return clean_url.rstrip('/')
                except Exception:
                    return None

            # Execute BFS crawl with worker pool
            pages, timing, depth_stats = await worker_pool.crawl_bfs(
                seed_url=status.seed_url,
                max_depth=status.max_depth,
                mode=status.mode,
                base_domain=base_domain,
                normalize_url_func=normalize_url,
                include_child_pages=status.include_child_pages,
            )

            # Stop total timer
            timer.stop_total()

            # Update status with final data
            status.urls_discovered = sum(ds.urls_count for ds in depth_stats)
            status.urls_processed = len(pages)
            status.urls_by_depth = depth_stats
            status.current_depth = max(ds.depth for ds in depth_stats) if depth_stats else 0

            # Merge timing
            status.timing = TimingMetrics(
                url_discovery_ms=timing.url_discovery_ms,
                crawling_ms=timing.crawling_ms,
                scraping_ms=timing.scraping_ms,
                total_ms=timer.total_ms,
            )

            # Create final result
            scraped_count = sum(1 for p in pages if p.content)
            result = CrawlResult(
                job_id=job_id,
                seed_url=status.seed_url,
                mode=status.mode,
                max_depth=status.max_depth,
                worker_count=status.worker_count,
                allow_subdomains=status.allow_subdomains,
                allowed_domains=status.allowed_domains,
                include_child_pages=status.include_child_pages,
                state=CrawlState.COMPLETED,
                timing=status.timing,
                urls_by_depth=depth_stats,
                pages=pages,
                total_urls_discovered=status.urls_discovered,
                total_pages_scraped=scraped_count,
            )

            self._results[job_id] = result
            status.state = CrawlState.COMPLETED

            logger.info(f"[JOB] Completed job {job_id}: {status.urls_discovered} URLs discovered, {status.urls_processed} pages processed in {timer.total_ms:.2f}ms")

            # Broadcast job completed
            await connection_manager.broadcast_job_completed(job_id, {
                "state": status.state.value,
                "urls_discovered": status.urls_discovered,
                "urls_processed": status.urls_processed,
                "current_depth": status.current_depth,
                "timing": {
                    "total_ms": status.timing.total_ms,
                    "crawling_ms": status.timing.crawling_ms,
                    "scraping_ms": status.timing.scraping_ms,
                },
            })

            # Close scraper
            await scraper.close()

        except Exception as e:
            timer.stop_total()
            status.state = CrawlState.FAILED
            status.error = str(e)
            status.timing.total_ms = timer.total_ms
            logger.error(f"[JOB] Failed job {job_id}: {e}")

            # Broadcast job failed
            await connection_manager.broadcast_job_failed(job_id, str(e))

    def get_json_output(self, job_id: str) -> Optional[str]:
        """Get JSON formatted output for a job."""
        result = self._results.get(job_id)
        if result:
            return OutputFormatter.to_json(result)
        return None

    def get_markdown_output(self, job_id: str) -> Optional[str]:
        """Get Markdown formatted output for a job."""
        result = self._results.get(job_id)
        if result:
            return OutputFormatter.to_markdown(result)
        return None

    def list_jobs(self) -> list[CrawlStatus]:
        """List all jobs."""
        return list(self._jobs.values())

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and its results."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._results.pop(job_id, None)
            self._domain_filters.pop(job_id, None)
            task = self._tasks.pop(job_id, None)
            if task and not task.done():
                task.cancel()
            return True
        return False


# Global job manager instance
job_manager = JobManager()
