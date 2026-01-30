import json
from datetime import datetime
from typing import Optional

from ..models.crawl import CrawlResult, PageResult, TimingMetrics, DepthStats, CrawlMode, PageStatus


class OutputFormatter:
    """
    Service for formatting crawl results into JSON and Markdown outputs.

    Generates single combined files with all crawled pages and timing data.
    """

    @staticmethod
    def to_json(result: CrawlResult) -> str:
        """
        Format crawl results as JSON.

        Args:
            result: Complete crawl results

        Returns:
            JSON string with all data
        """
        output = {
            "metadata": {
                "job_id": result.job_id,
                "seed_url": result.seed_url,
                "mode": result.mode.value,
                "max_depth": result.max_depth,
                "worker_count": result.worker_count,
                "state": result.state.value,
                "generated_at": datetime.utcnow().isoformat() + "Z",
            },
            "timing": {
                "url_discovery_ms": result.timing.url_discovery_ms,
                "crawling_ms": result.timing.crawling_ms,
                "scraping_ms": result.timing.scraping_ms,
                "total_ms": result.timing.total_ms,
            },
            "summary": {
                "total_urls_discovered": result.total_urls_discovered,
                "total_pages_scraped": result.total_pages_scraped,
                "depth_breakdown": [
                    {
                        "depth": ds.depth,
                        "count": ds.urls_count,
                        "urls": ds.urls,
                    }
                    for ds in result.urls_by_depth
                ],
            },
            "pages": [
                {
                    "url": page.url,
                    "parent_url": page.parent_url,
                    "depth": page.depth,
                    "title": page.title,
                    "headings": page.headings,
                    "content": page.content,
                    "links_found": page.links_found,
                    "timing_ms": page.timing_ms,
                    "timing": {
                        "total_ms": page.page_timing.total_ms,
                        "crawl_ms": page.page_timing.crawl_ms,
                        "scrape_ms": page.page_timing.scrape_ms,
                        "time_before_failure_ms": page.page_timing.time_before_failure_ms,
                    },
                    "status": page.status.value,
                    "skip_reason": page.skip_reason.value if page.status == PageStatus.SKIPPED else None,
                    "error": page.error,
                    "failure": {
                        "phase": page.failure.phase.value,
                        "type": page.failure.type.value,
                        "reason": page.failure.reason,
                        "http_status": page.failure.http_status,
                    } if page.failure.phase.value != "none" else None,
                }
                for page in result.pages
            ],
        }

        return json.dumps(output, indent=2, ensure_ascii=False)

    @staticmethod
    def to_markdown(result: CrawlResult) -> str:
        """
        Format crawl results as Markdown.

        Args:
            result: Complete crawl results

        Returns:
            Markdown formatted string
        """
        lines = []

        # Header
        lines.append(f"# Crawl Report: {result.seed_url}")
        lines.append("")
        lines.append(f"**Job ID:** {result.job_id}")
        lines.append(f"**Mode:** {result.mode.value}")
        lines.append(f"**Max Depth:** {result.max_depth}")
        lines.append(f"**Workers:** {result.worker_count}")
        lines.append(f"**Status:** {result.state.value}")
        lines.append(f"**Generated:** {datetime.utcnow().isoformat()}Z")
        lines.append("")

        # Timing Summary
        lines.append("## Timing Summary")
        lines.append("")
        lines.append("| Metric | Time (ms) |")
        lines.append("|--------|-----------|")
        lines.append(f"| URL Discovery | {result.timing.url_discovery_ms:.2f} |")
        lines.append(f"| Crawling | {result.timing.crawling_ms:.2f} |")
        lines.append(f"| Scraping | {result.timing.scraping_ms:.2f} |")
        lines.append(f"| **Total** | **{result.timing.total_ms:.2f}** |")
        lines.append("")

        # Statistics
        lines.append("## Statistics")
        lines.append("")
        lines.append(f"- **Total URLs Discovered:** {result.total_urls_discovered}")
        lines.append(f"- **Total Pages Scraped:** {result.total_pages_scraped}")
        lines.append("")

        # URLs by Depth
        lines.append("## URLs by Depth")
        lines.append("")
        for ds in result.urls_by_depth:
            lines.append(f"### Depth {ds.depth} ({ds.urls_count} URLs)")
            lines.append("")
            for url in ds.urls:  # Show all URLs for sitemap comparison
                lines.append(f"- {url}")
            lines.append("")

        # Pages Content
        lines.append("## Pages")
        lines.append("")

        for page in result.pages:
            lines.append(f"### {page.title or page.url}")
            lines.append("")
            lines.append(f"**URL:** {page.url}")
            if page.parent_url:
                lines.append(f"**Parent:** {page.parent_url}")
            lines.append(f"**Depth:** {page.depth}")
            lines.append(f"**Status:** {page.status.value}")
            if page.status == PageStatus.SKIPPED:
                lines.append(f"**Skip Reason:** {page.skip_reason.value}")
            lines.append(f"**Links Found:** {page.links_found}")
            lines.append(f"**Processing Time:** {page.timing_ms:.2f}ms")
            lines.append(f"**Crawl Time:** {page.page_timing.crawl_ms:.2f}ms")
            lines.append(f"**Scrape Time:** {page.page_timing.scrape_ms:.2f}ms")

            if page.error:
                lines.append(f"**Error:** {page.error}")

            if page.failure.phase.value != "none":
                lines.append("")
                lines.append("**Failure Details:**")
                lines.append(f"- Phase: {page.failure.phase.value}")
                lines.append(f"- Type: {page.failure.type.value}")
                if page.failure.reason:
                    lines.append(f"- Reason: {page.failure.reason}")
                if page.failure.http_status:
                    lines.append(f"- HTTP Status: {page.failure.http_status}")

            if page.headings:
                lines.append("")
                lines.append("**Headings:**")
                for heading in page.headings:  # Show all headings
                    lines.append(f"- {heading}")

            if page.content:
                lines.append("")
                lines.append("**Content:**")
                lines.append("")
                lines.append("```")
                lines.append(page.content)  # Full content without truncation
                lines.append("```")

            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_timing_breakdown(timing: TimingMetrics) -> dict:
        """
        Format timing metrics for API response.

        Args:
            timing: Timing metrics

        Returns:
            Dictionary with formatted timing data
        """
        total = timing.total_ms
        return {
            "url_discovery_ms": round(timing.url_discovery_ms, 2),
            "url_discovery_pct": round((timing.url_discovery_ms / total * 100) if total > 0 else 0, 1),
            "crawling_ms": round(timing.crawling_ms, 2),
            "crawling_pct": round((timing.crawling_ms / total * 100) if total > 0 else 0, 1),
            "scraping_ms": round(timing.scraping_ms, 2),
            "scraping_pct": round((timing.scraping_ms / total * 100) if total > 0 else 0, 1),
            "total_ms": round(total, 2),
        }

    @staticmethod
    def create_summary(
        pages: list[PageResult],
        timing: TimingMetrics,
        depth_stats: list[DepthStats],
        mode: CrawlMode,
    ) -> dict:
        """
        Create a summary of crawl results.

        Args:
            pages: List of page results
            timing: Timing metrics
            depth_stats: URLs grouped by depth
            mode: Crawl mode used

        Returns:
            Summary dictionary
        """
        # Categorize pages by status
        scraped_pages = [p for p in pages if p.status == PageStatus.SCRAPED]
        crawled_pages = [p for p in pages if p.status == PageStatus.CRAWLED]
        skipped_pages = [p for p in pages if p.status == PageStatus.SKIPPED]
        error_pages = [p for p in pages if p.status == PageStatus.ERROR]

        # Legacy: successful = non-error pages (including skipped)
        successful_pages = [p for p in pages if p.status != PageStatus.ERROR]
        failed_pages = error_pages

        # Count failures by phase (skipped pages are NOT failures)
        crawl_failures = sum(1 for p in pages if p.status == PageStatus.ERROR and p.failure.phase.value == "crawl")
        scrape_failures = sum(1 for p in pages if p.status == PageStatus.ERROR and p.failure.phase.value == "scrape")

        # Calculate timing breakdowns
        total_crawl_ms = sum(p.page_timing.crawl_ms for p in pages)
        total_scrape_ms = sum(p.page_timing.scrape_ms for p in pages)

        return {
            "total_pages": len(pages),
            "successful_pages": len(successful_pages),
            "failed_pages": len(failed_pages),
            "scraped_pages": len(scraped_pages),
            "skipped_pages": len(skipped_pages),
            "crawled_pages": len(crawled_pages),
            "total_links_found": sum(p.links_found for p in pages),
            "depth_distribution": {
                ds.depth: ds.urls_count for ds in depth_stats
            },
            "avg_page_time_ms": round(
                sum(p.timing_ms for p in pages) / len(pages) if pages else 0,
                2
            ),
            "mode": mode.value,
            # Enhanced timing breakdown
            "timing_breakdown": {
                "url_discovery_ms": round(timing.url_discovery_ms, 2),
                "crawling_ms": round(timing.crawling_ms, 2),
                "scraping_ms": round(timing.scraping_ms, 2),
                "total_ms": round(timing.total_ms, 2),
                "avg_crawl_per_page_ms": round(total_crawl_ms / len(pages), 2) if pages else 0,
                "avg_scrape_per_page_ms": round(total_scrape_ms / len(pages), 2) if pages else 0,
            },
            # Enhanced failure breakdown
            "failure_breakdown": {
                "crawl_failures": crawl_failures,
                "scrape_failures": scrape_failures,
                "total_failures": crawl_failures + scrape_failures,
            },
        }
