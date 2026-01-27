"""
Path scope filter for Knowledge Base URL boundary enforcement.

This module provides path-based URL filtering for KB-scoped crawling,
ensuring that crawled URLs stay within the defined path prefixes.
"""

from urllib.parse import urlparse, urljoin
from typing import Optional, Tuple
from dataclasses import dataclass, field

from ..utils.logger import get_crawler_logger

logger = get_crawler_logger()


@dataclass
class ScopeFilterStats:
    """Statistics for scope filtering operations."""
    urls_checked: int = 0
    urls_allowed: int = 0
    urls_rejected_domain: int = 0
    urls_rejected_path: int = 0
    urls_rejected_scheme: int = 0
    urls_rejected_malformed: int = 0

    @property
    def total_rejected(self) -> int:
        return (
            self.urls_rejected_domain +
            self.urls_rejected_path +
            self.urls_rejected_scheme +
            self.urls_rejected_malformed
        )

    @property
    def rejection_rate(self) -> float:
        if self.urls_checked == 0:
            return 0.0
        return self.total_rejected / self.urls_checked

    def to_dict(self) -> dict:
        return {
            "urls_checked": self.urls_checked,
            "urls_allowed": self.urls_allowed,
            "urls_rejected_domain": self.urls_rejected_domain,
            "urls_rejected_path": self.urls_rejected_path,
            "urls_rejected_scheme": self.urls_rejected_scheme,
            "urls_rejected_malformed": self.urls_rejected_malformed,
            "total_rejected": self.total_rejected,
            "rejection_rate": round(self.rejection_rate, 4),
        }


class PathScopeFilter:
    """
    Enforces URL scope boundaries for a Knowledge Base.

    Unlike DomainFilter (which only checks domain/subdomain),
    this checks if a URL's path falls under allowed prefixes.

    Example:
        filter = PathScopeFilter(
            kb_id="kb_admissions",
            kb_name="Admissions",
            base_domain="gmu.edu",
            allowed_prefixes=["/admissions-aid"],
        )

        filter.is_in_scope("https://gmu.edu/admissions-aid/apply")  # True
        filter.is_in_scope("https://gmu.edu/academics")  # False
    """

    def __init__(
        self,
        kb_id: str,
        kb_name: str,
        base_domain: str,
        allowed_prefixes: list[str],
        allow_subdomains: bool = False,
    ):
        """
        Initialize path scope filter.

        Args:
            kb_id: Knowledge Base identifier
            kb_name: Knowledge Base name (for logging)
            base_domain: Base domain for URL validation
            allowed_prefixes: List of path prefixes to allow
            allow_subdomains: Whether to allow subdomains of base_domain
        """
        self.kb_id = kb_id
        self.kb_name = kb_name
        self.base_domain = self._normalize_domain(base_domain)
        self.allowed_prefixes = self._normalize_prefixes(allowed_prefixes)
        self.allow_subdomains = allow_subdomains

        # Statistics tracking
        self.stats = ScopeFilterStats()

        logger.debug(
            f"[PathScopeFilter] Initialized for KB '{kb_name}': "
            f"domain={self.base_domain}, prefixes={self.allowed_prefixes}, "
            f"allow_subdomains={allow_subdomains}"
        )

    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain by removing www. prefix and lowercasing."""
        # Handle full URL input
        if '://' in domain:
            parsed = urlparse(domain)
            domain = parsed.netloc

        domain = domain.lower().strip()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain

    def _normalize_prefixes(self, prefixes: list[str]) -> list[str]:
        """Ensure prefixes are normalized for consistent matching."""
        normalized = []
        for prefix in prefixes:
            # Ensure leading slash
            if not prefix.startswith('/'):
                prefix = '/' + prefix
            # Remove trailing slash for consistent matching
            prefix = prefix.rstrip('/')
            # Handle root path special case
            if not prefix:
                prefix = '/'
            # Lowercase for case-insensitive matching
            normalized_prefix = prefix.lower()
            if normalized_prefix not in normalized:
                normalized.append(normalized_prefix)
        return normalized

    def _get_root_domain(self, domain: str) -> str:
        """Extract root domain for subdomain matching."""
        parts = domain.split('.')
        if len(parts) <= 2:
            return domain
        # Simple heuristic: take last 2 parts
        return '.'.join(parts[-2:])

    def _is_subdomain_of(self, domain: str, root_domain: str) -> bool:
        """Check if domain is a subdomain of root_domain."""
        if domain == root_domain:
            return True
        if domain.endswith('.' + root_domain):
            return True
        return False

    def is_in_scope(
        self,
        url: str,
        parent_url: Optional[str] = None
    ) -> Tuple[bool, Optional[str], str]:
        """
        Check if URL is within the Knowledge Base scope.

        Args:
            url: URL to check (can be relative if parent_url provided)
            parent_url: Parent URL for resolving relative URLs

        Returns:
            Tuple of (is_allowed, matched_prefix, rejection_reason)
            - is_allowed: True if URL is in scope
            - matched_prefix: The prefix that matched (or None)
            - rejection_reason: Reason for rejection (empty if allowed)
        """
        self.stats.urls_checked += 1

        try:
            # Handle relative URLs
            if parent_url and not url.startswith(('http://', 'https://', '//')):
                url = urljoin(parent_url, url)

            # Handle protocol-relative URLs
            if url.startswith('//'):
                url = 'https:' + url

            parsed = urlparse(url)

            # Check 1: Valid scheme
            if parsed.scheme not in ('http', 'https'):
                self.stats.urls_rejected_scheme += 1
                return (False, None, f"invalid_scheme:{parsed.scheme}")

            # Check 2: Valid netloc
            if not parsed.netloc:
                self.stats.urls_rejected_malformed += 1
                return (False, None, "missing_domain")

            # Check 3: Domain match
            url_domain = parsed.netloc.lower()
            if url_domain.startswith('www.'):
                url_domain = url_domain[4:]

            domain_match = False
            if url_domain == self.base_domain:
                domain_match = True
            elif self.allow_subdomains:
                root_domain = self._get_root_domain(self.base_domain)
                if self._is_subdomain_of(url_domain, root_domain):
                    domain_match = True

            if not domain_match:
                self.stats.urls_rejected_domain += 1
                return (False, None, f"domain_mismatch:{url_domain}")

            # Check 4: Path prefix match
            url_path = parsed.path.lower().rstrip('/') or '/'

            for prefix in self.allowed_prefixes:
                if prefix == '/':
                    # Root prefix allows everything on this domain
                    self.stats.urls_allowed += 1
                    return (True, '/', "")

                # Check if URL path starts with prefix
                # /admissions-aid should match /admissions-aid/apply
                # But NOT /admissions-aidxyz (must match at path boundary)
                if url_path == prefix or url_path.startswith(prefix + '/'):
                    self.stats.urls_allowed += 1
                    return (True, prefix, "")

            # No prefix matched
            self.stats.urls_rejected_path += 1
            return (False, None, f"path_out_of_scope:{parsed.path}")

        except Exception as e:
            self.stats.urls_rejected_malformed += 1
            logger.warning(f"[PathScopeFilter] Error checking scope for '{url}': {e}")
            return (False, None, f"parse_error:{str(e)}")

    def normalize_url(
        self,
        url: str,
        parent_url: Optional[str] = None
    ) -> Optional[str]:
        """
        Normalize URL and return it only if in scope.

        Args:
            url: URL to normalize (may be relative)
            parent_url: Parent URL for resolving relative URLs

        Returns:
            Normalized URL if in scope, None otherwise
        """
        is_allowed, _, _ = self.is_in_scope(url, parent_url)
        if not is_allowed:
            return None

        try:
            # Handle relative URLs
            if parent_url and not url.startswith(('http://', 'https://', '//')):
                url = urljoin(parent_url, url)

            # Handle protocol-relative URLs
            if url.startswith('//'):
                url = 'https:' + url

            parsed = urlparse(url)

            # Build clean URL (remove fragment, preserve query)
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                normalized += f"?{parsed.query}"

            return normalized.rstrip('/')

        except Exception as e:
            logger.warning(f"[PathScopeFilter] Error normalizing URL '{url}': {e}")
            return None

    def get_matched_prefix(self, url: str) -> Optional[str]:
        """
        Get the matching prefix for a URL without updating stats.

        Args:
            url: URL to check

        Returns:
            Matching prefix or None
        """
        try:
            parsed = urlparse(url)
            url_path = parsed.path.lower().rstrip('/') or '/'

            for prefix in self.allowed_prefixes:
                if prefix == '/':
                    return '/'
                if url_path == prefix or url_path.startswith(prefix + '/'):
                    return prefix

            return None
        except Exception:
            return None

    def get_stats(self) -> dict:
        """Return filtering statistics as dictionary."""
        return {
            "kb_id": self.kb_id,
            "kb_name": self.kb_name,
            "base_domain": self.base_domain,
            "allowed_prefixes": self.allowed_prefixes,
            "allow_subdomains": self.allow_subdomains,
            **self.stats.to_dict(),
        }

    def reset_stats(self) -> None:
        """Reset filtering statistics."""
        self.stats = ScopeFilterStats()

    def add_prefix(self, prefix: str) -> bool:
        """
        Add a new path prefix to allowed prefixes.

        Args:
            prefix: Path prefix to add (e.g., '/admission')

        Returns:
            True if prefix was added, False if already exists
        """
        normalized = self._normalize_prefixes([prefix])
        if normalized and normalized[0] not in self.allowed_prefixes:
            self.allowed_prefixes.append(normalized[0])
            logger.info(
                f"[PathScopeFilter] Added prefix '{normalized[0]}' to KB '{self.kb_name}'"
            )
            return True
        return False

    def discover_prefixes_from_urls(
        self,
        urls: list[str],
        base_domain: str,
        min_depth: int = 1
    ) -> list[str]:
        """
        Discover unique path prefixes from a list of URLs.

        Args:
            urls: List of URLs to analyze
            base_domain: Base domain to match against
            min_depth: Minimum path depth to consider (1 = top-level like /admissions)

        Returns:
            List of newly discovered prefixes (not already in allowed_prefixes)
        """
        discovered = []
        normalized_base = self._normalize_domain(base_domain)

        for url in urls:
            try:
                parsed = urlparse(url)

                # Check domain matches
                url_domain = parsed.netloc.lower()
                if url_domain.startswith('www.'):
                    url_domain = url_domain[4:]

                domain_match = url_domain == normalized_base
                if not domain_match and self.allow_subdomains:
                    root_domain = self._get_root_domain(normalized_base)
                    domain_match = self._is_subdomain_of(url_domain, root_domain)

                if not domain_match:
                    continue

                # Extract prefix (first path segment)
                path = parsed.path.lower().strip('/')
                if not path:
                    continue

                segments = path.split('/')
                if len(segments) >= min_depth:
                    # Use first segment as prefix
                    prefix = '/' + segments[0]
                    if prefix not in self.allowed_prefixes and prefix not in discovered:
                        discovered.append(prefix)
                        logger.debug(
                            f"[PathScopeFilter] Discovered prefix '{prefix}' from URL: {url}"
                        )

            except Exception as e:
                logger.warning(f"[PathScopeFilter] Error parsing URL '{url}': {e}")
                continue

        return discovered


class RedirectScopeHandler:
    """
    Handle redirects that may escape KB scope.

    Tracks redirect chains and validates final destinations.
    """

    def __init__(
        self,
        scope_filter: PathScopeFilter,
        max_redirects: int = 5
    ):
        """
        Initialize redirect handler.

        Args:
            scope_filter: PathScopeFilter for scope validation
            max_redirects: Maximum redirects to follow
        """
        self.scope_filter = scope_filter
        self.max_redirects = max_redirects
        self._redirect_chains: dict[str, list[str]] = {}

    def validate_redirect(
        self,
        original_url: str,
        redirect_url: str,
        redirect_count: int = 0
    ) -> Tuple[bool, str, str]:
        """
        Validate a redirect and check if destination is in scope.

        Args:
            original_url: Original URL before redirect
            redirect_url: Redirect destination URL
            redirect_count: Current redirect count

        Returns:
            Tuple of (is_valid, final_url, reason)
        """
        # Check redirect limit
        if redirect_count >= self.max_redirects:
            return (False, redirect_url, "max_redirects_exceeded")

        # Check for circular redirect
        chain = self._redirect_chains.get(original_url, [original_url])
        if redirect_url in chain:
            return (False, redirect_url, "circular_redirect")

        # Check if redirect target is in scope
        is_in_scope, prefix, reason = self.scope_filter.is_in_scope(redirect_url)

        if not is_in_scope:
            return (False, redirect_url, f"redirect_out_of_scope:{reason}")

        # Record redirect in chain
        chain.append(redirect_url)
        self._redirect_chains[redirect_url] = chain

        return (True, redirect_url, "")

    def clear_chains(self) -> None:
        """Clear tracked redirect chains."""
        self._redirect_chains.clear()


class OverlapDetector:
    """
    Detect and analyze overlapping KB scopes.

    Useful for warning users about potential duplicate crawling.
    """

    @staticmethod
    def detect_overlaps(
        kb_configs: list
    ) -> list[Tuple[str, str, str]]:
        """
        Detect overlapping path prefixes between KBs.

        Args:
            kb_configs: List of KnowledgeBaseConfig objects

        Returns:
            List of (kb1_id, kb2_id, overlap_description) tuples
        """
        overlaps = []
        prefixes_by_kb = {}

        for kb in kb_configs:
            prefixes_by_kb[kb.kb_id] = {
                "name": kb.name,
                "prefixes": kb.get_allowed_path_prefixes()
            }

        kb_ids = list(prefixes_by_kb.keys())

        for i, kb1_id in enumerate(kb_ids):
            kb1_data = prefixes_by_kb[kb1_id]
            for kb2_id in kb_ids[i + 1:]:
                kb2_data = prefixes_by_kb[kb2_id]

                for p1 in kb1_data["prefixes"]:
                    for p2 in kb2_data["prefixes"]:
                        # Check if one prefix contains the other
                        if p1 == p2:
                            overlaps.append((
                                kb1_id,
                                kb2_id,
                                f"identical:{p1}"
                            ))
                        elif p1.startswith(p2 + '/'):
                            overlaps.append((
                                kb1_id,
                                kb2_id,
                                f"nested:{p1} under {p2}"
                            ))
                        elif p2.startswith(p1 + '/'):
                            overlaps.append((
                                kb1_id,
                                kb2_id,
                                f"nested:{p2} under {p1}"
                            ))

        return overlaps

    @staticmethod
    def get_dedup_strategy(overlaps: list) -> str:
        """
        Suggest deduplication strategy based on detected overlaps.

        Args:
            overlaps: List of detected overlaps

        Returns:
            Strategy name: "none", "assign_to_most_specific", "warn_only"
        """
        if not overlaps:
            return "none"

        # Check if any are identical (same prefix)
        has_identical = any("identical:" in o[2] for o in overlaps)
        if has_identical:
            return "warn_and_merge"

        # Nested overlaps can use most-specific assignment
        return "assign_to_most_specific"
