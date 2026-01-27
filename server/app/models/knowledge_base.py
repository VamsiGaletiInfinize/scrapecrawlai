"""
Knowledge Base models for category-scoped crawling.

This module provides data models for:
- Knowledge Base configuration (entry URLs, scope boundaries)
- Multi-KB crawl requests and responses
- Per-KB status tracking and results
"""

from enum import Enum
from typing import Optional
from urllib.parse import urlparse
import uuid

from pydantic import BaseModel, HttpUrl, Field, field_validator

from .crawl import CrawlMode, CrawlState, PageResult, PageStatus, TimingMetrics


class KBCrawlState(str, Enum):
    """State for individual Knowledge Base crawl within a job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # User deactivated or no valid URLs


class KnowledgeBaseConfig(BaseModel):
    """Configuration for a single Knowledge Base."""
    kb_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = Field(..., min_length=1, max_length=100, description="KB name (e.g., 'Admissions', 'Academics')")
    description: Optional[str] = Field(default=None, max_length=500, description="Optional description")
    entry_urls: list[HttpUrl] = Field(..., min_length=1, description="One or more seed URLs for this KB")
    is_active: bool = Field(default=True, description="Whether this KB should be crawled")
    max_depth: Optional[int] = Field(default=None, ge=1, le=10, description="Override job-level max_depth")

    @field_validator('entry_urls')
    @classmethod
    def validate_entry_urls(cls, v):
        if not v:
            raise ValueError("At least one entry URL is required")
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    def get_allowed_path_prefixes(self) -> list[str]:
        """
        Extract path prefixes from entry URLs.
        e.g., https://gmu.edu/admissions-aid → /admissions-aid
        """
        prefixes = []
        for url in self.entry_urls:
            parsed = urlparse(str(url))
            # Normalize: ensure leading slash, remove trailing slash
            path = parsed.path.rstrip('/') or '/'
            if path not in prefixes:
                prefixes.append(path)
        return prefixes

    def get_domains(self) -> set[str]:
        """Extract unique domains from entry URLs."""
        domains = set()
        for url in self.entry_urls:
            parsed = urlparse(str(url))
            domain = parsed.netloc.lower()
            if domain.startswith('www.'):
                domain = domain[4:]
            domains.add(domain)
        return domains


class KnowledgeBaseCrawlStatus(BaseModel):
    """Status tracking for a single KB within a job."""
    kb_id: str = Field(..., description="Knowledge Base identifier")
    kb_name: str = Field(..., description="Knowledge Base name")
    state: KBCrawlState = Field(default=KBCrawlState.PENDING, description="Current crawl state")
    entry_urls: list[str] = Field(default_factory=list, description="Entry URLs for this KB")
    allowed_prefixes: list[str] = Field(default_factory=list, description="Allowed path prefixes")

    # Progress metrics (isolated per KB)
    urls_discovered: int = Field(default=0, description="Total unique URLs found in scope")
    urls_processed: int = Field(default=0, description="URLs processed so far")
    urls_queued: int = Field(default=0, description="URLs waiting in queue")
    urls_skipped_out_of_scope: int = Field(default=0, description="URLs rejected as out of scope")
    current_depth: int = Field(default=0, description="Current depth being processed")
    max_depth: int = Field(default=0, description="Maximum depth for this KB")

    # Timing (per KB)
    started_at: Optional[str] = Field(default=None, description="ISO timestamp when crawl started")
    completed_at: Optional[str] = Field(default=None, description="ISO timestamp when crawl completed")
    duration_ms: float = Field(default=0, description="Total duration in milliseconds")

    # Errors
    error: Optional[str] = Field(default=None, description="Error message if failed")

    # Result summary
    pages_scraped: int = Field(default=0, description="Pages successfully scraped")
    pages_crawled: int = Field(default=0, description="Pages crawled (links only)")
    pages_failed: int = Field(default=0, description="Pages that failed to process")


class KBPageResult(PageResult):
    """Extended PageResult with KB tagging."""
    kb_id: str = Field(..., description="Knowledge Base this page belongs to")
    kb_name: str = Field(..., description="Knowledge Base name")
    matched_prefix: str = Field(default="", description="Which entry URL prefix this matched")


class KBDepthStats(BaseModel):
    """Statistics for a single depth level within a KB."""
    depth: int
    urls_count: int
    urls: list[str]


class KBCrawlResult(BaseModel):
    """Results for a single Knowledge Base."""
    kb_id: str = Field(..., description="Knowledge Base identifier")
    kb_name: str = Field(..., description="Knowledge Base name")
    entry_urls: list[str] = Field(default_factory=list, description="Entry URLs used")
    allowed_prefixes: list[str] = Field(default_factory=list, description="Path prefixes that were allowed")
    state: KBCrawlState = Field(..., description="Final state")

    # Pages (tagged with kb_id)
    pages: list[KBPageResult] = Field(default_factory=list, description="All processed pages")
    urls_by_depth: list[KBDepthStats] = Field(default_factory=list, description="URLs grouped by depth")

    # Metrics
    urls_discovered: int = Field(default=0, description="Total URLs discovered in scope")
    urls_processed: int = Field(default=0, description="Total URLs processed")
    urls_out_of_scope: int = Field(default=0, description="URLs rejected as out of scope")
    pages_scraped: int = Field(default=0, description="Pages successfully scraped")
    pages_crawled: int = Field(default=0, description="Pages crawled (links only)")
    pages_failed: int = Field(default=0, description="Pages that failed")

    # Timing
    started_at: Optional[str] = Field(default=None, description="ISO timestamp when started")
    completed_at: Optional[str] = Field(default=None, description="ISO timestamp when completed")
    duration_ms: float = Field(default=0, description="Total duration in milliseconds")

    # Error if failed
    error: Optional[str] = Field(default=None, description="Error message if KB crawl failed")


class MultiKBCrawlRequest(BaseModel):
    """Request to crawl multiple Knowledge Bases."""
    domain: HttpUrl = Field(..., description="Base domain for validation")
    knowledge_bases: list[KnowledgeBaseConfig] = Field(..., min_length=1, description="Knowledge Bases to crawl")

    # Job-level defaults (can be overridden per KB)
    mode: CrawlMode = Field(default=CrawlMode.CRAWL_SCRAPE, description="Crawl execution mode")
    max_depth: int = Field(default=3, ge=1, le=10, description="Maximum crawl depth (1-10)")
    worker_count: int = Field(default=4, ge=2, le=10, description="Number of concurrent workers (2-10)")

    # Global settings
    respect_robots_txt: bool = Field(default=True, description="Respect robots.txt rules")
    allow_subdomains: bool = Field(default=False, description="Allow crawling subdomains within KB scope")
    include_child_pages: bool = Field(default=True, description="Include all child pages in crawl/scrape")

    # Execution strategy
    parallel_kbs: int = Field(default=2, ge=1, le=5, description="Number of KBs to crawl concurrently")

    # Auto-discovery
    auto_discover_prefixes: bool = Field(
        default=False,
        description="Auto-discover and include path prefixes from links on entry pages"
    )

    @field_validator('knowledge_bases')
    @classmethod
    def validate_knowledge_bases(cls, v):
        if not v:
            raise ValueError("At least one Knowledge Base is required")

        # Check for duplicate KB IDs
        kb_ids = [kb.kb_id for kb in v]
        if len(kb_ids) != len(set(kb_ids)):
            raise ValueError("Duplicate Knowledge Base IDs detected")

        # Check for duplicate KB names
        kb_names = [kb.name.lower() for kb in v]
        if len(kb_names) != len(set(kb_names)):
            raise ValueError("Duplicate Knowledge Base names detected")

        return v


class MultiKBSummary(BaseModel):
    """Summary statistics for a multi-KB crawl job."""
    total_kbs: int = Field(default=0, description="Total number of KBs")
    kbs_completed: int = Field(default=0, description="KBs that completed successfully")
    kbs_failed: int = Field(default=0, description="KBs that failed")
    kbs_skipped: int = Field(default=0, description="KBs that were skipped")

    total_pages: int = Field(default=0, description="Total pages across all KBs")
    total_pages_scraped: int = Field(default=0, description="Total pages scraped")
    total_pages_failed: int = Field(default=0, description="Total pages failed")

    total_urls_discovered: int = Field(default=0, description="Total URLs discovered")
    total_urls_out_of_scope: int = Field(default=0, description="Total URLs rejected as out of scope")

    total_duration_ms: float = Field(default=0, description="Total job duration")

    pages_by_kb: dict[str, int] = Field(default_factory=dict, description="Page count per KB name")


class MultiKBCrawlStatus(BaseModel):
    """Overall job status for multi-KB crawl."""
    job_id: str = Field(..., description="Unique job identifier")
    domain: str = Field(..., description="Base domain")
    state: CrawlState = Field(default=CrawlState.PENDING, description="Overall job state")
    mode: CrawlMode = Field(..., description="Crawl execution mode")

    # Aggregate metrics
    total_kbs: int = Field(default=0, description="Total number of KBs")
    kbs_completed: int = Field(default=0, description="KBs completed successfully")
    kbs_failed: int = Field(default=0, description="KBs that failed")
    kbs_running: int = Field(default=0, description="KBs currently running")
    kbs_pending: int = Field(default=0, description="KBs waiting to start")

    # Per-KB breakdown
    knowledge_bases: list[KnowledgeBaseCrawlStatus] = Field(
        default_factory=list,
        description="Status for each KB"
    )

    # Overall progress
    total_urls_discovered: int = Field(default=0, description="Total URLs discovered across all KBs")
    total_urls_processed: int = Field(default=0, description="Total URLs processed across all KBs")
    total_urls_out_of_scope: int = Field(default=0, description="Total URLs rejected as out of scope")

    # Timing
    started_at: Optional[str] = Field(default=None, description="ISO timestamp when job started")
    completed_at: Optional[str] = Field(default=None, description="ISO timestamp when job completed")

    # Error
    error: Optional[str] = Field(default=None, description="Error message if job failed")


class MultiKBCrawlResult(BaseModel):
    """Complete results for multi-KB crawl."""
    job_id: str = Field(..., description="Unique job identifier")
    domain: str = Field(..., description="Base domain")
    mode: CrawlMode = Field(..., description="Crawl execution mode")
    state: CrawlState = Field(..., description="Final job state")

    # Configuration used
    max_depth: int = Field(..., description="Maximum depth setting")
    worker_count: int = Field(..., description="Number of workers used")
    allow_subdomains: bool = Field(default=False, description="Whether subdomains were allowed")
    include_child_pages: bool = Field(default=True, description="Whether child pages were included")
    auto_discover_prefixes: bool = Field(default=False, description="Whether prefix auto-discovery was enabled")

    # Per-KB results
    knowledge_bases: list[KBCrawlResult] = Field(
        default_factory=list,
        description="Results for each KB"
    )

    # Aggregate statistics
    summary: MultiKBSummary = Field(default_factory=MultiKBSummary, description="Summary statistics")

    # Timing
    started_at: Optional[str] = Field(default=None, description="ISO timestamp when job started")
    completed_at: Optional[str] = Field(default=None, description="ISO timestamp when job completed")
    total_duration_ms: float = Field(default=0, description="Total job duration in milliseconds")

    # Error
    error: Optional[str] = Field(default=None, description="Error message if job failed")


class KBURLTask(BaseModel):
    """URL task with KB context for queue processing."""
    url: str = Field(..., description="URL to process")
    depth: int = Field(..., ge=1, description="Depth level")
    parent_url: Optional[str] = Field(default=None, description="Parent URL that linked to this")
    matched_prefix: str = Field(default="", description="Which path prefix this URL matched")
