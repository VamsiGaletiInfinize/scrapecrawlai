"""
Data models for ScrapeCrawlAI.

This package contains Pydantic models for:
- Crawl requests and results
- Knowledge Base configurations
- Output formatting options
"""

from .crawl import (
    CrawlMode,
    CrawlState,
    CrawlRequest,
    CrawlStatus,
    CrawlResult,
    PageResult,
    PageStatus,
    SkipReason,
    PageTiming,
    TimingMetrics,
    DepthStats,
    FailurePhase,
    FailureType,
    FailureInfo,
    URLTask,
)

from .output import (
    ContentType,
    OutputFormat,
    OrganizationType,
    PageCategory,
    OutputConfig,
    EnhancedPageResult,
    PageMetadata,
    SubdomainGroup,
    DepthGroup,
    ContentTypeGroup,
    OrganizedOutput,
    CrawlMetadata,
    TimingBreakdown,
)

from .knowledge_base import (
    KBCrawlState,
    KnowledgeBaseConfig,
    KnowledgeBaseCrawlStatus,
    KBCrawlResult,
    KBPageResult,
    MultiKBCrawlRequest,
    MultiKBCrawlStatus,
    MultiKBCrawlResult,
    MultiKBSummary,
)

__all__ = [
    # Crawl models
    "CrawlMode",
    "CrawlState",
    "CrawlRequest",
    "CrawlStatus",
    "CrawlResult",
    "PageResult",
    "PageStatus",
    "SkipReason",
    "PageTiming",
    "TimingMetrics",
    "DepthStats",
    "FailurePhase",
    "FailureType",
    "FailureInfo",
    "URLTask",
    # Output models
    "ContentType",
    "OutputFormat",
    "OrganizationType",
    "PageCategory",
    "OutputConfig",
    "EnhancedPageResult",
    "PageMetadata",
    "SubdomainGroup",
    "DepthGroup",
    "ContentTypeGroup",
    "OrganizedOutput",
    "CrawlMetadata",
    "TimingBreakdown",
    # Knowledge Base models
    "KBCrawlState",
    "KnowledgeBaseConfig",
    "KnowledgeBaseCrawlStatus",
    "KBCrawlResult",
    "KBPageResult",
    "MultiKBCrawlRequest",
    "MultiKBCrawlStatus",
    "MultiKBCrawlResult",
    "MultiKBSummary",
]
