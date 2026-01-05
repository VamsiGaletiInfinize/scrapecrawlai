from enum import Enum
from typing import Optional
from pydantic import BaseModel, HttpUrl, Field


class CrawlMode(str, Enum):
    """Crawl execution modes."""
    ONLY_CRAWL = "only_crawl"
    ONLY_SCRAPE = "only_scrape"
    CRAWL_SCRAPE = "crawl_scrape"


class CrawlState(str, Enum):
    """Job execution states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CrawlRequest(BaseModel):
    """Request payload for starting a crawl job."""
    seed_url: HttpUrl = Field(..., description="Starting URL for the crawl")
    mode: CrawlMode = Field(default=CrawlMode.CRAWL_SCRAPE, description="Crawl execution mode")
    max_depth: int = Field(default=3, ge=1, le=5, description="Maximum crawl depth (1-5)")
    worker_count: int = Field(default=4, ge=2, le=10, description="Number of concurrent workers (2-10)")


class TimingMetrics(BaseModel):
    """High-precision timing measurements in milliseconds."""
    url_discovery_ms: float = Field(default=0.0, description="Time spent discovering URLs")
    crawling_ms: float = Field(default=0.0, description="Time spent fetching pages")
    scraping_ms: float = Field(default=0.0, description="Time spent extracting content")
    total_ms: float = Field(default=0.0, description="Total execution time")


class PageResult(BaseModel):
    """Result for a single crawled/scraped page."""
    url: str = Field(..., description="Page URL")
    parent_url: Optional[str] = Field(default=None, description="URL of the referring page")
    depth: int = Field(..., ge=1, description="Depth level in BFS traversal")
    title: Optional[str] = Field(default=None, description="Page title")
    content: Optional[str] = Field(default=None, description="Extracted content (if scraped)")
    headings: list[str] = Field(default_factory=list, description="Page headings")
    links_found: int = Field(default=0, description="Number of child links discovered")
    timing_ms: float = Field(default=0.0, description="Time to process this page")
    error: Optional[str] = Field(default=None, description="Error message if processing failed")


class DepthStats(BaseModel):
    """Statistics for a single depth level."""
    depth: int
    urls_count: int
    urls: list[str]


class CrawlStatus(BaseModel):
    """Current status of a crawl job."""
    job_id: str = Field(..., description="Unique job identifier")
    state: CrawlState = Field(default=CrawlState.PENDING, description="Current job state")
    seed_url: str = Field(..., description="Starting URL")
    mode: CrawlMode = Field(..., description="Execution mode")
    max_depth: int = Field(..., description="Maximum depth setting")
    worker_count: int = Field(..., description="Number of workers")
    current_depth: int = Field(default=0, description="Current BFS depth being processed")
    urls_discovered: int = Field(default=0, description="Total URLs discovered")
    urls_processed: int = Field(default=0, description="URLs processed so far")
    urls_by_depth: list[DepthStats] = Field(default_factory=list, description="URLs grouped by depth")
    timing: TimingMetrics = Field(default_factory=TimingMetrics, description="Timing breakdown")
    error: Optional[str] = Field(default=None, description="Error message if job failed")


class CrawlResult(BaseModel):
    """Complete results of a crawl job."""
    job_id: str = Field(..., description="Unique job identifier")
    seed_url: str = Field(..., description="Starting URL")
    mode: CrawlMode = Field(..., description="Execution mode")
    max_depth: int = Field(..., description="Maximum depth setting")
    worker_count: int = Field(..., description="Number of workers used")
    state: CrawlState = Field(..., description="Final job state")
    timing: TimingMetrics = Field(..., description="Complete timing breakdown")
    urls_by_depth: list[DepthStats] = Field(default_factory=list, description="URLs grouped by depth")
    pages: list[PageResult] = Field(default_factory=list, description="All processed pages")
    total_urls_discovered: int = Field(default=0, description="Total URLs discovered")
    total_pages_scraped: int = Field(default=0, description="Total pages with content extracted")


class URLTask(BaseModel):
    """Internal task for processing a single URL."""
    url: str
    parent_url: Optional[str] = None
    depth: int
