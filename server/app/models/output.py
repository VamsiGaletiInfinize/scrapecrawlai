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
    FLAT = "flat"


class OutputConfig(BaseModel):
    """Configuration for output generation."""
    format: OutputFormat = Field(default=OutputFormat.MARKDOWN, description="Output format")
    organization: OrganizationType = Field(default=OrganizationType.FLAT, description="How to organize output")
    include_metadata: bool = Field(default=True, description="Include metadata in output")
    include_content: bool = Field(default=True, description="Include page content")
    include_timing: bool = Field(default=True, description="Include timing information")
    max_content_length: int = Field(default=5000, description="Maximum content length per page")
    create_index: bool = Field(default=True, description="Create index files for directories")


class PageMetadata(BaseModel):
    """Enhanced metadata for a single page."""
    url: str = Field(..., description="Page URL")
    subdomain: str = Field(..., description="Subdomain of the page")
    depth: int = Field(..., description="Crawl depth")
    content_type: ContentType = Field(default=ContentType.OTHER, description="Classified content type")
    title: Optional[str] = Field(default=None, description="Page title")
    parent_url: Optional[str] = Field(default=None, description="Referring page URL")
    links_found: int = Field(default=0, description="Number of outgoing links")
    timing_ms: float = Field(default=0.0, description="Processing time in milliseconds")
    word_count: int = Field(default=0, description="Word count of content")
    crawled_at: Optional[str] = Field(default=None, description="Timestamp when page was crawled")
    error: Optional[str] = Field(default=None, description="Error message if any")


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
