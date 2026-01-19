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


class FailurePhase(str, Enum):
    """Phase where failure occurred."""
    CRAWL = "crawl"
    SCRAPE = "scrape"
    NONE = "none"


class FailureType(str, Enum):
    """Specific failure type classification."""
    # Crawl failures
    CRAWL_TIMEOUT = "timeout"
    CRAWL_DNS_ERROR = "dns_error"
    CRAWL_CONNECTION_ERROR = "connection_error"
    CRAWL_SSL_ERROR = "ssl_error"
    CRAWL_HTTP_4XX = "http_4xx"
    CRAWL_HTTP_5XX = "http_5xx"
    CRAWL_ROBOTS_BLOCKED = "robots_blocked"
    CRAWL_REDIRECT_LOOP = "redirect_loop"
    # Scrape failures
    SCRAPE_EMPTY_CONTENT = "empty_content"
    SCRAPE_JS_BLOCKED = "js_blocked"
    SCRAPE_PARSE_ERROR = "parse_error"
    SCRAPE_SELECTOR_MISMATCH = "selector_mismatch"
    # Unknown
    UNKNOWN = "unknown"
    NONE = "none"


class PageStatus(str, Enum):
    """Status of page processing."""
    SCRAPED = "scraped"
    CRAWLED = "crawled"
    SKIPPED = "skipped"
    ERROR = "error"


class SkipReason(str, Enum):
    """Reason why a page was skipped."""
    CHILD_PAGES_DISABLED = "child_pages_disabled"
    NONE = "none"


class CrawlRequest(BaseModel):
    """Request payload for starting a crawl job."""
    seed_url: HttpUrl = Field(..., description="Starting URL for the crawl")
    mode: CrawlMode = Field(default=CrawlMode.CRAWL_SCRAPE, description="Crawl execution mode")
    max_depth: int = Field(default=3, ge=1, le=5, description="Maximum crawl depth (1-5)")
    worker_count: int = Field(default=4, ge=2, le=10, description="Number of concurrent workers (2-10)")
    allow_subdomains: bool = Field(default=False, description="Allow crawling subdomains")
    allowed_domains: list[str] = Field(default_factory=list, description="Additional allowed domains")
    include_child_pages: bool = Field(default=True, description="Include all child pages in crawl/scrape")


class TimingMetrics(BaseModel):
    """High-precision timing measurements in milliseconds."""
    url_discovery_ms: float = Field(default=0.0, description="Time spent discovering URLs")
    crawling_ms: float = Field(default=0.0, description="Time spent fetching pages")
    scraping_ms: float = Field(default=0.0, description="Time spent extracting content")
    total_ms: float = Field(default=0.0, description="Total execution time")


class PageTiming(BaseModel):
    """Detailed timing breakdown for a single page."""
    total_ms: float = Field(default=0.0, description="Total time to process this page")
    crawl_ms: float = Field(default=0.0, description="Time spent fetching the page (HTTP request)")
    scrape_ms: float = Field(default=0.0, description="Time spent extracting content")
    time_before_failure_ms: float = Field(default=0.0, description="Time spent before failure occurred")


class FailureInfo(BaseModel):
    """Detailed failure information."""
    phase: FailurePhase = Field(default=FailurePhase.NONE, description="Phase where failure occurred")
    type: FailureType = Field(default=FailureType.NONE, description="Specific failure type")
    reason: Optional[str] = Field(default=None, description="Human-readable failure reason")
    http_status: Optional[int] = Field(default=None, description="HTTP status code if applicable")
    exception: Optional[str] = Field(default=None, description="Exception message if applicable")


class PageResult(BaseModel):
    """Result for a single crawled/scraped page."""
    url: str = Field(..., description="Page URL")
    parent_url: Optional[str] = Field(default=None, description="URL of the referring page")
    depth: int = Field(..., ge=1, description="Depth level in BFS traversal")
    title: Optional[str] = Field(default=None, description="Page title")
    content: Optional[str] = Field(default=None, description="Extracted content (if scraped)")
    headings: list[str] = Field(default_factory=list, description="Page headings")
    links_found: int = Field(default=0, description="Number of child links discovered")

    # Enhanced timing - separate crawl vs scrape
    timing_ms: float = Field(default=0.0, description="Total time to process this page (legacy)")
    page_timing: PageTiming = Field(default_factory=PageTiming, description="Detailed timing breakdown")

    # Enhanced failure tracking
    error: Optional[str] = Field(default=None, description="Error message if processing failed (legacy)")
    failure: FailureInfo = Field(default_factory=FailureInfo, description="Detailed failure information")

    # Domain classification
    is_same_domain: bool = Field(default=True, description="Whether URL is same domain as seed")
    is_subdomain: bool = Field(default=False, description="Whether URL is a subdomain")

    # Page status for skipped pages support
    status: PageStatus = Field(default=PageStatus.SCRAPED, description="Processing status of the page")
    skip_reason: SkipReason = Field(default=SkipReason.NONE, description="Reason if page was skipped")


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
    allow_subdomains: bool = Field(default=False, description="Allow crawling subdomains")
    allowed_domains: list[str] = Field(default_factory=list, description="Additional allowed domains")
    include_child_pages: bool = Field(default=True, description="Include all child pages in crawl/scrape")
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
    allow_subdomains: bool = Field(default=False, description="Allow crawling subdomains")
    allowed_domains: list[str] = Field(default_factory=list, description="Additional allowed domains")
    include_child_pages: bool = Field(default=True, description="Include all child pages in crawl/scrape")
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
