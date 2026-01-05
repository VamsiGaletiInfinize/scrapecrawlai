import uuid
import asyncio
from typing import Optional
from urllib.parse import urlparse

from ..models.crawl import (
    CrawlRequest, CrawlResult, CrawlStatus, CrawlState, CrawlMode,
    TimingMetrics, DepthStats, PageResult, URLTask
)
from .timer import TimerService
from .scraper import ScraperService
from .worker_pool import WorkerPool
from .formatter import OutputFormatter


class JobManager:
    """
    Manages crawl jobs with in-memory storage.

    Handles job creation, execution, status tracking, and result retrieval.
    """

    def __init__(self):
        """Initialize the job manager."""
        self._jobs: dict[str, CrawlStatus] = {}
        self._results: dict[str, CrawlResult] = {}
        self._tasks: dict[str, asyncio.Task] = {}

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
        )

        self._jobs[job_id] = status
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
        Execute the crawl job.

        Args:
            job_id: Job ID to execute
        """
        status = self._jobs[job_id]
        timer = TimerService()

        try:
            # Update state to running
            status.state = CrawlState.RUNNING
            timer.start_total()

            # Create scraper service
            scraper = ScraperService(mode=status.mode)

            # Create worker pool
            worker_pool = WorkerPool(
                num_workers=status.worker_count,
                process_callback=scraper.fetch_page,
            )

            # Get base domain for same-domain filtering
            parsed = urlparse(status.seed_url)
            base_domain = parsed.netloc

            def normalize_url(url: str, base_url: str) -> Optional[str]:
                """Normalize URL and filter to same domain."""
                try:
                    from urllib.parse import urljoin, urlparse
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
                state=CrawlState.COMPLETED,
                timing=status.timing,
                urls_by_depth=depth_stats,
                pages=pages,
                total_urls_discovered=status.urls_discovered,
                total_pages_scraped=scraped_count,
            )

            self._results[job_id] = result
            status.state = CrawlState.COMPLETED

            # Close scraper
            await scraper.close()

        except Exception as e:
            timer.stop_total()
            status.state = CrawlState.FAILED
            status.error = str(e)
            status.timing.total_ms = timer.total_ms

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
            task = self._tasks.pop(job_id, None)
            if task and not task.done():
                task.cancel()
            return True
        return False


# Global job manager instance
job_manager = JobManager()
