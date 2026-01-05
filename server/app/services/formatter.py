import json
from datetime import datetime
from typing import Optional

from ..models.crawl import CrawlResult, PageResult, TimingMetrics, DepthStats, CrawlMode


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
                    "error": page.error,
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
            for url in ds.urls[:50]:  # Limit to 50 per depth
                lines.append(f"- {url}")
            if len(ds.urls) > 50:
                lines.append(f"- ... and {len(ds.urls) - 50} more")
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
            lines.append(f"**Links Found:** {page.links_found}")
            lines.append(f"**Processing Time:** {page.timing_ms:.2f}ms")

            if page.error:
                lines.append(f"**Error:** {page.error}")

            if page.headings:
                lines.append("")
                lines.append("**Headings:**")
                for heading in page.headings[:10]:
                    lines.append(f"- {heading}")
                if len(page.headings) > 10:
                    lines.append(f"- ... and {len(page.headings) - 10} more")

            if page.content:
                lines.append("")
                lines.append("**Content Preview:**")
                lines.append("")
                lines.append("```")
                # Limit content preview
                preview = page.content[:2000]
                if len(page.content) > 2000:
                    preview += "\n...[truncated]"
                lines.append(preview)
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
        successful_pages = [p for p in pages if not p.error]
        failed_pages = [p for p in pages if p.error]
        scraped_pages = [p for p in pages if p.content]

        return {
            "total_pages": len(pages),
            "successful_pages": len(successful_pages),
            "failed_pages": len(failed_pages),
            "scraped_pages": len(scraped_pages),
            "total_links_found": sum(p.links_found for p in pages),
            "depth_distribution": {
                ds.depth: ds.urls_count for ds in depth_stats
            },
            "avg_page_time_ms": round(
                sum(p.timing_ms for p in pages) / len(pages) if pages else 0,
                2
            ),
            "mode": mode.value,
        }
