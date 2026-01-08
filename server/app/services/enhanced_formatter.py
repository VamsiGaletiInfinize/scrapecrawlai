"""
Enhanced formatter for multi-format output organization.

Provides comprehensive output formatting with support for:
- Organization by subdomain, depth, and content type
- Multiple output formats (JSON, Markdown, CSV)
- Detailed metadata and timing information
"""

import json
import csv
import io
from datetime import datetime
from typing import Optional
from collections import defaultdict

from ..models.crawl import CrawlResult, PageResult
from ..models.output import (
    ContentType, OutputConfig, OutputFormat, OrganizationType,
    PageMetadata, EnhancedPageResult, SubdomainGroup, DepthGroup,
    ContentTypeGroup, CrawlMetadata, TimingBreakdown, OrganizedOutput,
)
from .classifier import ContentClassifier, content_classifier


class EnhancedFormatter:
    """
    Enhanced output formatter with multi-dimensional organization.

    Features:
    - Organize by subdomain, depth, or content type
    - Multiple output formats (JSON, Markdown, CSV)
    - Comprehensive metadata and statistics
    - Directory-based export structure
    """

    def __init__(self, classifier: Optional[ContentClassifier] = None):
        """
        Initialize the enhanced formatter.

        Args:
            classifier: Content classifier instance (uses global if not provided)
        """
        self.classifier = classifier or content_classifier

    def organize_results(self, result: CrawlResult) -> OrganizedOutput:
        """
        Organize crawl results into all groupings.

        Args:
            result: Raw crawl results

        Returns:
            OrganizedOutput with all groupings and metadata
        """
        # Convert pages to enhanced format
        enhanced_pages = self._enhance_pages(result.pages)

        # Build metadata
        metadata = CrawlMetadata(
            job_id=result.job_id,
            seed_url=result.seed_url,
            mode=result.mode.value,
            max_depth=result.max_depth,
            worker_count=result.worker_count,
            allow_subdomains=result.allow_subdomains,
            allowed_domains=result.allowed_domains,
            state=result.state.value,
            completed_at=datetime.utcnow().isoformat() + "Z",
            total_urls_discovered=result.total_urls_discovered,
            total_pages_scraped=result.total_pages_scraped,
            total_errors=sum(1 for p in result.pages if p.error),
        )

        # Build timing breakdown
        page_times = [p.timing_ms for p in result.pages if p.timing_ms > 0]
        timing = TimingBreakdown(
            url_discovery_ms=result.timing.url_discovery_ms,
            crawling_ms=result.timing.crawling_ms,
            scraping_ms=result.timing.scraping_ms,
            total_ms=result.timing.total_ms,
            avg_page_time_ms=sum(page_times) / len(page_times) if page_times else 0,
            fastest_page_ms=min(page_times) if page_times else 0,
            slowest_page_ms=max(page_times) if page_times else 0,
        )

        # Build all groupings
        by_subdomain = self._group_by_subdomain(enhanced_pages)
        by_depth = self._group_by_depth(enhanced_pages)
        by_content_type = self._group_by_content_type(enhanced_pages)

        # Build summary
        summary = self._build_summary(enhanced_pages, by_subdomain, by_depth, by_content_type)

        return OrganizedOutput(
            metadata=metadata,
            timing=timing,
            summary=summary,
            by_subdomain=by_subdomain,
            by_depth=by_depth,
            by_content_type=by_content_type,
            all_pages=enhanced_pages,
        )

    def _enhance_pages(self, pages: list[PageResult]) -> list[EnhancedPageResult]:
        """
        Convert raw pages to enhanced format with metadata.

        Args:
            pages: List of raw page results

        Returns:
            List of enhanced page results
        """
        enhanced = []
        for page in pages:
            # Classify content type
            content_type = self.classifier.classify(
                url=page.url,
                title=page.title,
                content=page.content,
            )

            # Extract subdomain
            subdomain = self.classifier.extract_subdomain(page.url)

            # Calculate word count
            word_count = len(page.content.split()) if page.content else 0

            metadata = PageMetadata(
                url=page.url,
                subdomain=subdomain,
                depth=page.depth,
                content_type=content_type,
                title=page.title,
                parent_url=page.parent_url,
                links_found=page.links_found,
                timing_ms=page.timing_ms,
                word_count=word_count,
                crawled_at=datetime.utcnow().isoformat() + "Z",
                error=page.error,
            )

            enhanced.append(EnhancedPageResult(
                metadata=metadata,
                headings=page.headings,
                content=page.content,
            ))

        return enhanced

    def _group_by_subdomain(self, pages: list[EnhancedPageResult]) -> list[SubdomainGroup]:
        """
        Group pages by subdomain.

        Args:
            pages: List of enhanced pages

        Returns:
            List of subdomain groups
        """
        groups = defaultdict(lambda: {
            'pages': [],
            'content_types': defaultdict(int),
            'depth_distribution': defaultdict(int),
            'total_words': 0,
        })

        for page in pages:
            subdomain = page.metadata.subdomain
            groups[subdomain]['pages'].append(page)
            groups[subdomain]['content_types'][page.metadata.content_type.value] += 1
            groups[subdomain]['depth_distribution'][page.metadata.depth] += 1
            groups[subdomain]['total_words'] += page.metadata.word_count

        result = []
        for subdomain, data in sorted(groups.items()):
            result.append(SubdomainGroup(
                subdomain=subdomain,
                page_count=len(data['pages']),
                total_word_count=data['total_words'],
                content_types=dict(data['content_types']),
                depth_distribution=dict(data['depth_distribution']),
                pages=data['pages'],
            ))

        return result

    def _group_by_depth(self, pages: list[EnhancedPageResult]) -> list[DepthGroup]:
        """
        Group pages by crawl depth.

        Args:
            pages: List of enhanced pages

        Returns:
            List of depth groups
        """
        groups = defaultdict(lambda: {
            'pages': [],
            'subdomains': set(),
            'content_types': defaultdict(int),
        })

        for page in pages:
            depth = page.metadata.depth
            groups[depth]['pages'].append(page)
            groups[depth]['subdomains'].add(page.metadata.subdomain)
            groups[depth]['content_types'][page.metadata.content_type.value] += 1

        result = []
        for depth in sorted(groups.keys()):
            data = groups[depth]
            result.append(DepthGroup(
                depth=depth,
                page_count=len(data['pages']),
                subdomains=sorted(list(data['subdomains'])),
                content_types=dict(data['content_types']),
                pages=data['pages'],
            ))

        return result

    def _group_by_content_type(self, pages: list[EnhancedPageResult]) -> list[ContentTypeGroup]:
        """
        Group pages by content type.

        Args:
            pages: List of enhanced pages

        Returns:
            List of content type groups
        """
        groups = defaultdict(lambda: {
            'pages': [],
            'subdomains': set(),
            'depth_distribution': defaultdict(int),
        })

        for page in pages:
            ct = page.metadata.content_type
            groups[ct]['pages'].append(page)
            groups[ct]['subdomains'].add(page.metadata.subdomain)
            groups[ct]['depth_distribution'][page.metadata.depth] += 1

        result = []
        for content_type in ContentType:
            if content_type in groups:
                data = groups[content_type]
                result.append(ContentTypeGroup(
                    content_type=content_type,
                    page_count=len(data['pages']),
                    subdomains=sorted(list(data['subdomains'])),
                    depth_distribution=dict(data['depth_distribution']),
                    pages=data['pages'],
                ))

        return result

    def _build_summary(
        self,
        pages: list[EnhancedPageResult],
        by_subdomain: list[SubdomainGroup],
        by_depth: list[DepthGroup],
        by_content_type: list[ContentTypeGroup],
    ) -> dict:
        """
        Build summary statistics.

        Args:
            pages: All enhanced pages
            by_subdomain: Subdomain groups
            by_depth: Depth groups
            by_content_type: Content type groups

        Returns:
            Summary dictionary
        """
        total_words = sum(p.metadata.word_count for p in pages)
        successful = sum(1 for p in pages if not p.metadata.error)
        failed = sum(1 for p in pages if p.metadata.error)

        return {
            'total_pages': len(pages),
            'successful_pages': successful,
            'failed_pages': failed,
            'total_word_count': total_words,
            'avg_words_per_page': total_words // len(pages) if pages else 0,
            'subdomain_count': len(by_subdomain),
            'max_depth_reached': max(g.depth for g in by_depth) if by_depth else 0,
            'content_type_distribution': {
                g.content_type.value: g.page_count for g in by_content_type
            },
            'subdomain_distribution': {
                g.subdomain: g.page_count for g in by_subdomain
            },
        }

    def to_json(
        self,
        organized: OrganizedOutput,
        config: OutputConfig,
    ) -> str:
        """
        Format organized output as JSON.

        Args:
            organized: Organized output data
            config: Output configuration

        Returns:
            JSON string
        """
        output = {
            'metadata': organized.metadata.model_dump() if config.include_metadata else None,
            'timing': organized.timing.model_dump() if config.include_timing else None,
            'summary': organized.summary,
        }

        # Include requested organization
        if config.organization == OrganizationType.BY_SUBDOMAIN:
            output['by_subdomain'] = [
                self._serialize_subdomain_group(g, config) for g in organized.by_subdomain
            ]
        elif config.organization == OrganizationType.BY_DEPTH:
            output['by_depth'] = [
                self._serialize_depth_group(g, config) for g in organized.by_depth
            ]
        elif config.organization == OrganizationType.BY_CONTENT_TYPE:
            output['by_content_type'] = [
                self._serialize_content_type_group(g, config) for g in organized.by_content_type
            ]
        else:  # FLAT
            output['pages'] = [
                self._serialize_page(p, config) for p in organized.all_pages
            ]

        # Remove None values
        output = {k: v for k, v in output.items() if v is not None}

        return json.dumps(output, indent=2, ensure_ascii=False)

    def to_markdown(
        self,
        organized: OrganizedOutput,
        config: OutputConfig,
    ) -> str:
        """
        Format organized output as Markdown.

        Args:
            organized: Organized output data
            config: Output configuration

        Returns:
            Markdown string
        """
        lines = []

        # Header
        lines.append(f"# Crawl Report: {organized.metadata.seed_url}")
        lines.append("")

        # Metadata section
        if config.include_metadata:
            lines.append("## Metadata")
            lines.append("")
            lines.append(f"- **Job ID:** {organized.metadata.job_id}")
            lines.append(f"- **Mode:** {organized.metadata.mode}")
            lines.append(f"- **Max Depth:** {organized.metadata.max_depth}")
            lines.append(f"- **Workers:** {organized.metadata.worker_count}")
            lines.append(f"- **Subdomains Allowed:** {organized.metadata.allow_subdomains}")
            if organized.metadata.allowed_domains:
                lines.append(f"- **Allowed Domains:** {', '.join(organized.metadata.allowed_domains)}")
            lines.append(f"- **State:** {organized.metadata.state}")
            lines.append(f"- **Generated:** {organized.metadata.completed_at}")
            lines.append("")

        # Timing section
        if config.include_timing:
            lines.append("## Timing")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Total Time | {organized.timing.total_ms:.2f}ms |")
            lines.append(f"| URL Discovery | {organized.timing.url_discovery_ms:.2f}ms |")
            lines.append(f"| Crawling | {organized.timing.crawling_ms:.2f}ms |")
            lines.append(f"| Scraping | {organized.timing.scraping_ms:.2f}ms |")
            lines.append(f"| Avg Page Time | {organized.timing.avg_page_time_ms:.2f}ms |")
            lines.append(f"| Fastest Page | {organized.timing.fastest_page_ms:.2f}ms |")
            lines.append(f"| Slowest Page | {organized.timing.slowest_page_ms:.2f}ms |")
            lines.append("")

        # Summary section
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total Pages:** {organized.summary['total_pages']}")
        lines.append(f"- **Successful:** {organized.summary['successful_pages']}")
        lines.append(f"- **Failed:** {organized.summary['failed_pages']}")
        lines.append(f"- **Total Words:** {organized.summary['total_word_count']:,}")
        lines.append(f"- **Subdomains:** {organized.summary['subdomain_count']}")
        lines.append(f"- **Max Depth:** {organized.summary['max_depth_reached']}")
        lines.append("")

        # Content type distribution
        lines.append("### Content Type Distribution")
        lines.append("")
        lines.append("| Type | Count |")
        lines.append("|------|-------|")
        for ct, count in organized.summary['content_type_distribution'].items():
            lines.append(f"| {ct} | {count} |")
        lines.append("")

        # Subdomain distribution
        lines.append("### Subdomain Distribution")
        lines.append("")
        lines.append("| Subdomain | Pages |")
        lines.append("|-----------|-------|")
        for subdomain, count in organized.summary['subdomain_distribution'].items():
            lines.append(f"| {subdomain} | {count} |")
        lines.append("")

        # Pages by organization type
        if config.organization == OrganizationType.BY_SUBDOMAIN:
            lines.extend(self._markdown_by_subdomain(organized.by_subdomain, config))
        elif config.organization == OrganizationType.BY_DEPTH:
            lines.extend(self._markdown_by_depth(organized.by_depth, config))
        elif config.organization == OrganizationType.BY_CONTENT_TYPE:
            lines.extend(self._markdown_by_content_type(organized.by_content_type, config))
        else:
            lines.extend(self._markdown_flat(organized.all_pages, config))

        return "\n".join(lines)

    def to_csv(
        self,
        organized: OrganizedOutput,
        config: OutputConfig,
    ) -> str:
        """
        Format organized output as CSV.

        Args:
            organized: Organized output data
            config: Output configuration

        Returns:
            CSV string
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        headers = [
            'URL', 'Title', 'Subdomain', 'Depth', 'Content Type',
            'Parent URL', 'Links Found', 'Word Count', 'Timing (ms)', 'Error'
        ]
        if config.include_content:
            headers.append('Content Preview')
        writer.writerow(headers)

        # Data rows
        for page in organized.all_pages:
            row = [
                page.metadata.url,
                page.metadata.title or '',
                page.metadata.subdomain,
                page.metadata.depth,
                page.metadata.content_type.value,
                page.metadata.parent_url or '',
                page.metadata.links_found,
                page.metadata.word_count,
                f"{page.metadata.timing_ms:.2f}",
                page.metadata.error or '',
            ]
            if config.include_content:
                content_preview = (page.content or '')[:500].replace('\n', ' ')
                row.append(content_preview)
            writer.writerow(row)

        return output.getvalue()

    def _serialize_page(self, page: EnhancedPageResult, config: OutputConfig) -> dict:
        """Serialize a single page for JSON output."""
        result = {
            'url': page.metadata.url,
            'title': page.metadata.title,
            'subdomain': page.metadata.subdomain,
            'depth': page.metadata.depth,
            'content_type': page.metadata.content_type.value,
            'parent_url': page.metadata.parent_url,
            'links_found': page.metadata.links_found,
            'word_count': page.metadata.word_count,
            'timing_ms': page.metadata.timing_ms,
            'headings': page.headings,
            'error': page.metadata.error,
        }
        if config.include_content and page.content:
            result['content'] = page.content[:config.max_content_length]
        return result

    def _serialize_subdomain_group(self, group: SubdomainGroup, config: OutputConfig) -> dict:
        """Serialize a subdomain group for JSON output."""
        return {
            'subdomain': group.subdomain,
            'page_count': group.page_count,
            'total_word_count': group.total_word_count,
            'content_types': group.content_types,
            'depth_distribution': group.depth_distribution,
            'pages': [self._serialize_page(p, config) for p in group.pages],
        }

    def _serialize_depth_group(self, group: DepthGroup, config: OutputConfig) -> dict:
        """Serialize a depth group for JSON output."""
        return {
            'depth': group.depth,
            'page_count': group.page_count,
            'subdomains': group.subdomains,
            'content_types': group.content_types,
            'pages': [self._serialize_page(p, config) for p in group.pages],
        }

    def _serialize_content_type_group(self, group: ContentTypeGroup, config: OutputConfig) -> dict:
        """Serialize a content type group for JSON output."""
        return {
            'content_type': group.content_type.value,
            'page_count': group.page_count,
            'subdomains': group.subdomains,
            'depth_distribution': group.depth_distribution,
            'pages': [self._serialize_page(p, config) for p in group.pages],
        }

    def _markdown_by_subdomain(
        self,
        groups: list[SubdomainGroup],
        config: OutputConfig,
    ) -> list[str]:
        """Generate markdown content organized by subdomain."""
        lines = ["## Pages by Subdomain", ""]

        for group in groups:
            lines.append(f"### {group.subdomain} ({group.page_count} pages)")
            lines.append("")
            lines.append(f"**Total Words:** {group.total_word_count:,}")
            lines.append("")

            for page in group.pages[:50]:  # Limit per group
                lines.extend(self._markdown_page(page, config))

            if len(group.pages) > 50:
                lines.append(f"*... and {len(group.pages) - 50} more pages*")
                lines.append("")

        return lines

    def _markdown_by_depth(
        self,
        groups: list[DepthGroup],
        config: OutputConfig,
    ) -> list[str]:
        """Generate markdown content organized by depth."""
        lines = ["## Pages by Depth", ""]

        for group in groups:
            lines.append(f"### Depth {group.depth} ({group.page_count} pages)")
            lines.append("")
            lines.append(f"**Subdomains:** {', '.join(group.subdomains)}")
            lines.append("")

            for page in group.pages[:50]:
                lines.extend(self._markdown_page(page, config))

            if len(group.pages) > 50:
                lines.append(f"*... and {len(group.pages) - 50} more pages*")
                lines.append("")

        return lines

    def _markdown_by_content_type(
        self,
        groups: list[ContentTypeGroup],
        config: OutputConfig,
    ) -> list[str]:
        """Generate markdown content organized by content type."""
        lines = ["## Pages by Content Type", ""]

        for group in groups:
            lines.append(f"### {group.content_type.value.title()} ({group.page_count} pages)")
            lines.append("")
            lines.append(f"**Subdomains:** {', '.join(group.subdomains)}")
            lines.append("")

            for page in group.pages[:50]:
                lines.extend(self._markdown_page(page, config))

            if len(group.pages) > 50:
                lines.append(f"*... and {len(group.pages) - 50} more pages*")
                lines.append("")

        return lines

    def _markdown_flat(
        self,
        pages: list[EnhancedPageResult],
        config: OutputConfig,
    ) -> list[str]:
        """Generate flat markdown content."""
        lines = ["## All Pages", ""]

        for page in pages:
            lines.extend(self._markdown_page(page, config))

        return lines

    def _markdown_page(
        self,
        page: EnhancedPageResult,
        config: OutputConfig,
    ) -> list[str]:
        """Generate markdown for a single page."""
        lines = []
        title = page.metadata.title or page.metadata.url
        lines.append(f"#### {title}")
        lines.append("")
        lines.append(f"- **URL:** {page.metadata.url}")
        lines.append(f"- **Subdomain:** {page.metadata.subdomain}")
        lines.append(f"- **Depth:** {page.metadata.depth}")
        lines.append(f"- **Type:** {page.metadata.content_type.value}")
        lines.append(f"- **Words:** {page.metadata.word_count}")
        lines.append(f"- **Links:** {page.metadata.links_found}")
        lines.append(f"- **Time:** {page.metadata.timing_ms:.2f}ms")

        if page.metadata.error:
            lines.append(f"- **Error:** {page.metadata.error}")

        if page.headings:
            lines.append("")
            lines.append("**Headings:**")
            for h in page.headings[:5]:
                lines.append(f"  - {h}")
            if len(page.headings) > 5:
                lines.append(f"  - *... and {len(page.headings) - 5} more*")

        if config.include_content and page.content:
            lines.append("")
            lines.append("**Content Preview:**")
            lines.append("```")
            preview = page.content[:config.max_content_length]
            if len(page.content) > config.max_content_length:
                preview += "\n...[truncated]"
            lines.append(preview)
            lines.append("```")

        lines.append("")
        lines.append("---")
        lines.append("")

        return lines


# Global enhanced formatter instance
enhanced_formatter = EnhancedFormatter()
