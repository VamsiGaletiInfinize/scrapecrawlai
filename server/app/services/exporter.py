"""
Directory exporter for organized output files.

Creates structured directory exports with ZIP support for
multi-format crawl results.
"""

import os
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models.output import (
    OrganizedOutput, OutputConfig, OutputFormat, OrganizationType,
    SubdomainGroup, DepthGroup, ContentTypeGroup, EnhancedPageResult,
)
from .enhanced_formatter import EnhancedFormatter, enhanced_formatter


class DirectoryExporter:
    """
    Exports organized crawl results to directory structure or ZIP file.

    Directory structure:
    output/
    ├── metadata.json
    ├── summary.md
    ├── by_subdomain/
    │   ├── index.md
    │   ├── www/
    │   │   ├── index.md
    │   │   └── pages.json
    │   └── catalog/
    │       ├── index.md
    │       └── pages.json
    ├── by_depth/
    │   ├── index.md
    │   ├── depth_1/
    │   │   ├── index.md
    │   │   └── pages.json
    │   └── depth_2/
    │       └── ...
    └── by_content_type/
        ├── index.md
        ├── academic/
        │   ├── index.md
        │   └── pages.json
        └── faculty/
            └── ...
    """

    def __init__(self, formatter: Optional[EnhancedFormatter] = None):
        """
        Initialize the exporter.

        Args:
            formatter: Enhanced formatter instance
        """
        self.formatter = formatter or enhanced_formatter

    def export_to_zip(
        self,
        organized: OrganizedOutput,
        config: OutputConfig,
    ) -> bytes:
        """
        Export organized results to a ZIP file in memory.

        Args:
            organized: Organized output data
            config: Output configuration

        Returns:
            ZIP file as bytes
        """
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add metadata.json
            metadata_json = json.dumps(
                organized.metadata.model_dump(),
                indent=2,
                ensure_ascii=False,
            )
            zf.writestr('metadata.json', metadata_json)

            # Add timing.json
            timing_json = json.dumps(
                organized.timing.model_dump(),
                indent=2,
            )
            zf.writestr('timing.json', timing_json)

            # Add summary.md
            summary_md = self._create_summary_markdown(organized)
            zf.writestr('summary.md', summary_md)

            # Add all pages in flat format
            all_pages_json = json.dumps(
                [self._page_to_dict(p, config) for p in organized.all_pages],
                indent=2,
                ensure_ascii=False,
            )
            zf.writestr('all_pages.json', all_pages_json)

            # Create by_subdomain directory
            self._add_subdomain_files(zf, organized.by_subdomain, config)

            # Create by_depth directory
            self._add_depth_files(zf, organized.by_depth, config)

            # Create by_content_type directory
            self._add_content_type_files(zf, organized.by_content_type, config)

            # Add master index
            index_md = self._create_master_index(organized)
            zf.writestr('index.md', index_md)

        buffer.seek(0)
        return buffer.read()

    def export_to_directory(
        self,
        organized: OrganizedOutput,
        config: OutputConfig,
        output_dir: str,
    ) -> str:
        """
        Export organized results to a directory structure.

        Args:
            organized: Organized output data
            config: Output configuration
            output_dir: Base output directory path

        Returns:
            Path to the created directory
        """
        base_path = Path(output_dir)
        job_dir = base_path / f"crawl_{organized.metadata.job_id}"
        job_dir.mkdir(parents=True, exist_ok=True)

        # Write metadata.json
        with open(job_dir / 'metadata.json', 'w', encoding='utf-8') as f:
            json.dump(organized.metadata.model_dump(), f, indent=2, ensure_ascii=False)

        # Write timing.json
        with open(job_dir / 'timing.json', 'w', encoding='utf-8') as f:
            json.dump(organized.timing.model_dump(), f, indent=2)

        # Write summary.md
        with open(job_dir / 'summary.md', 'w', encoding='utf-8') as f:
            f.write(self._create_summary_markdown(organized))

        # Write all_pages.json
        with open(job_dir / 'all_pages.json', 'w', encoding='utf-8') as f:
            pages_data = [self._page_to_dict(p, config) for p in organized.all_pages]
            json.dump(pages_data, f, indent=2, ensure_ascii=False)

        # Create by_subdomain directory
        subdomain_dir = job_dir / 'by_subdomain'
        subdomain_dir.mkdir(exist_ok=True)
        self._write_subdomain_files(subdomain_dir, organized.by_subdomain, config)

        # Create by_depth directory
        depth_dir = job_dir / 'by_depth'
        depth_dir.mkdir(exist_ok=True)
        self._write_depth_files(depth_dir, organized.by_depth, config)

        # Create by_content_type directory
        content_type_dir = job_dir / 'by_content_type'
        content_type_dir.mkdir(exist_ok=True)
        self._write_content_type_files(content_type_dir, organized.by_content_type, config)

        # Write master index
        with open(job_dir / 'index.md', 'w', encoding='utf-8') as f:
            f.write(self._create_master_index(organized))

        return str(job_dir)

    def _page_to_dict(self, page: EnhancedPageResult, config: OutputConfig) -> dict:
        """Convert a page to dictionary format."""
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

    def _create_summary_markdown(self, organized: OrganizedOutput) -> str:
        """Create summary markdown content."""
        lines = [
            f"# Crawl Summary: {organized.metadata.seed_url}",
            "",
            f"**Job ID:** {organized.metadata.job_id}",
            f"**Generated:** {datetime.utcnow().isoformat()}Z",
            "",
            "## Statistics",
            "",
            f"- Total Pages: {organized.summary['total_pages']}",
            f"- Successful: {organized.summary['successful_pages']}",
            f"- Failed: {organized.summary['failed_pages']}",
            f"- Total Words: {organized.summary['total_word_count']:,}",
            f"- Subdomains: {organized.summary['subdomain_count']}",
            f"- Max Depth: {organized.summary['max_depth_reached']}",
            "",
            "## Timing",
            "",
            f"- Total: {organized.timing.total_ms:.2f}ms",
            f"- Crawling: {organized.timing.crawling_ms:.2f}ms",
            f"- Scraping: {organized.timing.scraping_ms:.2f}ms",
            f"- Avg Page: {organized.timing.avg_page_time_ms:.2f}ms",
            "",
            "## Content Types",
            "",
        ]

        for ct, count in organized.summary['content_type_distribution'].items():
            lines.append(f"- {ct}: {count} pages")

        lines.extend(["", "## Subdomains", ""])
        for subdomain, count in organized.summary['subdomain_distribution'].items():
            lines.append(f"- {subdomain}: {count} pages")

        return "\n".join(lines)

    def _create_master_index(self, organized: OrganizedOutput) -> str:
        """Create master index markdown."""
        lines = [
            f"# Crawl Export: {organized.metadata.seed_url}",
            "",
            f"**Job ID:** {organized.metadata.job_id}",
            f"**Total Pages:** {organized.summary['total_pages']}",
            "",
            "## Directory Structure",
            "",
            "- [metadata.json](metadata.json) - Job metadata",
            "- [timing.json](timing.json) - Timing breakdown",
            "- [summary.md](summary.md) - Summary report",
            "- [all_pages.json](all_pages.json) - All pages in flat format",
            "",
            "### By Subdomain",
            "",
        ]

        for group in organized.by_subdomain:
            lines.append(f"- [{group.subdomain}/](by_subdomain/{group.subdomain}/) - {group.page_count} pages")

        lines.extend(["", "### By Depth", ""])
        for group in organized.by_depth:
            lines.append(f"- [depth_{group.depth}/](by_depth/depth_{group.depth}/) - {group.page_count} pages")

        lines.extend(["", "### By Content Type", ""])
        for group in organized.by_content_type:
            lines.append(f"- [{group.content_type.value}/](by_content_type/{group.content_type.value}/) - {group.page_count} pages")

        return "\n".join(lines)

    def _add_subdomain_files(
        self,
        zf: zipfile.ZipFile,
        groups: list[SubdomainGroup],
        config: OutputConfig,
    ):
        """Add subdomain files to ZIP."""
        # Index file
        index_lines = ["# Pages by Subdomain", ""]
        for group in groups:
            index_lines.append(f"- [{group.subdomain}]({group.subdomain}/) - {group.page_count} pages")
        zf.writestr('by_subdomain/index.md', "\n".join(index_lines))

        # Individual subdomain directories
        for group in groups:
            safe_name = self._safe_filename(group.subdomain)

            # Pages JSON
            pages_data = [self._page_to_dict(p, config) for p in group.pages]
            zf.writestr(
                f'by_subdomain/{safe_name}/pages.json',
                json.dumps(pages_data, indent=2, ensure_ascii=False),
            )

            # Index markdown
            index_md = self._create_group_index(
                title=f"Subdomain: {group.subdomain}",
                stats={
                    'Page Count': group.page_count,
                    'Total Words': f"{group.total_word_count:,}",
                },
                pages=group.pages,
            )
            zf.writestr(f'by_subdomain/{safe_name}/index.md', index_md)

    def _add_depth_files(
        self,
        zf: zipfile.ZipFile,
        groups: list[DepthGroup],
        config: OutputConfig,
    ):
        """Add depth files to ZIP."""
        # Index file
        index_lines = ["# Pages by Depth", ""]
        for group in groups:
            index_lines.append(f"- [Depth {group.depth}](depth_{group.depth}/) - {group.page_count} pages")
        zf.writestr('by_depth/index.md', "\n".join(index_lines))

        # Individual depth directories
        for group in groups:
            dir_name = f"depth_{group.depth}"

            # Pages JSON
            pages_data = [self._page_to_dict(p, config) for p in group.pages]
            zf.writestr(
                f'by_depth/{dir_name}/pages.json',
                json.dumps(pages_data, indent=2, ensure_ascii=False),
            )

            # Index markdown
            index_md = self._create_group_index(
                title=f"Depth Level: {group.depth}",
                stats={
                    'Page Count': group.page_count,
                    'Subdomains': ', '.join(group.subdomains),
                },
                pages=group.pages,
            )
            zf.writestr(f'by_depth/{dir_name}/index.md', index_md)

    def _add_content_type_files(
        self,
        zf: zipfile.ZipFile,
        groups: list[ContentTypeGroup],
        config: OutputConfig,
    ):
        """Add content type files to ZIP."""
        # Index file
        index_lines = ["# Pages by Content Type", ""]
        for group in groups:
            index_lines.append(f"- [{group.content_type.value}]({group.content_type.value}/) - {group.page_count} pages")
        zf.writestr('by_content_type/index.md', "\n".join(index_lines))

        # Individual content type directories
        for group in groups:
            dir_name = group.content_type.value

            # Pages JSON
            pages_data = [self._page_to_dict(p, config) for p in group.pages]
            zf.writestr(
                f'by_content_type/{dir_name}/pages.json',
                json.dumps(pages_data, indent=2, ensure_ascii=False),
            )

            # Index markdown
            index_md = self._create_group_index(
                title=f"Content Type: {group.content_type.value.title()}",
                stats={
                    'Page Count': group.page_count,
                    'Subdomains': ', '.join(group.subdomains),
                },
                pages=group.pages,
            )
            zf.writestr(f'by_content_type/{dir_name}/index.md', index_md)

    def _write_subdomain_files(
        self,
        base_dir: Path,
        groups: list[SubdomainGroup],
        config: OutputConfig,
    ):
        """Write subdomain files to directory."""
        # Index file
        index_lines = ["# Pages by Subdomain", ""]
        for group in groups:
            index_lines.append(f"- [{group.subdomain}]({group.subdomain}/) - {group.page_count} pages")
        with open(base_dir / 'index.md', 'w', encoding='utf-8') as f:
            f.write("\n".join(index_lines))

        # Individual subdomain directories
        for group in groups:
            safe_name = self._safe_filename(group.subdomain)
            group_dir = base_dir / safe_name
            group_dir.mkdir(exist_ok=True)

            # Pages JSON
            pages_data = [self._page_to_dict(p, config) for p in group.pages]
            with open(group_dir / 'pages.json', 'w', encoding='utf-8') as f:
                json.dump(pages_data, f, indent=2, ensure_ascii=False)

            # Index markdown
            index_md = self._create_group_index(
                title=f"Subdomain: {group.subdomain}",
                stats={
                    'Page Count': group.page_count,
                    'Total Words': f"{group.total_word_count:,}",
                },
                pages=group.pages,
            )
            with open(group_dir / 'index.md', 'w', encoding='utf-8') as f:
                f.write(index_md)

    def _write_depth_files(
        self,
        base_dir: Path,
        groups: list[DepthGroup],
        config: OutputConfig,
    ):
        """Write depth files to directory."""
        # Index file
        index_lines = ["# Pages by Depth", ""]
        for group in groups:
            index_lines.append(f"- [Depth {group.depth}](depth_{group.depth}/) - {group.page_count} pages")
        with open(base_dir / 'index.md', 'w', encoding='utf-8') as f:
            f.write("\n".join(index_lines))

        # Individual depth directories
        for group in groups:
            dir_name = f"depth_{group.depth}"
            group_dir = base_dir / dir_name
            group_dir.mkdir(exist_ok=True)

            # Pages JSON
            pages_data = [self._page_to_dict(p, config) for p in group.pages]
            with open(group_dir / 'pages.json', 'w', encoding='utf-8') as f:
                json.dump(pages_data, f, indent=2, ensure_ascii=False)

            # Index markdown
            index_md = self._create_group_index(
                title=f"Depth Level: {group.depth}",
                stats={
                    'Page Count': group.page_count,
                    'Subdomains': ', '.join(group.subdomains),
                },
                pages=group.pages,
            )
            with open(group_dir / 'index.md', 'w', encoding='utf-8') as f:
                f.write(index_md)

    def _write_content_type_files(
        self,
        base_dir: Path,
        groups: list[ContentTypeGroup],
        config: OutputConfig,
    ):
        """Write content type files to directory."""
        # Index file
        index_lines = ["# Pages by Content Type", ""]
        for group in groups:
            index_lines.append(f"- [{group.content_type.value}]({group.content_type.value}/) - {group.page_count} pages")
        with open(base_dir / 'index.md', 'w', encoding='utf-8') as f:
            f.write("\n".join(index_lines))

        # Individual content type directories
        for group in groups:
            dir_name = group.content_type.value
            group_dir = base_dir / dir_name
            group_dir.mkdir(exist_ok=True)

            # Pages JSON
            pages_data = [self._page_to_dict(p, config) for p in group.pages]
            with open(group_dir / 'pages.json', 'w', encoding='utf-8') as f:
                json.dump(pages_data, f, indent=2, ensure_ascii=False)

            # Index markdown
            index_md = self._create_group_index(
                title=f"Content Type: {group.content_type.value.title()}",
                stats={
                    'Page Count': group.page_count,
                    'Subdomains': ', '.join(group.subdomains),
                },
                pages=group.pages,
            )
            with open(group_dir / 'index.md', 'w', encoding='utf-8') as f:
                f.write(index_md)

    def _create_group_index(
        self,
        title: str,
        stats: dict,
        pages: list[EnhancedPageResult],
    ) -> str:
        """Create index markdown for a group."""
        lines = [f"# {title}", ""]

        for key, value in stats.items():
            lines.append(f"**{key}:** {value}")
        lines.append("")

        lines.append("## Pages")
        lines.append("")
        lines.append("| Title | URL | Words | Type |")
        lines.append("|-------|-----|-------|------|")

        for page in pages:  # All pages without limit
            title = (page.metadata.title or 'Untitled')[:50]
            url = page.metadata.url[:60] + ('...' if len(page.metadata.url) > 60 else '')
            lines.append(f"| {title} | {url} | {page.metadata.word_count} | {page.metadata.content_type.value} |")

        return "\n".join(lines)

    @staticmethod
    def _safe_filename(name: str) -> str:
        """Convert a string to a safe filename."""
        # Replace unsafe characters
        safe = name.replace('/', '_').replace('\\', '_').replace(':', '_')
        safe = safe.replace('<', '_').replace('>', '_').replace('"', '_')
        safe = safe.replace('|', '_').replace('?', '_').replace('*', '_')
        return safe or 'unknown'


# Global exporter instance
directory_exporter = DirectoryExporter()
