"""
Multi-Knowledge Base job manager for orchestrating category-scoped crawls.

This module provides:
- Job creation and lifecycle management for multi-KB crawls
- Parallel KB crawl coordination with shared resources
- Aggregate progress tracking across KBs
- WebSocket broadcasting for real-time updates
"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional, Dict

from ..models.crawl import CrawlState, CrawlMode
from ..models.knowledge_base import (
    MultiKBCrawlRequest, MultiKBCrawlStatus, MultiKBCrawlResult,
    KnowledgeBaseConfig, KBCrawlState, KnowledgeBaseCrawlStatus,
    KBCrawlResult, KBPageResult, MultiKBSummary
)
from ..utils.logger import get_crawler_logger
from .kb_crawler import KnowledgeBaseCrawler
from .scraper import ScraperService
from .websocket import connection_manager
from .path_scope_filter import OverlapDetector

logger = get_crawler_logger()


class MultiKBJobManager:
    """
    Orchestrates multi-Knowledge-Base crawl jobs.

    Key responsibilities:
    1. Create and track multi-KB jobs
    2. Coordinate parallel KB crawls with shared semaphore
    3. Aggregate progress across KBs
    4. Broadcast per-KB and overall progress via WebSocket

    Example:
        manager = MultiKBJobManager()
        job_id = manager.create_job(request)
        await manager.start_job(job_id, request)
        status = manager.get_status(job_id)
    """

    def __init__(self):
        """Initialize the multi-KB job manager."""
        self._jobs: Dict[str, MultiKBCrawlStatus] = {}
        self._results: Dict[str, MultiKBCrawlResult] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._kb_crawlers: Dict[str, Dict[str, KnowledgeBaseCrawler]] = {}
        self._requests: Dict[str, MultiKBCrawlRequest] = {}
        self._lock = asyncio.Lock()

    def create_job(self, request: MultiKBCrawlRequest) -> str:
        """
        Create a new multi-KB crawl job.

        Args:
            request: Multi-KB crawl request

        Returns:
            Unique job ID
        """
        job_id = uuid.uuid4().hex[:8]

        # Filter to only active KBs
        active_kbs = [kb for kb in request.knowledge_bases if kb.is_active]

        if not active_kbs:
            raise ValueError("At least one active Knowledge Base is required")

        # Check for overlapping scopes and warn
        overlaps = OverlapDetector.detect_overlaps(active_kbs)
        if overlaps:
            for kb1_id, kb2_id, overlap_desc in overlaps:
                kb1_name = next((kb.name for kb in active_kbs if kb.kb_id == kb1_id), kb1_id)
                kb2_name = next((kb.name for kb in active_kbs if kb.kb_id == kb2_id), kb2_id)
                logger.warning(
                    f"[JOB:{job_id}] Overlapping scopes detected between "
                    f"'{kb1_name}' and '{kb2_name}': {overlap_desc}"
                )

        # Initialize KB statuses
        kb_statuses = []
        for kb in active_kbs:
            kb_statuses.append(KnowledgeBaseCrawlStatus(
                kb_id=kb.kb_id,
                kb_name=kb.name,
                state=KBCrawlState.PENDING,
                entry_urls=[str(u) for u in kb.entry_urls],
                allowed_prefixes=kb.get_allowed_path_prefixes(),
                max_depth=kb.max_depth or request.max_depth,
            ))

        # Create job status
        self._jobs[job_id] = MultiKBCrawlStatus(
            job_id=job_id,
            domain=str(request.domain),
            state=CrawlState.PENDING,
            mode=request.mode,
            total_kbs=len(kb_statuses),
            kbs_completed=0,
            kbs_failed=0,
            kbs_running=0,
            kbs_pending=len(kb_statuses),
            knowledge_bases=kb_statuses,
            total_urls_discovered=0,
            total_urls_processed=0,
            total_urls_out_of_scope=0,
        )

        # Store request for later use
        self._requests[job_id] = request

        logger.info(
            f"[JOB:{job_id}] Created multi-KB job: {len(active_kbs)} KBs, "
            f"domain={request.domain}, mode={request.mode.value}"
        )

        return job_id

    async def start_job(self, job_id: str, request: Optional[MultiKBCrawlRequest] = None) -> None:
        """
        Start executing a multi-KB crawl job.

        Args:
            job_id: Job ID to start
            request: Optional request (uses stored request if not provided)
        """
        if job_id not in self._jobs:
            raise ValueError(f"Job {job_id} not found")

        request = request or self._requests.get(job_id)
        if not request:
            raise ValueError(f"Request for job {job_id} not found")

        # Create async task for the job
        task = asyncio.create_task(self._execute_job(job_id, request))
        self._tasks[job_id] = task

    async def _execute_job(self, job_id: str, request: MultiKBCrawlRequest) -> None:
        """
        Execute the multi-KB crawl job.

        Args:
            job_id: Job ID to execute
            request: Multi-KB crawl request
        """
        job_status = self._jobs[job_id]
        job_status.state = CrawlState.RUNNING
        job_status.started_at = datetime.now().isoformat()

        logger.info(f"[JOB:{job_id}] Starting multi-KB crawl execution")

        scraper: Optional[ScraperService] = None

        try:
            # Broadcast job started
            await connection_manager.broadcast_to_job(job_id, {
                "type": "job_started",
                "job_id": job_id,
                "total_kbs": job_status.total_kbs,
                "domain": str(request.domain),
            })

            # Create shared scraper service
            scraper = ScraperService(
                mode=request.mode,
                respect_robots=request.respect_robots_txt,
                use_rate_limiting=True,
            )

            # Shared semaphore for all KB crawlers (controls total concurrency)
            semaphore = asyncio.Semaphore(request.worker_count)

            # Create crawlers for active KBs
            self._kb_crawlers[job_id] = {}
            active_kbs = [kb for kb in request.knowledge_bases if kb.is_active]

            for kb_config in active_kbs:
                crawler = KnowledgeBaseCrawler(
                    kb_config=kb_config,
                    base_domain=str(request.domain),
                    scraper=scraper,
                    mode=request.mode,
                    max_depth=request.max_depth,
                    allow_subdomains=request.allow_subdomains,
                    include_child_pages=request.include_child_pages,
                    auto_discover_prefixes=request.auto_discover_prefixes,
                    on_progress=lambda status, jid=job_id: self._on_kb_progress(jid, status),
                    on_page_complete=lambda page, jid=job_id: self._on_page_complete(jid, page),
                )
                self._kb_crawlers[job_id][kb_config.kb_id] = crawler

            # Execute KB crawls with controlled parallelism
            kb_semaphore = asyncio.Semaphore(request.parallel_kbs)

            async def crawl_kb_with_limit(crawler: KnowledgeBaseCrawler) -> KBCrawlResult:
                async with kb_semaphore:
                    logger.info(f"[JOB:{job_id}] Starting KB: {crawler.kb_config.name}")
                    return await crawler.crawl(semaphore)

            # Run all KB crawls
            kb_results = await asyncio.gather(
                *[crawl_kb_with_limit(c) for c in self._kb_crawlers[job_id].values()],
                return_exceptions=True,
            )

            # Process results
            final_kb_results: list[KBCrawlResult] = []
            for i, result in enumerate(kb_results):
                if isinstance(result, Exception):
                    kb_id = list(self._kb_crawlers[job_id].keys())[i]
                    kb_name = list(self._kb_crawlers[job_id].values())[i].kb_config.name
                    logger.error(f"[JOB:{job_id}] KB {kb_name} failed with exception: {result}")

                    # Create failed result
                    failed_result = KBCrawlResult(
                        kb_id=kb_id,
                        kb_name=kb_name,
                        entry_urls=[],
                        allowed_prefixes=[],
                        state=KBCrawlState.FAILED,
                        error=str(result),
                        pages=[],
                        urls_by_depth=[],
                        urls_discovered=0,
                        urls_processed=0,
                        urls_out_of_scope=0,
                        pages_scraped=0,
                        pages_crawled=0,
                        pages_failed=0,
                        duration_ms=0,
                    )
                    final_kb_results.append(failed_result)
                else:
                    final_kb_results.append(result)

            # Build final result
            self._results[job_id] = self._build_final_result(job_id, request, final_kb_results)
            job_status.state = CrawlState.COMPLETED
            job_status.completed_at = datetime.now().isoformat()

            logger.info(
                f"[JOB:{job_id}] Multi-KB crawl completed: "
                f"{len(final_kb_results)} KBs, "
                f"{sum(r.urls_processed for r in final_kb_results)} total URLs"
            )

            # Broadcast completion
            await connection_manager.broadcast_to_job(job_id, {
                "type": "job_completed",
                "job_id": job_id,
                "summary": self._get_summary(final_kb_results),
            })

        except asyncio.CancelledError:
            job_status.state = CrawlState.FAILED
            job_status.error = "Job cancelled"
            logger.warning(f"[JOB:{job_id}] Multi-KB crawl cancelled")
            await connection_manager.broadcast_job_failed(job_id, "Job cancelled")
            raise

        except Exception as e:
            logger.error(f"[JOB:{job_id}] Multi-KB job failed: {e}")
            job_status.state = CrawlState.FAILED
            job_status.error = str(e)
            job_status.completed_at = datetime.now().isoformat()

            await connection_manager.broadcast_job_failed(job_id, str(e))

        finally:
            # Cleanup
            if scraper:
                await scraper.close()
            self._kb_crawlers.pop(job_id, None)

    async def _on_kb_progress(self, job_id: str, kb_status: KnowledgeBaseCrawlStatus) -> None:
        """
        Handle progress update from a KB crawler.

        Args:
            job_id: Job ID
            kb_status: Updated KB status
        """
        async with self._lock:
            job_status = self._jobs.get(job_id)
            if not job_status:
                return

            # Update KB status in job
            for i, kb in enumerate(job_status.knowledge_bases):
                if kb.kb_id == kb_status.kb_id:
                    job_status.knowledge_bases[i] = kb_status
                    break

            # Recalculate aggregates
            job_status.kbs_pending = sum(
                1 for kb in job_status.knowledge_bases
                if kb.state == KBCrawlState.PENDING
            )
            job_status.kbs_running = sum(
                1 for kb in job_status.knowledge_bases
                if kb.state == KBCrawlState.RUNNING
            )
            job_status.kbs_completed = sum(
                1 for kb in job_status.knowledge_bases
                if kb.state == KBCrawlState.COMPLETED
            )
            job_status.kbs_failed = sum(
                1 for kb in job_status.knowledge_bases
                if kb.state == KBCrawlState.FAILED
            )
            job_status.total_urls_discovered = sum(
                kb.urls_discovered for kb in job_status.knowledge_bases
            )
            job_status.total_urls_processed = sum(
                kb.urls_processed for kb in job_status.knowledge_bases
            )
            job_status.total_urls_out_of_scope = sum(
                kb.urls_skipped_out_of_scope for kb in job_status.knowledge_bases
            )

        # Broadcast update
        await connection_manager.broadcast_to_job(job_id, {
            "type": "multi_kb_progress",
            "job_id": job_id,
            "timestamp": datetime.now().isoformat(),
            "overall": {
                "state": job_status.state.value,
                "kbs_pending": job_status.kbs_pending,
                "kbs_running": job_status.kbs_running,
                "kbs_completed": job_status.kbs_completed,
                "kbs_failed": job_status.kbs_failed,
                "total_urls_discovered": job_status.total_urls_discovered,
                "total_urls_processed": job_status.total_urls_processed,
                "total_urls_out_of_scope": job_status.total_urls_out_of_scope,
            },
            "kb_update": {
                "kb_id": kb_status.kb_id,
                "kb_name": kb_status.kb_name,
                "state": kb_status.state.value,
                "urls_discovered": kb_status.urls_discovered,
                "urls_processed": kb_status.urls_processed,
                "urls_queued": kb_status.urls_queued,
                "urls_skipped_out_of_scope": kb_status.urls_skipped_out_of_scope,
                "current_depth": kb_status.current_depth,
                "max_depth": kb_status.max_depth,
                "pages_scraped": kb_status.pages_scraped,
                "pages_failed": kb_status.pages_failed,
            },
        })

    async def _on_page_complete(self, job_id: str, page: KBPageResult) -> None:
        """
        Handle individual page completion.

        Args:
            job_id: Job ID
            page: Completed page result
        """
        # Broadcast individual page update (optional, for detailed UI)
        await connection_manager.broadcast_to_job(job_id, {
            "type": "page_complete",
            "job_id": job_id,
            "kb_id": page.kb_id,
            "kb_name": page.kb_name,
            "url": page.url,
            "status": page.status.value,
            "depth": page.depth,
            "matched_prefix": page.matched_prefix,
        })

    def _build_final_result(
        self,
        job_id: str,
        request: MultiKBCrawlRequest,
        kb_results: list[KBCrawlResult],
    ) -> MultiKBCrawlResult:
        """Build the final aggregated result."""
        # Calculate summary
        summary = MultiKBSummary(
            total_kbs=len(kb_results),
            kbs_completed=sum(1 for kb in kb_results if kb.state == KBCrawlState.COMPLETED),
            kbs_failed=sum(1 for kb in kb_results if kb.state == KBCrawlState.FAILED),
            kbs_skipped=sum(1 for kb in kb_results if kb.state == KBCrawlState.SKIPPED),
            total_pages=sum(len(kb.pages) for kb in kb_results),
            total_pages_scraped=sum(kb.pages_scraped for kb in kb_results),
            total_pages_failed=sum(kb.pages_failed for kb in kb_results),
            total_urls_discovered=sum(kb.urls_discovered for kb in kb_results),
            total_urls_out_of_scope=sum(kb.urls_out_of_scope for kb in kb_results),
            total_duration_ms=sum(kb.duration_ms for kb in kb_results),
            pages_by_kb={kb.kb_name: len(kb.pages) for kb in kb_results},
        )

        # Calculate total duration
        job_status = self._jobs.get(job_id)
        total_duration_ms = 0.0
        started_at = None
        completed_at = None

        if job_status:
            started_at = job_status.started_at
            completed_at = job_status.completed_at
            if started_at and completed_at:
                start_dt = datetime.fromisoformat(started_at)
                end_dt = datetime.fromisoformat(completed_at)
                total_duration_ms = (end_dt - start_dt).total_seconds() * 1000

        return MultiKBCrawlResult(
            job_id=job_id,
            domain=str(request.domain),
            mode=request.mode,
            state=CrawlState.COMPLETED,
            max_depth=request.max_depth,
            worker_count=request.worker_count,
            allow_subdomains=request.allow_subdomains,
            include_child_pages=request.include_child_pages,
            auto_discover_prefixes=request.auto_discover_prefixes,
            knowledge_bases=kb_results,
            summary=summary,
            started_at=started_at,
            completed_at=completed_at,
            total_duration_ms=total_duration_ms,
        )

    def _get_summary(self, kb_results: list[KBCrawlResult]) -> dict:
        """Get summary statistics for broadcasting."""
        return {
            "total_kbs": len(kb_results),
            "kbs_completed": sum(1 for kb in kb_results if kb.state == KBCrawlState.COMPLETED),
            "kbs_failed": sum(1 for kb in kb_results if kb.state == KBCrawlState.FAILED),
            "total_pages": sum(len(kb.pages) for kb in kb_results),
            "total_urls_discovered": sum(kb.urls_discovered for kb in kb_results),
            "total_urls_out_of_scope": sum(kb.urls_out_of_scope for kb in kb_results),
            "pages_by_kb": {kb.kb_name: len(kb.pages) for kb in kb_results},
        }

    def get_status(self, job_id: str) -> Optional[MultiKBCrawlStatus]:
        """Get current job status."""
        return self._jobs.get(job_id)

    def get_result(self, job_id: str) -> Optional[MultiKBCrawlResult]:
        """Get completed job result."""
        return self._results.get(job_id)

    def get_kb_status(self, job_id: str, kb_id: str) -> Optional[KnowledgeBaseCrawlStatus]:
        """Get status for a specific KB within a job."""
        job_status = self._jobs.get(job_id)
        if not job_status:
            return None

        for kb in job_status.knowledge_bases:
            if kb.kb_id == kb_id:
                return kb
        return None

    def get_kb_result(self, job_id: str, kb_id: str) -> Optional[KBCrawlResult]:
        """Get result for a specific KB within a job."""
        result = self._results.get(job_id)
        if not result:
            return None

        for kb_result in result.knowledge_bases:
            if kb_result.kb_id == kb_id:
                return kb_result
        return None

    def list_jobs(self) -> list[MultiKBCrawlStatus]:
        """List all multi-KB jobs."""
        return list(self._jobs.values())

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and its results."""
        if job_id in self._jobs:
            # Cancel running task
            task = self._tasks.pop(job_id, None)
            if task and not task.done():
                task.cancel()

            # Remove job data
            del self._jobs[job_id]
            self._results.pop(job_id, None)
            self._requests.pop(job_id, None)
            self._kb_crawlers.pop(job_id, None)

            logger.info(f"[JOB:{job_id}] Deleted multi-KB job")
            return True

        return False

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            logger.info(f"[JOB:{job_id}] Cancellation requested")
            return True
        return False


# Global multi-KB job manager instance
multi_kb_job_manager = MultiKBJobManager()
