from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import PlainTextResponse, JSONResponse, Response
from typing import Optional
import asyncio

from ..models.crawl import CrawlRequest, CrawlStatus, CrawlResult, CrawlState
from ..models.output import OutputConfig, OutputFormat, OrganizationType
from ..services.job_manager import job_manager
from ..services.formatter import OutputFormatter
from ..services.enhanced_formatter import enhanced_formatter
from ..services.exporter import directory_exporter
from ..services.websocket import connection_manager
from ..utils.logger import get_api_logger

# Initialize logger
logger = get_api_logger()

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
    logger.info(f"[API] POST /start-crawl - seed_url={request.seed_url}, mode={request.mode.value}")

    # Create job
    job_id = job_manager.create_job(request)

    # Start job in background
    background_tasks.add_task(job_manager.start_job, job_id)

    logger.info(f"[API] Job created: {job_id}")

    return {
        "job_id": job_id,
        "message": "Crawl job started",
        "seed_url": str(request.seed_url),
        "mode": request.mode.value,
        "max_depth": request.max_depth,
        "worker_count": request.worker_count,
        "allow_subdomains": request.allow_subdomains,
        "allowed_domains": request.allowed_domains,
        "include_child_pages": request.include_child_pages,
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


@router.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time job updates.

    Clients connect to receive live status updates for a specific job.
    Messages sent:
    - status_update: Periodic progress updates during crawl
    - job_completed: Final status when job finishes successfully
    - job_failed: Error information if job fails
    """
    await connection_manager.connect(websocket, job_id)

    try:
        # Send initial status if job exists
        status = job_manager.get_status(job_id)
        if status:
            await websocket.send_json({
                "type": "initial_status",
                "job_id": job_id,
                "data": {
                    "state": status.state.value,
                    "urls_discovered": status.urls_discovered,
                    "urls_processed": status.urls_processed,
                    "current_depth": status.current_depth,
                }
            })

        # Keep connection alive and listen for client messages
        while True:
            try:
                # Wait for any message (ping/pong or close)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Echo back ping messages
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info(f"[WS] Client disconnected from job {job_id}")
    except Exception as e:
        logger.error(f"[WS] Error in websocket for job {job_id}: {e}")
    finally:
        await connection_manager.disconnect(websocket)


# ============================================================================
# Enhanced Export Endpoints
# ============================================================================

@router.get("/export/{job_id}/organized")
async def get_organized_results(
    job_id: str,
    organization: OrganizationType = Query(
        default=OrganizationType.FLAT,
        description="How to organize the output"
    ),
    format: OutputFormat = Query(
        default=OutputFormat.JSON,
        description="Output format"
    ),
    include_content: bool = Query(
        default=True,
        description="Include page content"
    ),
    max_content_length: int = Query(
        default=10000000,  # 10MB - effectively unlimited for chat agent feeders
        ge=100,
        le=10000000,
        description="Maximum content length per page (default: unlimited)"
    ),
):
    """
    Get organized crawl results with enhanced metadata.

    Supports organization by subdomain, depth, or content type.
    Available formats: JSON, Markdown, CSV.
    """
    result = job_manager.get_result(job_id)
    if not result:
        status = job_manager.get_status(job_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        if status.state == CrawlState.RUNNING:
            raise HTTPException(status_code=400, detail="Job is still running")
        if status.state == CrawlState.PENDING:
            raise HTTPException(status_code=400, detail="Job has not started")
        raise HTTPException(status_code=400, detail=f"Job failed: {status.error}")

    # Create output config
    config = OutputConfig(
        format=format,
        organization=organization,
        include_content=include_content,
        max_content_length=max_content_length,
    )

    # Organize results
    organized = enhanced_formatter.organize_results(result)

    # Format based on requested format
    if format == OutputFormat.JSON:
        content = enhanced_formatter.to_json(organized, config)
        return PlainTextResponse(
            content=content,
            media_type="application/json",
        )
    elif format == OutputFormat.MARKDOWN:
        content = enhanced_formatter.to_markdown(organized, config)
        return PlainTextResponse(
            content=content,
            media_type="text/markdown",
        )
    elif format == OutputFormat.CSV:
        content = enhanced_formatter.to_csv(organized, config)
        return PlainTextResponse(
            content=content,
            media_type="text/csv",
        )


@router.get("/export/{job_id}/summary")
async def get_export_summary(job_id: str):
    """
    Get a summary of available export options for a job.

    Returns metadata, statistics, and available groupings.
    """
    result = job_manager.get_result(job_id)
    if not result:
        status = job_manager.get_status(job_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        if status.state != CrawlState.COMPLETED:
            raise HTTPException(status_code=400, detail="Job not completed")
        raise HTTPException(status_code=404, detail="Results not found")

    # Organize results
    organized = enhanced_formatter.organize_results(result)

    return {
        "job_id": job_id,
        "metadata": organized.metadata.model_dump(),
        "timing": organized.timing.model_dump(),
        "summary": organized.summary,
        "available_organizations": {
            "by_subdomain": [
                {"subdomain": g.subdomain, "page_count": g.page_count}
                for g in organized.by_subdomain
            ],
            "by_depth": [
                {"depth": g.depth, "page_count": g.page_count}
                for g in organized.by_depth
            ],
            "by_content_type": [
                {"content_type": g.content_type.value, "page_count": g.page_count}
                for g in organized.by_content_type
            ],
        },
        "export_formats": ["json", "markdown", "csv", "zip"],
    }


@router.get("/export/{job_id}/by-subdomain/{subdomain}")
async def get_pages_by_subdomain(
    job_id: str,
    subdomain: str,
    format: OutputFormat = Query(default=OutputFormat.JSON),
    include_content: bool = Query(default=True),
):
    """
    Get pages for a specific subdomain.
    """
    result = job_manager.get_result(job_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found or not completed")

    config = OutputConfig(format=format, include_content=include_content)
    organized = enhanced_formatter.organize_results(result)

    # Find the subdomain group
    group = next((g for g in organized.by_subdomain if g.subdomain == subdomain), None)
    if not group:
        raise HTTPException(status_code=404, detail=f"Subdomain '{subdomain}' not found")

    if format == OutputFormat.JSON:
        import json
        content = json.dumps({
            "subdomain": group.subdomain,
            "page_count": group.page_count,
            "total_word_count": group.total_word_count,
            "content_types": group.content_types,
            "pages": [
                {
                    "url": p.metadata.url,
                    "title": p.metadata.title,
                    "depth": p.metadata.depth,
                    "content_type": p.metadata.content_type.value,
                    "word_count": p.metadata.word_count,
                    "content": p.content[:config.max_content_length] if include_content and p.content else None,
                }
                for p in group.pages
            ],
        }, indent=2)
        return PlainTextResponse(content=content, media_type="application/json")

    return {"subdomain": subdomain, "page_count": group.page_count}


@router.get("/export/{job_id}/by-depth/{depth}")
async def get_pages_by_depth(
    job_id: str,
    depth: int,
    format: OutputFormat = Query(default=OutputFormat.JSON),
    include_content: bool = Query(default=True),
):
    """
    Get pages at a specific depth level.
    """
    result = job_manager.get_result(job_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found or not completed")

    config = OutputConfig(format=format, include_content=include_content)
    organized = enhanced_formatter.organize_results(result)

    # Find the depth group
    group = next((g for g in organized.by_depth if g.depth == depth), None)
    if not group:
        raise HTTPException(status_code=404, detail=f"Depth level {depth} not found")

    if format == OutputFormat.JSON:
        import json
        content = json.dumps({
            "depth": group.depth,
            "page_count": group.page_count,
            "subdomains": group.subdomains,
            "content_types": group.content_types,
            "pages": [
                {
                    "url": p.metadata.url,
                    "title": p.metadata.title,
                    "subdomain": p.metadata.subdomain,
                    "content_type": p.metadata.content_type.value,
                    "word_count": p.metadata.word_count,
                    "content": p.content[:config.max_content_length] if include_content and p.content else None,
                }
                for p in group.pages
            ],
        }, indent=2)
        return PlainTextResponse(content=content, media_type="application/json")

    return {"depth": depth, "page_count": group.page_count}


@router.get("/export/{job_id}/by-content-type/{content_type}")
async def get_pages_by_content_type(
    job_id: str,
    content_type: str,
    format: OutputFormat = Query(default=OutputFormat.JSON),
    include_content: bool = Query(default=True),
):
    """
    Get pages of a specific content type.

    Valid content types: academic, faculty, research, administrative, news, events, resources, other
    """
    result = job_manager.get_result(job_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found or not completed")

    config = OutputConfig(format=format, include_content=include_content)
    organized = enhanced_formatter.organize_results(result)

    # Find the content type group
    group = next((g for g in organized.by_content_type if g.content_type.value == content_type), None)
    if not group:
        valid_types = [g.content_type.value for g in organized.by_content_type]
        raise HTTPException(
            status_code=404,
            detail=f"Content type '{content_type}' not found. Available: {valid_types}"
        )

    if format == OutputFormat.JSON:
        import json
        content = json.dumps({
            "content_type": group.content_type.value,
            "page_count": group.page_count,
            "subdomains": group.subdomains,
            "depth_distribution": group.depth_distribution,
            "pages": [
                {
                    "url": p.metadata.url,
                    "title": p.metadata.title,
                    "subdomain": p.metadata.subdomain,
                    "depth": p.metadata.depth,
                    "word_count": p.metadata.word_count,
                    "content": p.content[:config.max_content_length] if include_content and p.content else None,
                }
                for p in group.pages
            ],
        }, indent=2)
        return PlainTextResponse(content=content, media_type="application/json")

    return {"content_type": content_type, "page_count": group.page_count}


@router.get("/export/{job_id}/zip")
async def download_zip_export(
    job_id: str,
    include_content: bool = Query(default=True),
    max_content_length: int = Query(default=10000000, ge=100, le=10000000),  # Unlimited
):
    """
    Download complete crawl results as a ZIP file.

    The ZIP contains organized directories for subdomain, depth, and content type views,
    along with metadata, timing, and summary files.
    """
    result = job_manager.get_result(job_id)
    if not result:
        status = job_manager.get_status(job_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        if status.state != CrawlState.COMPLETED:
            raise HTTPException(status_code=400, detail="Job not completed")
        raise HTTPException(status_code=404, detail="Results not found")

    config = OutputConfig(
        include_content=include_content,
        max_content_length=max_content_length,
    )

    # Organize and export
    organized = enhanced_formatter.organize_results(result)
    zip_bytes = directory_exporter.export_to_zip(organized, config)

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="crawl_{job_id}_export.zip"'
        }
    )
