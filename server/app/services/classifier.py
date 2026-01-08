"""
Content classifier for categorizing crawled pages.

Classifies pages into content types based on URL patterns,
page titles, and content keywords.
"""

import re
from typing import Optional
from urllib.parse import urlparse

from ..models.output import ContentType


class ContentClassifier:
    """
    Classifies crawled pages into content categories.

    Uses a combination of URL pattern matching, title analysis,
    and content keyword detection to determine the content type.
    """

    # URL patterns for classification
    URL_PATTERNS = {
        ContentType.ACADEMIC: [
            r'/academics?/',
            r'/programs?/',
            r'/courses?/',
            r'/catalog/',
            r'/curriculum/',
            r'/degrees?/',
            r'/majors?/',
            r'/minors?/',
            r'/graduate/',
            r'/undergraduate/',
            r'/masters?/',
            r'/phd/',
            r'/doctoral/',
            r'/certificates?/',
            r'/syllabus/',
            r'/syllabi/',
            r'/departments?/',
            r'/schools?/',
            r'/colleges?/',
        ],
        ContentType.FACULTY: [
            r'/faculty/',
            r'/professors?/',
            r'/staff/',
            r'/people/',
            r'/directory/',
            r'/team/',
            r'/instructors?/',
            r'/advisors?/',
            r'/bio/',
            r'/profile/',
            r'~[a-z]+',  # Unix-style user directories
        ],
        ContentType.RESEARCH: [
            r'/research/',
            r'/labs?/',
            r'/publications?/',
            r'/projects?/',
            r'/papers?/',
            r'/journals?/',
            r'/grants?/',
            r'/funding/',
            r'/innovation/',
            r'/discovery/',
            r'/centers?/',
            r'/institutes?/',
        ],
        ContentType.ADMINISTRATIVE: [
            r'/admissions?/',
            r'/registrar/',
            r'/financial/',
            r'/tuition/',
            r'/fees/',
            r'/aid/',
            r'/scholarships?/',
            r'/apply/',
            r'/application/',
            r'/enroll/',
            r'/housing/',
            r'/parking/',
            r'/policies?/',
            r'/compliance/',
            r'/hr/',
            r'/human-resources/',
            r'/about/',
            r'/contact/',
            r'/offices?/',
            r'/services/',
        ],
        ContentType.NEWS: [
            r'/news/',
            r'/press/',
            r'/media/',
            r'/announcements?/',
            r'/updates?/',
            r'/stories/',
            r'/articles?/',
            r'/blog/',
            r'/posts?/',
            r'/releases?/',
        ],
        ContentType.EVENTS: [
            r'/events?/',
            r'/calendar/',
            r'/schedule/',
            r'/workshops?/',
            r'/seminars?/',
            r'/conferences?/',
            r'/lectures?/',
            r'/webinars?/',
            r'/meetings?/',
            r'/activities/',
        ],
        ContentType.RESOURCES: [
            r'/resources?/',
            r'/library/',
            r'/libraries/',
            r'/downloads?/',
            r'/tools?/',
            r'/guides?/',
            r'/tutorials?/',
            r'/help/',
            r'/support/',
            r'/faq/',
            r'/documentation/',
            r'/manuals?/',
            r'/handbooks?/',
        ],
    }

    # Title keywords for classification (case-insensitive)
    TITLE_KEYWORDS = {
        ContentType.ACADEMIC: [
            'program', 'course', 'degree', 'major', 'minor', 'curriculum',
            'academic', 'catalog', 'syllabus', 'department', 'school',
            'college', 'graduate', 'undergraduate', 'masters', 'phd',
            'bachelor', 'certificate', 'credits', 'requirements',
        ],
        ContentType.FACULTY: [
            'faculty', 'professor', 'staff', 'directory', 'team',
            'instructor', 'advisor', 'dr.', 'ph.d', 'biography',
            'profile', 'people', 'member',
        ],
        ContentType.RESEARCH: [
            'research', 'lab', 'laboratory', 'publication', 'project',
            'paper', 'journal', 'grant', 'study', 'findings',
            'innovation', 'discovery', 'center', 'institute',
        ],
        ContentType.ADMINISTRATIVE: [
            'admission', 'apply', 'application', 'enroll', 'registrar',
            'financial', 'tuition', 'fee', 'scholarship', 'aid',
            'housing', 'parking', 'policy', 'office', 'service',
            'contact', 'about', 'administration',
        ],
        ContentType.NEWS: [
            'news', 'press', 'announcement', 'update', 'story',
            'article', 'blog', 'post', 'release', 'headline',
            'breaking', 'latest',
        ],
        ContentType.EVENTS: [
            'event', 'calendar', 'schedule', 'workshop', 'seminar',
            'conference', 'lecture', 'webinar', 'meeting', 'activity',
            'upcoming', 'registration',
        ],
        ContentType.RESOURCES: [
            'resource', 'library', 'download', 'tool', 'guide',
            'tutorial', 'help', 'support', 'faq', 'documentation',
            'manual', 'handbook', 'reference',
        ],
    }

    # Content keywords for deeper classification
    CONTENT_KEYWORDS = {
        ContentType.ACADEMIC: [
            'credit hours', 'prerequisite', 'corequisite', 'gpa',
            'graduation', 'enrollment', 'semester', 'quarter',
            'elective', 'core course', 'learning outcomes',
        ],
        ContentType.FACULTY: [
            'office hours', 'research interests', 'publications',
            'education', 'cv', 'curriculum vitae', 'email',
            'phone', 'appointment',
        ],
        ContentType.RESEARCH: [
            'abstract', 'methodology', 'findings', 'hypothesis',
            'experiment', 'data', 'analysis', 'conclusion',
            'peer-reviewed', 'citation',
        ],
    }

    def __init__(self):
        """Initialize the classifier with compiled regex patterns."""
        self._compiled_patterns = {}
        for content_type, patterns in self.URL_PATTERNS.items():
            self._compiled_patterns[content_type] = [
                re.compile(pattern, re.IGNORECASE)
                for pattern in patterns
            ]

    def classify(
        self,
        url: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
    ) -> ContentType:
        """
        Classify a page's content type.

        Uses a weighted scoring system:
        - URL patterns: 3 points
        - Title keywords: 2 points
        - Content keywords: 1 point

        Args:
            url: Page URL
            title: Page title (optional)
            content: Page content (optional)

        Returns:
            Classified ContentType
        """
        scores = {ct: 0 for ct in ContentType}

        # Score based on URL patterns
        url_path = urlparse(url).path.lower()
        for content_type, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(url_path):
                    scores[content_type] += 3
                    break  # Only count one match per type

        # Score based on title keywords
        if title:
            title_lower = title.lower()
            for content_type, keywords in self.TITLE_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in title_lower:
                        scores[content_type] += 2
                        break  # Only count one match per type

        # Score based on content keywords (limited check for performance)
        if content:
            content_lower = content[:2000].lower()  # Check first 2000 chars
            for content_type, keywords in self.CONTENT_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in content_lower:
                        scores[content_type] += 1
                        break  # Only count one match per type

        # Find the highest scoring content type
        max_score = max(scores.values())
        if max_score == 0:
            return ContentType.OTHER

        # Return the first content type with the max score
        for content_type in ContentType:
            if scores[content_type] == max_score:
                return content_type

        return ContentType.OTHER

    def classify_batch(
        self,
        pages: list[dict],
    ) -> dict[str, ContentType]:
        """
        Classify multiple pages.

        Args:
            pages: List of page dictionaries with 'url', 'title', 'content' keys

        Returns:
            Dictionary mapping URL to ContentType
        """
        results = {}
        for page in pages:
            url = page.get('url', '')
            title = page.get('title')
            content = page.get('content')
            results[url] = self.classify(url, title, content)
        return results

    def get_type_description(self, content_type: ContentType) -> str:
        """
        Get a human-readable description of a content type.

        Args:
            content_type: The content type

        Returns:
            Description string
        """
        descriptions = {
            ContentType.ACADEMIC: "Academic programs, courses, and curriculum content",
            ContentType.FACULTY: "Faculty profiles, staff directories, and team information",
            ContentType.RESEARCH: "Research projects, publications, and lab information",
            ContentType.ADMINISTRATIVE: "Administrative services, admissions, and policies",
            ContentType.NEWS: "News articles, press releases, and announcements",
            ContentType.EVENTS: "Events, calendars, and scheduled activities",
            ContentType.RESOURCES: "Resources, libraries, and support documentation",
            ContentType.OTHER: "General content not matching specific categories",
        }
        return descriptions.get(content_type, "Unknown content type")

    @staticmethod
    def extract_subdomain(url: str) -> str:
        """
        Extract the subdomain from a URL.

        Args:
            url: Full URL

        Returns:
            Subdomain string (e.g., 'catalog' from 'catalog.gmu.edu')
        """
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            parts = netloc.split('.')

            # Handle common cases
            if len(parts) <= 2:
                # e.g., gmu.edu -> www (default)
                return 'www'
            elif len(parts) == 3:
                # e.g., catalog.gmu.edu -> catalog
                return parts[0]
            else:
                # e.g., sub.catalog.gmu.edu -> sub.catalog
                return '.'.join(parts[:-2])
        except Exception:
            return 'unknown'


# Global classifier instance
content_classifier = ContentClassifier()
