"""
API routes for Knowledge Base-scoped crawling.

This module provides REST API endpoints for:
- Starting multi-KB crawl jobs
- Tracking per-KB progress
- Retrieving per-KB and aggregate results
- WebSocket real-time updates
"""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import PlainTextResponse, Response

from ..models.crawl import CrawlState
from ..models.knowledge_base import (
    MultiKBCrawlRequest, MultiKBCrawlStatus, MultiKBCrawlResult,
    KnowledgeBaseConfig, KBCrawlState, KnowledgeBaseCrawlStatus,
    KBCrawlResult
)
from ..services.multi_kb_job_manager import multi_kb_job_manager
from ..services.websocket import connection_manager
from ..services.path_scope_filter import OverlapDetector
from ..utils.logger import get_api_logger

logger = get_api_logger()

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])


# ============================================================================
# Job Management Endpoints
# ============================================================================

@router.post("/start-crawl")
async def start_multi_kb_crawl(
    request: MultiKBCrawlRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start a multi-Knowledge-Base crawl job.

    Each KB is crawled independently with isolated:
    - BFS queue and visited set
    - Path scope enforcement
    - Progress tracking
    - Results storage

    Args:
        request: Multi-KB crawl configuration

    Returns:
        Job ID and confirmation with KB details
    """
    logger.info(
        f"[API] POST /kb/start-crawl - domain={request.domain}, "
        f"kbs={len(request.knowledge_bases)}, mode={request.mode.value}"
    )

    # Validate at least one active KB
    active_kbs = [kb for kb in request.knowledge_bases if kb.is_active]
    if not active_kbs:
        raise HTTPException(
            status_code=400,
            detail="At least one active Knowledge Base is required"
        )

    # Check for duplicate KB IDs
    kb_ids = [kb.kb_id for kb in request.knowledge_bases]
    if len(kb_ids) != len(set(kb_ids)):
        raise HTTPException(
            status_code=400,
            detail="Duplicate Knowledge Base IDs detected"
        )

    # Check for overlapping scopes
    overlaps = OverlapDetector.detect_overlaps(active_kbs)
    overlap_warnings = []
    if overlaps:
        for kb1_id, kb2_id, overlap_desc in overlaps:
            kb1_name = next((kb.name for kb in active_kbs if kb.kb_id == kb1_id), kb1_id)
            kb2_name = next((kb.name for kb in active_kbs if kb.kb_id == kb2_id), kb2_id)
            overlap_warnings.append(f"'{kb1_name}' and '{kb2_name}': {overlap_desc}")

    try:
        # Create job
        job_id = multi_kb_job_manager.create_job(request)

        # Start job in background
        background_tasks.add_task(multi_kb_job_manager.start_job, job_id, request)

        logger.info(f"[API] Multi-KB job created: {job_id}")

        response = {
            "job_id": job_id,
            "message": f"Started crawl for {len(active_kbs)} Knowledge Bases",
            "domain": str(request.domain),
            "mode": request.mode.value,
            "max_depth": request.max_depth,
            "worker_count": request.worker_count,
            "parallel_kbs": request.parallel_kbs,
            "knowledge_bases": [
                {
                    "kb_id": kb.kb_id,
                    "name": kb.name,
                    "entry_urls": [str(u) for u in kb.entry_urls],
                    "allowed_prefixes": kb.get_allowed_path_prefixes(),
                }
                for kb in active_kbs
            ],
        }

        # Include overlap warnings if any
        if overlap_warnings:
            response["warnings"] = {
                "overlapping_scopes": overlap_warnings,
                "message": "URLs in overlapping paths may be crawled by multiple KBs"
            }

        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status/{job_id}", response_model=MultiKBCrawlStatus)
async def get_multi_kb_status(job_id: str):
    """
    Get status of a multi-KB crawl job.

    Returns overall job status and per-KB progress breakdown.
    """
    status = multi_kb_job_manager.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return status


@router.get("/status/{job_id}/summary")
async def get_multi_kb_status_summary(job_id: str):
    """
    Get a concise summary of multi-KB job status.

    Returns aggregate metrics without full KB details.
    """
    status = multi_kb_job_manager.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return {
        "job_id": status.job_id,
        "state": status.state.value,
        "domain": status.domain,
        "progress": {
            "kbs_pending": status.kbs_pending,
            "kbs_running": status.kbs_running,
            "kbs_completed": status.kbs_completed,
            "kbs_failed": status.kbs_failed,
            "total_kbs": status.total_kbs,
        },
        "metrics": {
            "total_urls_discovered": status.total_urls_discovered,
            "total_urls_processed": status.total_urls_processed,
            "total_urls_out_of_scope": status.total_urls_out_of_scope,
        },
        "started_at": status.started_at,
        "error": status.error,
    }


@router.get("/status/{job_id}/kb/{kb_id}")
async def get_kb_status(job_id: str, kb_id: str):
    """
    Get status for a specific Knowledge Base within a job.
    """
    kb_status = multi_kb_job_manager.get_kb_status(job_id, kb_id)
    if not kb_status:
        # Check if job exists
        if not multi_kb_job_manager.get_status(job_id):
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        raise HTTPException(status_code=404, detail=f"KB {kb_id} not found in job {job_id}")

    return kb_status


# ============================================================================
# Results Endpoints
# ============================================================================

@router.get("/results/{job_id}", response_model=MultiKBCrawlResult)
async def get_multi_kb_results(job_id: str):
    """
    Get complete results of a multi-KB crawl job.

    Returns all KBs' results with aggregate statistics.
    """
    result = multi_kb_job_manager.get_result(job_id)
    if not result:
        status = multi_kb_job_manager.get_status(job_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        if status.state == CrawlState.PENDING:
            raise HTTPException(status_code=400, detail="Job has not started yet")
        if status.state == CrawlState.RUNNING:
            raise HTTPException(
                status_code=202,
                detail="Job still running",
                headers={"Retry-After": "5"}
            )
        if status.state == CrawlState.FAILED:
            raise HTTPException(status_code=400, detail=f"Job failed: {status.error}")
        raise HTTPException(status_code=404, detail="Results not found")

    return result


@router.get("/results/{job_id}/summary")
async def get_multi_kb_results_summary(job_id: str):
    """
    Get summary of multi-KB crawl results without full page content.

    Returns aggregate statistics and per-KB summaries.
    """
    result = multi_kb_job_manager.get_result(job_id)
    if not result:
        status = multi_kb_job_manager.get_status(job_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        if status.state != CrawlState.COMPLETED:
            raise HTTPException(status_code=400, detail="Job not completed")
        raise HTTPException(status_code=404, detail="Results not found")

    return {
        "job_id": result.job_id,
        "domain": result.domain,
        "mode": result.mode.value,
        "state": result.state.value,
        "configuration": {
            "max_depth": result.max_depth,
            "worker_count": result.worker_count,
            "allow_subdomains": result.allow_subdomains,
            "include_child_pages": result.include_child_pages,
        },
        "summary": result.summary.model_dump(),
        "timing": {
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "total_duration_ms": result.total_duration_ms,
        },
        "knowledge_bases": [
            {
                "kb_id": kb.kb_id,
                "kb_name": kb.kb_name,
                "state": kb.state.value,
                "entry_urls": kb.entry_urls,
                "urls_discovered": kb.urls_discovered,
                "urls_processed": kb.urls_processed,
                "urls_out_of_scope": kb.urls_out_of_scope,
                "pages_scraped": kb.pages_scraped,
                "pages_failed": kb.pages_failed,
                "duration_ms": kb.duration_ms,
                "error": kb.error,
            }
            for kb in result.knowledge_bases
        ],
    }


@router.get("/results/{job_id}/kb/{kb_id}", response_model=KBCrawlResult)
async def get_kb_results(job_id: str, kb_id: str):
    """
    Get results for a specific Knowledge Base within a job.

    Returns all pages and metrics for the specified KB.
    """
    kb_result = multi_kb_job_manager.get_kb_result(job_id, kb_id)
    if not kb_result:
        # Check if job/result exists
        result = multi_kb_job_manager.get_result(job_id)
        if not result:
            status = multi_kb_job_manager.get_status(job_id)
            if not status:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
            if status.state != CrawlState.COMPLETED:
                raise HTTPException(status_code=400, detail="Job not completed")
            raise HTTPException(status_code=404, detail="Results not found")
        raise HTTPException(status_code=404, detail=f"KB {kb_id} not found in job {job_id}")

    return kb_result


@router.get("/results/{job_id}/kb/{kb_id}/pages")
async def get_kb_pages(
    job_id: str,
    kb_id: str,
    include_content: bool = Query(default=False, description="Include page content"),
    depth: Optional[int] = Query(default=None, description="Filter by depth"),
    status_filter: Optional[str] = Query(default=None, description="Filter by status: scraped, crawled, error"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum pages to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
):
    """
    Get paginated pages for a specific Knowledge Base.

    Supports filtering by depth and status, with optional content inclusion.
    """
    kb_result = multi_kb_job_manager.get_kb_result(job_id, kb_id)
    if not kb_result:
        raise HTTPException(status_code=404, detail=f"KB {kb_id} results not found")

    # Filter pages
    pages = kb_result.pages

    if depth is not None:
        pages = [p for p in pages if p.depth == depth]

    if status_filter:
        pages = [p for p in pages if p.status.value == status_filter]

    # Paginate
    total = len(pages)
    pages = pages[offset:offset + limit]

    return {
        "kb_id": kb_id,
        "kb_name": kb_result.kb_name,
        "total_pages": total,
        "offset": offset,
        "limit": limit,
        "pages": [
            {
                "url": p.url,
                "parent_url": p.parent_url,
                "depth": p.depth,
                "title": p.title,
                "status": p.status.value,
                "links_found": p.links_found,
                "matched_prefix": p.matched_prefix,
                "timing_ms": p.timing_ms,
                "error": p.error,
                "content": p.content if include_content else None,
            }
            for p in pages
        ],
    }


# ============================================================================
# Download/Export Endpoints
# ============================================================================

@router.get("/download/{job_id}/json")
async def download_multi_kb_json(job_id: str):
    """
    Download complete multi-KB results as JSON file.
    """
    result = multi_kb_job_manager.get_result(job_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Job {job_id} results not found")

    content = result.model_dump_json(indent=2)

    return PlainTextResponse(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="kb_crawl_{job_id}.json"'
        }
    )


@router.get("/download/{job_id}/kb/{kb_id}/json")
async def download_kb_json(job_id: str, kb_id: str):
    """
    Download results for a specific KB as JSON file.
    """
    kb_result = multi_kb_job_manager.get_kb_result(job_id, kb_id)
    if not kb_result:
        raise HTTPException(status_code=404, detail=f"KB {kb_id} results not found")

    content = kb_result.model_dump_json(indent=2)

    return PlainTextResponse(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="kb_{kb_id}_{job_id}.json"'
        }
    )


@router.get("/download/{job_id}/markdown")
async def download_multi_kb_markdown(job_id: str):
    """
    Download multi-KB results as Markdown file.
    """
    result = multi_kb_job_manager.get_result(job_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Job {job_id} results not found")

    # Generate markdown
    md_content = _generate_multi_kb_markdown(result)

    return PlainTextResponse(
        content=md_content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="kb_crawl_{job_id}.md"'
        }
    )


# ============================================================================
# Job Management
# ============================================================================

@router.get("/jobs")
async def list_multi_kb_jobs():
    """
    List all multi-KB crawl jobs.
    """
    jobs = multi_kb_job_manager.list_jobs()
    return {
        "jobs": [
            {
                "job_id": job.job_id,
                "domain": job.domain,
                "state": job.state.value,
                "total_kbs": job.total_kbs,
                "kbs_completed": job.kbs_completed,
                "kbs_failed": job.kbs_failed,
                "total_urls_processed": job.total_urls_processed,
                "started_at": job.started_at,
            }
            for job in jobs
        ],
        "total": len(jobs),
    }


@router.delete("/jobs/{job_id}")
async def delete_multi_kb_job(job_id: str):
    """
    Delete a multi-KB crawl job.
    """
    if multi_kb_job_manager.delete_job(job_id):
        return {"message": f"Job {job_id} deleted"}
    raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


@router.post("/jobs/{job_id}/cancel")
async def cancel_multi_kb_job(job_id: str):
    """
    Cancel a running multi-KB crawl job.
    """
    if await multi_kb_job_manager.cancel_job(job_id):
        return {"message": f"Job {job_id} cancellation requested"}
    raise HTTPException(status_code=400, detail=f"Job {job_id} is not running")


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@router.websocket("/ws/{job_id}")
async def multi_kb_websocket(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time multi-KB crawl updates.

    Message types:
    - job_started: When job begins execution
    - multi_kb_progress: Per-KB and overall progress updates
    - page_complete: Individual page completion
    - kb_completed: When a KB finishes
    - job_completed: When entire job completes
    - job_failed: When job fails
    - heartbeat: Keep-alive message
    """
    await connection_manager.connect(websocket, job_id)

    try:
        # Send initial status if job exists
        status = multi_kb_job_manager.get_status(job_id)
        if status:
            await websocket.send_json({
                "type": "initial_status",
                "job_id": job_id,
                "data": {
                    "state": status.state.value,
                    "total_kbs": status.total_kbs,
                    "kbs_completed": status.kbs_completed,
                    "kbs_running": status.kbs_running,
                    "kbs_failed": status.kbs_failed,
                    "total_urls_discovered": status.total_urls_discovered,
                    "total_urls_processed": status.total_urls_processed,
                    "knowledge_bases": [
                        {
                            "kb_id": kb.kb_id,
                            "kb_name": kb.kb_name,
                            "state": kb.state.value,
                            "urls_discovered": kb.urls_discovered,
                            "urls_processed": kb.urls_processed,
                        }
                        for kb in status.knowledge_bases
                    ],
                }
            })

        # Keep connection alive and listen for client messages
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info(f"[WS] Client disconnected from KB job {job_id}")
    except Exception as e:
        logger.error(f"[WS] Error in KB websocket for job {job_id}: {e}")
    finally:
        await connection_manager.disconnect(websocket)


# ============================================================================
# Utility Endpoints
# ============================================================================

@router.post("/validate")
async def validate_kb_config(request: MultiKBCrawlRequest):
    """
    Validate a multi-KB crawl configuration without starting a job.

    Checks for:
    - Valid KB configurations
    - Overlapping scopes
    - Domain consistency
    """
    active_kbs = [kb for kb in request.knowledge_bases if kb.is_active]

    if not active_kbs:
        return {
            "valid": False,
            "errors": ["At least one active Knowledge Base is required"],
            "warnings": [],
        }

    errors = []
    warnings = []

    # Check for duplicate KB IDs
    kb_ids = [kb.kb_id for kb in request.knowledge_bases]
    if len(kb_ids) != len(set(kb_ids)):
        errors.append("Duplicate Knowledge Base IDs detected")

    # Check for duplicate KB names
    kb_names = [kb.name.lower() for kb in request.knowledge_bases]
    if len(kb_names) != len(set(kb_names)):
        errors.append("Duplicate Knowledge Base names detected")

    # Check domain consistency
    base_domain = str(request.domain).lower()
    for kb in active_kbs:
        for entry_url in kb.entry_urls:
            if base_domain not in str(entry_url).lower():
                warnings.append(
                    f"KB '{kb.name}' entry URL '{entry_url}' may not match base domain '{base_domain}'"
                )

    # Check for overlapping scopes
    overlaps = OverlapDetector.detect_overlaps(active_kbs)
    if overlaps:
        for kb1_id, kb2_id, overlap_desc in overlaps:
            kb1_name = next((kb.name for kb in active_kbs if kb.kb_id == kb1_id), kb1_id)
            kb2_name = next((kb.name for kb in active_kbs if kb.kb_id == kb2_id), kb2_id)
            warnings.append(f"Overlapping scopes: '{kb1_name}' and '{kb2_name}' ({overlap_desc})")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "knowledge_bases": [
            {
                "kb_id": kb.kb_id,
                "name": kb.name,
                "entry_urls": [str(u) for u in kb.entry_urls],
                "allowed_prefixes": kb.get_allowed_path_prefixes(),
                "is_active": kb.is_active,
            }
            for kb in request.knowledge_bases
        ],
    }


# ============================================================================
# Helper Functions
# ============================================================================

def _generate_multi_kb_markdown(result: MultiKBCrawlResult) -> str:
    """Generate markdown report for multi-KB crawl results."""
    lines = [
        f"# Multi-KB Crawl Report",
        f"",
        f"## Job Summary",
        f"",
        f"- **Job ID**: {result.job_id}",
        f"- **Domain**: {result.domain}",
        f"- **Mode**: {result.mode.value}",
        f"- **State**: {result.state.value}",
        f"- **Started**: {result.started_at}",
        f"- **Completed**: {result.completed_at}",
        f"- **Duration**: {result.total_duration_ms:.2f}ms",
        f"",
        f"## Configuration",
        f"",
        f"- Max Depth: {result.max_depth}",
        f"- Workers: {result.worker_count}",
        f"- Allow Subdomains: {result.allow_subdomains}",
        f"- Include Child Pages: {result.include_child_pages}",
        f"",
        f"## Aggregate Statistics",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total KBs | {result.summary.total_kbs} |",
        f"| KBs Completed | {result.summary.kbs_completed} |",
        f"| KBs Failed | {result.summary.kbs_failed} |",
        f"| Total Pages | {result.summary.total_pages} |",
        f"| Pages Scraped | {result.summary.total_pages_scraped} |",
        f"| Pages Failed | {result.summary.total_pages_failed} |",
        f"| URLs Discovered | {result.summary.total_urls_discovered} |",
        f"| URLs Out of Scope | {result.summary.total_urls_out_of_scope} |",
        f"",
        f"## Pages by Knowledge Base",
        f"",
        f"| KB Name | Pages |",
        f"|---------|-------|",
    ]

    for kb_name, count in result.summary.pages_by_kb.items():
        lines.append(f"| {kb_name} | {count} |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## Knowledge Base Details",
        f"",
    ])

    for kb in result.knowledge_bases:
        lines.extend([
            f"### {kb.kb_name}",
            f"",
            f"- **KB ID**: {kb.kb_id}",
            f"- **State**: {kb.state.value}",
            f"- **Entry URLs**: {', '.join(kb.entry_urls)}",
            f"- **Allowed Prefixes**: {', '.join(kb.allowed_prefixes)}",
            f"",
            f"#### Metrics",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| URLs Discovered | {kb.urls_discovered} |",
            f"| URLs Processed | {kb.urls_processed} |",
            f"| URLs Out of Scope | {kb.urls_out_of_scope} |",
            f"| Pages Scraped | {kb.pages_scraped} |",
            f"| Pages Crawled | {kb.pages_crawled} |",
            f"| Pages Failed | {kb.pages_failed} |",
            f"| Duration | {kb.duration_ms:.2f}ms |",
            f"",
        ])

        if kb.error:
            lines.append(f"**Error**: {kb.error}")
            lines.append("")

        # Add sample pages (first 10)
        if kb.pages:
            lines.extend([
                f"#### Sample Pages (first 10)",
                f"",
            ])
            for page in kb.pages[:10]:
                status_icon = "✅" if page.status.value == "scraped" else "⚠️" if page.status.value == "crawled" else "❌"
                lines.append(f"- {status_icon} [{page.title or page.url}]({page.url}) (depth {page.depth})")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)
