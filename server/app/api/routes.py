from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse
from typing import Optional

from ..models.crawl import CrawlRequest, CrawlStatus, CrawlResult, CrawlState
from ..services.job_manager import job_manager
from ..services.formatter import OutputFormatter

router = APIRouter(prefix="/api", tags=["crawl"])


@router.post("/start-crawl")
async def start_crawl(request: CrawlRequest, background_tasks: BackgroundTasks):
    """
    Start a new crawl job.

    Args:
        request: Crawl request with seed_url, mode, max_depth, worker_count

    Returns:
        Job ID for tracking progress
    """
    # Create job
    job_id = job_manager.create_job(request)

    # Start job in background
    background_tasks.add_task(job_manager.start_job, job_id)

    return {
        "job_id": job_id,
        "message": "Crawl job started",
        "seed_url": str(request.seed_url),
        "mode": request.mode.value,
        "max_depth": request.max_depth,
        "worker_count": request.worker_count,
        "allow_subdomains": request.allow_subdomains,
        "allowed_domains": request.allowed_domains,
    }


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """
    Get current status of a crawl job.

    Args:
        job_id: Job ID to check

    Returns:
        Current job status with progress and timing
    """
    status = job_manager.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return {
        "job_id": status.job_id,
        "state": status.state.value,
        "seed_url": status.seed_url,
        "mode": status.mode.value,
        "max_depth": status.max_depth,
        "worker_count": status.worker_count,
        "allow_subdomains": status.allow_subdomains,
        "allowed_domains": status.allowed_domains,
        "current_depth": status.current_depth,
        "urls_discovered": status.urls_discovered,
        "urls_processed": status.urls_processed,
        "urls_by_depth": [
            {"depth": ds.depth, "count": ds.urls_count}
            for ds in status.urls_by_depth
        ],
        "timing": {
            "url_discovery_ms": status.timing.url_discovery_ms,
            "crawling_ms": status.timing.crawling_ms,
            "scraping_ms": status.timing.scraping_ms,
            "total_ms": status.timing.total_ms,
        },
        "error": status.error,
    }


@router.get("/results/{job_id}")
async def get_results(job_id: str):
    """
    Get complete results of a finished crawl job.

    Args:
        job_id: Job ID to get results for

    Returns:
        Complete crawl results with all pages and timing
    """
    status = job_manager.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if status.state == CrawlState.PENDING:
        raise HTTPException(status_code=400, detail="Job has not started yet")

    if status.state == CrawlState.RUNNING:
        raise HTTPException(status_code=400, detail="Job is still running")

    if status.state == CrawlState.FAILED:
        raise HTTPException(status_code=400, detail=f"Job failed: {status.error}")

    result = job_manager.get_result(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Results not found")

    # Return summary with page data
    return {
        "job_id": result.job_id,
        "seed_url": result.seed_url,
        "mode": result.mode.value,
        "max_depth": result.max_depth,
        "worker_count": result.worker_count,
        "allow_subdomains": result.allow_subdomains,
        "allowed_domains": result.allowed_domains,
        "state": result.state.value,
        "timing": OutputFormatter.format_timing_breakdown(result.timing),
        "summary": OutputFormatter.create_summary(
            result.pages,
            result.timing,
            result.urls_by_depth,
            result.mode,
        ),
        "urls_by_depth": [
            {"depth": ds.depth, "count": ds.urls_count, "urls": ds.urls}
            for ds in result.urls_by_depth
        ],
        "pages": [
            {
                "url": page.url,
                "parent_url": page.parent_url,
                "depth": page.depth,
                "title": page.title,
                "links_found": page.links_found,
                "timing_ms": page.timing_ms,
                "has_content": bool(page.content),
                "error": page.error,
            }
            for page in result.pages
        ],
    }


@router.get("/download/{job_id}/json")
async def download_json(job_id: str):
    """
    Download crawl results as JSON file.

    Args:
        job_id: Job ID to download

    Returns:
        JSON file with complete results
    """
    json_output = job_manager.get_json_output(job_id)
    if not json_output:
        raise HTTPException(status_code=404, detail="Results not found")

    return PlainTextResponse(
        content=json_output,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="crawl_{job_id}.json"'
        }
    )


@router.get("/download/{job_id}/markdown")
async def download_markdown(job_id: str):
    """
    Download crawl results as Markdown file.

    Args:
        job_id: Job ID to download

    Returns:
        Markdown file with complete results
    """
    md_output = job_manager.get_markdown_output(job_id)
    if not md_output:
        raise HTTPException(status_code=404, detail="Results not found")

    return PlainTextResponse(
        content=md_output,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="crawl_{job_id}.md"'
        }
    )


@router.get("/jobs")
async def list_jobs():
    """
    List all crawl jobs.

    Returns:
        List of all jobs with their current status
    """
    jobs = job_manager.list_jobs()
    return {
        "jobs": [
            {
                "job_id": job.job_id,
                "state": job.state.value,
                "seed_url": job.seed_url,
                "mode": job.mode.value,
                "urls_discovered": job.urls_discovered,
            }
            for job in jobs
        ],
        "total": len(jobs),
    }


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    Delete a crawl job.

    Args:
        job_id: Job ID to delete

    Returns:
        Confirmation message
    """
    if job_manager.delete_job(job_id):
        return {"message": f"Job {job_id} deleted"}
    raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
