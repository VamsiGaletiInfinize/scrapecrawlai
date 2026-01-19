"""
Output models for enhanced multi-format output organization.

Provides models for organizing crawl results by subdomain, depth, and content type
with comprehensive metadata support.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ContentType(str, Enum):
    """Content type classification for crawled pages."""
    ACADEMIC = "academic"
    FACULTY = "faculty"
    RESEARCH = "research"
    ADMINISTRATIVE = "administrative"
    NEWS = "news"
    EVENTS = "events"
    RESOURCES = "resources"
    OTHER = "other"


class OutputFormat(str, Enum):
    """Available output formats."""
    JSON = "json"
    MARKDOWN = "markdown"
    CSV = "csv"


class OrganizationType(str, Enum):
    """How to organize the output."""
    BY_SUBDOMAIN = "by_subdomain"
    BY_DEPTH = "by_depth"
    BY_CONTENT_TYPE = "by_content_type"
    BY_STATUS = "by_status"  # New: organize by success/error/external
    FLAT = "flat"


class PageCategory(str, Enum):
    """Page result category for three-group organization."""
    SAME_DOMAIN_SUCCESS = "same_domain_success"
    EXTERNAL_DOMAIN = "external_domain"
    ERROR = "error"


class OutputConfig(BaseModel):
    """Configuration for output generation."""
    format: OutputFormat = Field(default=OutputFormat.MARKDOWN, description="Output format")
    organization: OrganizationType = Field(default=OrganizationType.FLAT, description="How to organize output")
    include_metadata: bool = Field(default=True, description="Include metadata in output")
    include_content: bool = Field(default=True, description="Include page content")
    include_timing: bool = Field(default=True, description="Include timing information")
    max_content_length: int = Field(default=5000, description="Maximum content length per page")
    create_index: bool = Field(default=True, description="Create index files for directories")


class PageTimingDetails(BaseModel):
    """Detailed timing breakdown for a page."""
    total_ms: float = Field(default=0.0, description="Total processing time")
    crawl_ms: float = Field(default=0.0, description="HTTP fetch time")
    scrape_ms: float = Field(default=0.0, description="Content extraction time")
    time_before_failure_ms: float = Field(default=0.0, description="Time spent before failure")


class FailureDetails(BaseModel):
    """Detailed failure information for output."""
    phase: str = Field(default="none", description="Phase where failure occurred (crawl/scrape)")
    type: str = Field(default="none", description="Specific failure type")
    reason: Optional[str] = Field(default=None, description="Human-readable reason")
    http_status: Optional[int] = Field(default=None, description="HTTP status code if applicable")


class PageMetadata(BaseModel):
    """Enhanced metadata for a single page."""
    url: str = Field(..., description="Page URL")
    subdomain: str = Field(..., description="Subdomain of the page")
    depth: int = Field(..., description="Crawl depth")
    content_type: ContentType = Field(default=ContentType.OTHER, description="Classified content type")
    category: PageCategory = Field(default=PageCategory.SAME_DOMAIN_SUCCESS, description="Page result category")
    title: Optional[str] = Field(default=None, description="Page title")
    parent_url: Optional[str] = Field(default=None, description="Referring page URL")
    links_found: int = Field(default=0, description="Number of outgoing links")
    timing_ms: float = Field(default=0.0, description="Processing time in milliseconds (legacy)")
    timing: PageTimingDetails = Field(default_factory=PageTimingDetails, description="Detailed timing breakdown")
    word_count: int = Field(default=0, description="Word count of content")
    crawled_at: Optional[str] = Field(default=None, description="Timestamp when page was crawled")
    error: Optional[str] = Field(default=None, description="Error message if any (legacy)")
    failure: FailureDetails = Field(default_factory=FailureDetails, description="Detailed failure information")
    is_same_domain: bool = Field(default=True, description="Whether URL is same domain as seed")
    is_subdomain: bool = Field(default=False, description="Whether URL is a subdomain")


class EnhancedPageResult(BaseModel):
    """Enhanced page result with full metadata and content."""
    metadata: PageMetadata = Field(..., description="Page metadata")
    headings: list[str] = Field(default_factory=list, description="Page headings")
    content: Optional[str] = Field(default=None, description="Extracted content")


class SubdomainGroup(BaseModel):
    """Group of pages organized by subdomain."""
    subdomain: str = Field(..., description="Subdomain name")
    page_count: int = Field(default=0, description="Number of pages in this group")
    total_word_count: int = Field(default=0, description="Total words across all pages")
    content_types: dict[str, int] = Field(default_factory=dict, description="Count by content type")
    depth_distribution: dict[int, int] = Field(default_factory=dict, description="Pages per depth level")
    pages: list[EnhancedPageResult] = Field(default_factory=list, description="Pages in this group")


class DepthGroup(BaseModel):
    """Group of pages organized by crawl depth."""
    depth: int = Field(..., description="Depth level")
    page_count: int = Field(default=0, description="Number of pages at this depth")
    subdomains: list[str] = Field(default_factory=list, description="Subdomains found at this depth")
    content_types: dict[str, int] = Field(default_factory=dict, description="Count by content type")
    pages: list[EnhancedPageResult] = Field(default_factory=list, description="Pages at this depth")


class ContentTypeGroup(BaseModel):
    """Group of pages organized by content type."""
    content_type: ContentType = Field(..., description="Content type")
    page_count: int = Field(default=0, description="Number of pages of this type")
    subdomains: list[str] = Field(default_factory=list, description="Subdomains with this content type")
    depth_distribution: dict[int, int] = Field(default_factory=dict, description="Pages per depth level")
    pages: list[EnhancedPageResult] = Field(default_factory=list, description="Pages of this type")


# ============================================================================
# THREE-GROUP ORGANIZATION MODELS
# ============================================================================

class SameDomainSuccessGroup(BaseModel):
    """Group of successfully scraped pages on the same domain."""
    page_count: int = Field(default=0, description="Number of successful same-domain pages")
    total_word_count: int = Field(default=0, description="Total words across all pages")
    avg_timing_ms: float = Field(default=0.0, description="Average processing time")
    avg_crawl_ms: float = Field(default=0.0, description="Average HTTP fetch time")
    avg_scrape_ms: float = Field(default=0.0, description="Average content extraction time")
    depth_distribution: dict[int, int] = Field(default_factory=dict, description="Pages per depth level")
    content_types: dict[str, int] = Field(default_factory=dict, description="Count by content type")
    pages: list[EnhancedPageResult] = Field(default_factory=list, description="All successful same-domain pages")


class ExternalDomainGroup(BaseModel):
    """Group of pages from external/different domains (including subdomains)."""
    page_count: int = Field(default=0, description="Number of external domain pages")
    domains: list[str] = Field(default_factory=list, description="List of external domains encountered")
    subdomain_count: int = Field(default=0, description="Number of subdomain pages")
    external_count: int = Field(default=0, description="Number of truly external domain pages")
    depth_distribution: dict[int, int] = Field(default_factory=dict, description="Pages per depth level")
    status_distribution: dict[str, int] = Field(default_factory=dict, description="Success/Error count")
    pages: list[EnhancedPageResult] = Field(default_factory=list, description="All external domain pages")


class FailureSummary(BaseModel):
    """Summary of a specific failure type."""
    type: str = Field(..., description="Failure type")
    count: int = Field(default=0, description="Number of pages with this failure")
    phase: str = Field(..., description="Failure phase (crawl/scrape)")
    example_urls: list[str] = Field(default_factory=list, description="Example URLs with this failure")


class ErrorGroup(BaseModel):
    """Group of pages that failed during crawling or scraping."""
    page_count: int = Field(default=0, description="Total number of failed pages")
    crawl_failures: int = Field(default=0, description="Failures during HTTP fetch")
    scrape_failures: int = Field(default=0, description="Failures during content extraction")
    total_time_wasted_ms: float = Field(default=0.0, description="Total time spent on failed pages")
    failure_types: list[FailureSummary] = Field(default_factory=list, description="Breakdown by failure type")
    depth_distribution: dict[int, int] = Field(default_factory=dict, description="Failed pages per depth level")
    pages: list[EnhancedPageResult] = Field(default_factory=list, description="All failed pages")


class ThreeGroupOutput(BaseModel):
    """Output organized into three distinct groups for analysis."""
    same_domain_success: SameDomainSuccessGroup = Field(
        default_factory=SameDomainSuccessGroup,
        description="Successfully scraped pages on the same domain"
    )
    external_domain: ExternalDomainGroup = Field(
        default_factory=ExternalDomainGroup,
        description="Pages from external/different domains"
    )
    errors: ErrorGroup = Field(
        default_factory=ErrorGroup,
        description="Pages that failed during crawling or scraping"
    )


class CrawlMetadata(BaseModel):
    """Comprehensive metadata for the entire crawl job."""
    job_id: str = Field(..., description="Unique job identifier")
    seed_url: str = Field(..., description="Starting URL")
    mode: str = Field(..., description="Crawl mode used")
    max_depth: int = Field(..., description="Maximum depth setting")
    worker_count: int = Field(..., description="Number of workers used")
    allow_subdomains: bool = Field(default=False, description="Whether subdomains were allowed")
    allowed_domains: list[str] = Field(default_factory=list, description="Additional allowed domains")
    state: str = Field(..., description="Final job state")
    started_at: Optional[str] = Field(default=None, description="Job start timestamp")
    completed_at: Optional[str] = Field(default=None, description="Job completion timestamp")
    total_urls_discovered: int = Field(default=0, description="Total URLs discovered")
    total_pages_scraped: int = Field(default=0, description="Total pages with content")
    total_errors: int = Field(default=0, description="Total pages with errors")


class TimingBreakdown(BaseModel):
    """Detailed timing breakdown."""
    url_discovery_ms: float = Field(default=0.0, description="Time for URL discovery")
    crawling_ms: float = Field(default=0.0, description="Time for fetching pages")
    scraping_ms: float = Field(default=0.0, description="Time for extracting content")
    total_ms: float = Field(default=0.0, description="Total execution time")
    avg_page_time_ms: float = Field(default=0.0, description="Average time per page")
    fastest_page_ms: float = Field(default=0.0, description="Fastest page processing time")
    slowest_page_ms: float = Field(default=0.0, description="Slowest page processing time")


class OrganizedOutput(BaseModel):
    """Complete organized output with all groupings and metadata."""
    metadata: CrawlMetadata = Field(..., description="Crawl job metadata")
    timing: TimingBreakdown = Field(..., description="Timing breakdown")
    summary: dict = Field(default_factory=dict, description="Summary statistics")

    # Different organization views
    by_subdomain: list[SubdomainGroup] = Field(default_factory=list, description="Pages grouped by subdomain")
    by_depth: list[DepthGroup] = Field(default_factory=list, description="Pages grouped by depth")
    by_content_type: list[ContentTypeGroup] = Field(default_factory=list, description="Pages grouped by content type")

    # Three-group organization (same-domain success, external domain, errors)
    by_status: ThreeGroupOutput = Field(default_factory=ThreeGroupOutput, description="Pages grouped by status")

    # Flat list for simple access
    all_pages: list[EnhancedPageResult] = Field(default_factory=list, description="All pages in flat list")


class ExportRequest(BaseModel):
    """Request for exporting crawl results."""
    job_id: str = Field(..., description="Job ID to export")
    config: OutputConfig = Field(default_factory=OutputConfig, description="Export configuration")


class ExportResponse(BaseModel):
    """Response containing export data or file path."""
    job_id: str = Field(..., description="Job ID")
    format: OutputFormat = Field(..., description="Output format")
    organization: OrganizationType = Field(..., description="Organization type")
    file_path: Optional[str] = Field(default=None, description="Path to exported file/directory")
    content: Optional[str] = Field(default=None, description="Inline content for small exports")
    file_count: int = Field(default=1, description="Number of files generated")
    total_size_bytes: int = Field(default=0, description="Total size of exported data")
