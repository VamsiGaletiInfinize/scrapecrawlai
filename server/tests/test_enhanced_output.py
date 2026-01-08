"""
Unit tests for enhanced output organization components.

Tests content classification, enhanced formatting, and export functionality.
"""

import pytest
import json
from datetime import datetime

# Test imports
from app.models.output import (
    ContentType, OutputFormat, OrganizationType, OutputConfig,
    PageMetadata, EnhancedPageResult, SubdomainGroup, DepthGroup,
    ContentTypeGroup, CrawlMetadata, TimingBreakdown, OrganizedOutput,
)
from app.models.crawl import CrawlResult, PageResult, CrawlState, CrawlMode, TimingMetrics, DepthStats
from app.services.classifier import ContentClassifier, content_classifier
from app.services.enhanced_formatter import EnhancedFormatter, enhanced_formatter
from app.services.exporter import DirectoryExporter, directory_exporter


class TestContentClassifier:
    """Tests for the ContentClassifier service."""

    def test_classify_academic_url(self):
        """Test classification of academic URLs."""
        classifier = ContentClassifier()

        # Academic URL patterns
        assert classifier.classify("https://gmu.edu/academics/programs") == ContentType.ACADEMIC
        assert classifier.classify("https://catalog.gmu.edu/courses/CS") == ContentType.ACADEMIC
        assert classifier.classify("https://gmu.edu/graduate/degrees") == ContentType.ACADEMIC

    def test_classify_faculty_url(self):
        """Test classification of faculty URLs."""
        classifier = ContentClassifier()

        assert classifier.classify("https://gmu.edu/faculty/john-doe") == ContentType.FACULTY
        assert classifier.classify("https://cs.gmu.edu/~jdoe") == ContentType.FACULTY
        assert classifier.classify("https://gmu.edu/directory/staff") == ContentType.FACULTY

    def test_classify_research_url(self):
        """Test classification of research URLs."""
        classifier = ContentClassifier()

        assert classifier.classify("https://gmu.edu/research/projects") == ContentType.RESEARCH
        assert classifier.classify("https://labs.gmu.edu/ai") == ContentType.RESEARCH
        assert classifier.classify("https://gmu.edu/publications/2024") == ContentType.RESEARCH

    def test_classify_administrative_url(self):
        """Test classification of administrative URLs."""
        classifier = ContentClassifier()

        assert classifier.classify("https://gmu.edu/admissions/apply") == ContentType.ADMINISTRATIVE
        assert classifier.classify("https://gmu.edu/registrar") == ContentType.ADMINISTRATIVE
        assert classifier.classify("https://gmu.edu/financial/tuition") == ContentType.ADMINISTRATIVE

    def test_classify_news_url(self):
        """Test classification of news URLs."""
        classifier = ContentClassifier()

        assert classifier.classify("https://gmu.edu/news/2024/announcement") == ContentType.NEWS
        assert classifier.classify("https://gmu.edu/press/releases") == ContentType.NEWS

    def test_classify_events_url(self):
        """Test classification of event URLs."""
        classifier = ContentClassifier()

        assert classifier.classify("https://gmu.edu/events/calendar") == ContentType.EVENTS
        assert classifier.classify("https://gmu.edu/workshops/spring") == ContentType.EVENTS

    def test_classify_resources_url(self):
        """Test classification of resource URLs."""
        classifier = ContentClassifier()

        assert classifier.classify("https://gmu.edu/library/resources") == ContentType.RESOURCES
        assert classifier.classify("https://gmu.edu/help/faq") == ContentType.RESOURCES

    def test_classify_with_title(self):
        """Test classification using title keywords."""
        classifier = ContentClassifier()

        # URL alone wouldn't classify, but title should
        result = classifier.classify(
            "https://gmu.edu/page",
            title="Computer Science Program Requirements"
        )
        assert result == ContentType.ACADEMIC

        result = classifier.classify(
            "https://gmu.edu/person",
            title="Dr. John Smith - Professor of Computer Science"
        )
        assert result == ContentType.FACULTY

    def test_classify_with_content(self):
        """Test classification using content keywords."""
        classifier = ContentClassifier()

        result = classifier.classify(
            "https://gmu.edu/page",
            title="Course Details",
            content="This course has 3 credit hours and requires GPA of 3.0. Prerequisites include CS 101."
        )
        assert result == ContentType.ACADEMIC

    def test_classify_unknown_url(self):
        """Test classification of unrecognizable URLs."""
        classifier = ContentClassifier()

        result = classifier.classify("https://example.com/random-page")
        assert result == ContentType.OTHER

    def test_extract_subdomain(self):
        """Test subdomain extraction."""
        assert ContentClassifier.extract_subdomain("https://www.gmu.edu/page") == "www"
        assert ContentClassifier.extract_subdomain("https://catalog.gmu.edu/page") == "catalog"
        assert ContentClassifier.extract_subdomain("https://cs.gmu.edu/page") == "cs"
        assert ContentClassifier.extract_subdomain("https://gmu.edu/page") == "www"

    def test_classify_batch(self):
        """Test batch classification."""
        classifier = ContentClassifier()

        pages = [
            {"url": "https://gmu.edu/academics/", "title": "Academics"},
            {"url": "https://gmu.edu/faculty/", "title": "Faculty"},
            {"url": "https://gmu.edu/news/", "title": "News"},
        ]

        results = classifier.classify_batch(pages)

        assert results["https://gmu.edu/academics/"] == ContentType.ACADEMIC
        assert results["https://gmu.edu/faculty/"] == ContentType.FACULTY
        assert results["https://gmu.edu/news/"] == ContentType.NEWS


class TestEnhancedFormatter:
    """Tests for the EnhancedFormatter service."""

    @pytest.fixture
    def sample_crawl_result(self):
        """Create a sample crawl result for testing."""
        pages = [
            PageResult(
                url="https://www.gmu.edu/",
                depth=1,
                title="George Mason University",
                content="Welcome to GMU, a public research university.",
                headings=["Welcome", "About Us"],
                links_found=50,
                timing_ms=150.5,
            ),
            PageResult(
                url="https://www.gmu.edu/academics/",
                parent_url="https://www.gmu.edu/",
                depth=2,
                title="Academics | GMU",
                content="Academic programs and courses at GMU.",
                headings=["Programs", "Courses"],
                links_found=30,
                timing_ms=120.3,
            ),
            PageResult(
                url="https://catalog.gmu.edu/courses/",
                parent_url="https://www.gmu.edu/academics/",
                depth=3,
                title="Course Catalog",
                content="Browse all courses at GMU.",
                headings=["Undergraduate", "Graduate"],
                links_found=100,
                timing_ms=200.1,
            ),
            PageResult(
                url="https://www.gmu.edu/faculty/",
                parent_url="https://www.gmu.edu/",
                depth=2,
                title="Faculty Directory",
                content="Meet our faculty members.",
                headings=["Professors", "Staff"],
                links_found=80,
                timing_ms=180.0,
            ),
        ]

        return CrawlResult(
            job_id="test123",
            seed_url="https://www.gmu.edu/",
            mode=CrawlMode.CRAWL_SCRAPE,
            max_depth=3,
            worker_count=4,
            allow_subdomains=True,
            allowed_domains=[],
            state=CrawlState.COMPLETED,
            timing=TimingMetrics(
                url_discovery_ms=100.0,
                crawling_ms=500.0,
                scraping_ms=150.0,
                total_ms=750.0,
            ),
            urls_by_depth=[
                DepthStats(depth=1, urls_count=1, urls=["https://www.gmu.edu/"]),
                DepthStats(depth=2, urls_count=2, urls=["https://www.gmu.edu/academics/", "https://www.gmu.edu/faculty/"]),
                DepthStats(depth=3, urls_count=1, urls=["https://catalog.gmu.edu/courses/"]),
            ],
            pages=pages,
            total_urls_discovered=4,
            total_pages_scraped=4,
        )

    def test_organize_results(self, sample_crawl_result):
        """Test organizing crawl results."""
        formatter = EnhancedFormatter()
        organized = formatter.organize_results(sample_crawl_result)

        # Check metadata
        assert organized.metadata.job_id == "test123"
        assert organized.metadata.seed_url == "https://www.gmu.edu/"
        assert organized.metadata.max_depth == 3

        # Check timing
        assert organized.timing.total_ms == 750.0
        assert organized.timing.avg_page_time_ms > 0

        # Check all pages enhanced
        assert len(organized.all_pages) == 4
        for page in organized.all_pages:
            assert page.metadata.subdomain in ["www", "catalog"]
            assert page.metadata.content_type in ContentType

    def test_group_by_subdomain(self, sample_crawl_result):
        """Test grouping by subdomain."""
        formatter = EnhancedFormatter()
        organized = formatter.organize_results(sample_crawl_result)

        # Should have www and catalog subdomains
        subdomains = [g.subdomain for g in organized.by_subdomain]
        assert "www" in subdomains
        assert "catalog" in subdomains

        # www should have 3 pages, catalog should have 1
        www_group = next(g for g in organized.by_subdomain if g.subdomain == "www")
        catalog_group = next(g for g in organized.by_subdomain if g.subdomain == "catalog")

        assert www_group.page_count == 3
        assert catalog_group.page_count == 1

    def test_group_by_depth(self, sample_crawl_result):
        """Test grouping by depth."""
        formatter = EnhancedFormatter()
        organized = formatter.organize_results(sample_crawl_result)

        depths = [g.depth for g in organized.by_depth]
        assert 1 in depths
        assert 2 in depths
        assert 3 in depths

        depth_1 = next(g for g in organized.by_depth if g.depth == 1)
        depth_2 = next(g for g in organized.by_depth if g.depth == 2)
        depth_3 = next(g for g in organized.by_depth if g.depth == 3)

        assert depth_1.page_count == 1
        assert depth_2.page_count == 2
        assert depth_3.page_count == 1

    def test_group_by_content_type(self, sample_crawl_result):
        """Test grouping by content type."""
        formatter = EnhancedFormatter()
        organized = formatter.organize_results(sample_crawl_result)

        # Should have multiple content types
        content_types = [g.content_type for g in organized.by_content_type]
        assert len(content_types) > 0

    def test_to_json_flat(self, sample_crawl_result):
        """Test JSON output with flat organization."""
        formatter = EnhancedFormatter()
        organized = formatter.organize_results(sample_crawl_result)

        config = OutputConfig(format=OutputFormat.JSON, organization=OrganizationType.FLAT)
        json_output = formatter.to_json(organized, config)

        # Should be valid JSON
        data = json.loads(json_output)
        assert "metadata" in data
        assert "timing" in data
        assert "summary" in data
        assert "pages" in data
        assert len(data["pages"]) == 4

    def test_to_json_by_subdomain(self, sample_crawl_result):
        """Test JSON output organized by subdomain."""
        formatter = EnhancedFormatter()
        organized = formatter.organize_results(sample_crawl_result)

        config = OutputConfig(format=OutputFormat.JSON, organization=OrganizationType.BY_SUBDOMAIN)
        json_output = formatter.to_json(organized, config)

        data = json.loads(json_output)
        assert "by_subdomain" in data
        assert len(data["by_subdomain"]) >= 2

    def test_to_markdown(self, sample_crawl_result):
        """Test Markdown output generation."""
        formatter = EnhancedFormatter()
        organized = formatter.organize_results(sample_crawl_result)

        config = OutputConfig(format=OutputFormat.MARKDOWN, organization=OrganizationType.FLAT)
        md_output = formatter.to_markdown(organized, config)

        # Should contain expected sections
        assert "# Crawl Report:" in md_output
        assert "## Metadata" in md_output
        assert "## Timing" in md_output
        assert "## Summary" in md_output
        assert "## All Pages" in md_output

    def test_to_csv(self, sample_crawl_result):
        """Test CSV output generation."""
        formatter = EnhancedFormatter()
        organized = formatter.organize_results(sample_crawl_result)

        config = OutputConfig(format=OutputFormat.CSV)
        csv_output = formatter.to_csv(organized, config)

        lines = csv_output.strip().split("\n")
        # Header + 4 data rows
        assert len(lines) == 5

        # Check header
        header = lines[0]
        assert "URL" in header
        assert "Subdomain" in header
        assert "Content Type" in header

    def test_content_truncation(self, sample_crawl_result):
        """Test content truncation based on config."""
        formatter = EnhancedFormatter()
        organized = formatter.organize_results(sample_crawl_result)

        config = OutputConfig(
            format=OutputFormat.JSON,
            organization=OrganizationType.FLAT,
            include_content=True,
            max_content_length=10,
        )
        json_output = formatter.to_json(organized, config)

        data = json.loads(json_output)
        for page in data["pages"]:
            if page.get("content"):
                assert len(page["content"]) <= 10


class TestDirectoryExporter:
    """Tests for the DirectoryExporter service."""

    @pytest.fixture
    def sample_organized_output(self):
        """Create a sample organized output for testing."""
        pages = [
            EnhancedPageResult(
                metadata=PageMetadata(
                    url="https://www.gmu.edu/",
                    subdomain="www",
                    depth=1,
                    content_type=ContentType.OTHER,
                    title="Home",
                    links_found=50,
                    timing_ms=100.0,
                    word_count=100,
                ),
                headings=["Welcome"],
                content="Welcome to GMU",
            ),
            EnhancedPageResult(
                metadata=PageMetadata(
                    url="https://www.gmu.edu/academics/",
                    subdomain="www",
                    depth=2,
                    content_type=ContentType.ACADEMIC,
                    title="Academics",
                    parent_url="https://www.gmu.edu/",
                    links_found=30,
                    timing_ms=80.0,
                    word_count=200,
                ),
                headings=["Programs"],
                content="Academic programs",
            ),
        ]

        return OrganizedOutput(
            metadata=CrawlMetadata(
                job_id="test123",
                seed_url="https://www.gmu.edu/",
                mode="crawl_scrape",
                max_depth=3,
                worker_count=4,
                state="completed",
                total_urls_discovered=2,
                total_pages_scraped=2,
            ),
            timing=TimingBreakdown(
                total_ms=500.0,
                crawling_ms=300.0,
                scraping_ms=100.0,
            ),
            summary={
                "total_pages": 2,
                "successful_pages": 2,
                "failed_pages": 0,
                "total_word_count": 300,
                "subdomain_count": 1,
                "max_depth_reached": 2,
                "content_type_distribution": {"other": 1, "academic": 1},
                "subdomain_distribution": {"www": 2},
            },
            by_subdomain=[
                SubdomainGroup(
                    subdomain="www",
                    page_count=2,
                    total_word_count=300,
                    content_types={"other": 1, "academic": 1},
                    depth_distribution={1: 1, 2: 1},
                    pages=pages,
                ),
            ],
            by_depth=[
                DepthGroup(
                    depth=1,
                    page_count=1,
                    subdomains=["www"],
                    content_types={"other": 1},
                    pages=[pages[0]],
                ),
                DepthGroup(
                    depth=2,
                    page_count=1,
                    subdomains=["www"],
                    content_types={"academic": 1},
                    pages=[pages[1]],
                ),
            ],
            by_content_type=[
                ContentTypeGroup(
                    content_type=ContentType.OTHER,
                    page_count=1,
                    subdomains=["www"],
                    depth_distribution={1: 1},
                    pages=[pages[0]],
                ),
                ContentTypeGroup(
                    content_type=ContentType.ACADEMIC,
                    page_count=1,
                    subdomains=["www"],
                    depth_distribution={2: 1},
                    pages=[pages[1]],
                ),
            ],
            all_pages=pages,
        )

    def test_export_to_zip(self, sample_organized_output):
        """Test ZIP export generation."""
        exporter = DirectoryExporter()
        config = OutputConfig()

        zip_bytes = exporter.export_to_zip(sample_organized_output, config)

        # Should return non-empty bytes
        assert len(zip_bytes) > 0

        # Should be valid ZIP
        import zipfile
        import io
        buffer = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(buffer, 'r') as zf:
            names = zf.namelist()

            # Check expected files exist
            assert "metadata.json" in names
            assert "timing.json" in names
            assert "summary.md" in names
            assert "index.md" in names
            assert "all_pages.json" in names

            # Check subdomain directory
            assert any("by_subdomain/" in n for n in names)
            assert any("by_depth/" in n for n in names)
            assert any("by_content_type/" in n for n in names)

    def test_zip_contains_valid_json(self, sample_organized_output):
        """Test that ZIP contains valid JSON files."""
        exporter = DirectoryExporter()
        config = OutputConfig()

        zip_bytes = exporter.export_to_zip(sample_organized_output, config)

        import zipfile
        import io
        buffer = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(buffer, 'r') as zf:
            # Check metadata.json is valid
            metadata_content = zf.read("metadata.json").decode('utf-8')
            metadata = json.loads(metadata_content)
            assert metadata["job_id"] == "test123"

            # Check all_pages.json is valid
            pages_content = zf.read("all_pages.json").decode('utf-8')
            pages = json.loads(pages_content)
            assert len(pages) == 2

    def test_safe_filename(self):
        """Test safe filename conversion."""
        exporter = DirectoryExporter()

        assert exporter._safe_filename("www") == "www"
        assert exporter._safe_filename("sub/domain") == "sub_domain"
        assert exporter._safe_filename("test:name") == "test_name"
        assert exporter._safe_filename("") == "unknown"


class TestOutputModels:
    """Tests for output data models."""

    def test_content_type_enum(self):
        """Test ContentType enum values."""
        assert ContentType.ACADEMIC.value == "academic"
        assert ContentType.FACULTY.value == "faculty"
        assert ContentType.RESEARCH.value == "research"

    def test_output_format_enum(self):
        """Test OutputFormat enum values."""
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.MARKDOWN.value == "markdown"
        assert OutputFormat.CSV.value == "csv"

    def test_organization_type_enum(self):
        """Test OrganizationType enum values."""
        assert OrganizationType.BY_SUBDOMAIN.value == "by_subdomain"
        assert OrganizationType.BY_DEPTH.value == "by_depth"
        assert OrganizationType.BY_CONTENT_TYPE.value == "by_content_type"
        assert OrganizationType.FLAT.value == "flat"

    def test_output_config_defaults(self):
        """Test OutputConfig default values."""
        config = OutputConfig()

        assert config.format == OutputFormat.MARKDOWN
        assert config.organization == OrganizationType.FLAT
        assert config.include_metadata is True
        assert config.include_content is True
        assert config.max_content_length == 5000

    def test_page_metadata_creation(self):
        """Test PageMetadata model creation."""
        metadata = PageMetadata(
            url="https://gmu.edu/test",
            subdomain="www",
            depth=2,
            content_type=ContentType.ACADEMIC,
            title="Test Page",
            word_count=100,
        )

        assert metadata.url == "https://gmu.edu/test"
        assert metadata.subdomain == "www"
        assert metadata.depth == 2
        assert metadata.content_type == ContentType.ACADEMIC

    def test_enhanced_page_result(self):
        """Test EnhancedPageResult model creation."""
        metadata = PageMetadata(
            url="https://gmu.edu/test",
            subdomain="www",
            depth=1,
        )
        page = EnhancedPageResult(
            metadata=metadata,
            headings=["Heading 1", "Heading 2"],
            content="Test content here",
        )

        assert page.metadata.url == "https://gmu.edu/test"
        assert len(page.headings) == 2
        assert page.content == "Test content here"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
