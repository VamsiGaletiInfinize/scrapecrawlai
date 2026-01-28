"""
Custom exceptions for ScrapeCrawlAI.

Provides a hierarchy of exceptions for consistent error handling
throughout the application.
"""

from typing import Optional


class ScrapeCrawlError(Exception):
    """Base exception for all ScrapeCrawlAI errors."""

    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


# Job-related exceptions
class JobError(ScrapeCrawlError):
    """Base exception for job-related errors."""
    pass


class JobNotFoundError(JobError):
    """Raised when a requested job does not exist."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        super().__init__(f"Job {job_id} not found", {"job_id": job_id})


class JobNotCompletedError(JobError):
    """Raised when trying to access results of an incomplete job."""

    def __init__(self, job_id: str, state: str):
        self.job_id = job_id
        self.state = state
        super().__init__(
            f"Job {job_id} is not completed (current state: {state})",
            {"job_id": job_id, "state": state}
        )


class JobFailedError(JobError):
    """Raised when a job has failed."""

    def __init__(self, job_id: str, error: str):
        self.job_id = job_id
        self.error = error
        super().__init__(f"Job {job_id} failed: {error}", {"job_id": job_id, "error": error})


# KB-related exceptions
class KBError(ScrapeCrawlError):
    """Base exception for Knowledge Base errors."""
    pass


class KBNotFoundError(KBError):
    """Raised when a requested KB does not exist."""

    def __init__(self, job_id: str, kb_id: str):
        self.job_id = job_id
        self.kb_id = kb_id
        super().__init__(
            f"KB {kb_id} not found in job {job_id}",
            {"job_id": job_id, "kb_id": kb_id}
        )


class NoActiveKBsError(KBError):
    """Raised when no active KBs are provided for a multi-KB crawl."""

    def __init__(self):
        super().__init__("At least one active Knowledge Base is required")


class DuplicateKBError(KBError):
    """Raised when duplicate KB IDs are detected."""

    def __init__(self, duplicate_ids: list[str]):
        self.duplicate_ids = duplicate_ids
        super().__init__(
            f"Duplicate Knowledge Base IDs detected: {duplicate_ids}",
            {"duplicate_ids": duplicate_ids}
        )


# Crawling exceptions
class CrawlError(ScrapeCrawlError):
    """Base exception for crawling errors."""
    pass


class RobotsBlockedError(CrawlError):
    """Raised when URL is blocked by robots.txt."""

    def __init__(self, url: str):
        self.url = url
        super().__init__(f"Blocked by robots.txt: {url}", {"url": url})


class RateLimitError(CrawlError):
    """Raised when rate limited by server."""

    def __init__(self, url: str, retry_after: Optional[int] = None):
        self.url = url
        self.retry_after = retry_after
        super().__init__(
            f"Rate limited: {url}",
            {"url": url, "retry_after": retry_after}
        )


class ConnectionError(CrawlError):
    """Raised on connection failures."""

    def __init__(self, url: str, reason: str):
        self.url = url
        self.reason = reason
        super().__init__(f"Connection failed for {url}: {reason}", {"url": url, "reason": reason})


# Export exceptions
class ExportError(ScrapeCrawlError):
    """Base exception for export errors."""
    pass


class InvalidFormatError(ExportError):
    """Raised when an invalid export format is requested."""

    def __init__(self, format: str, valid_formats: list[str]):
        self.format = format
        self.valid_formats = valid_formats
        super().__init__(
            f"Invalid format '{format}'. Valid formats: {valid_formats}",
            {"format": format, "valid_formats": valid_formats}
        )


class ResultsNotFoundError(ExportError):
    """Raised when results are not found for export."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        super().__init__(f"Results not found for job {job_id}", {"job_id": job_id})


# Validation exceptions
class ValidationError(ScrapeCrawlError):
    """Raised on input validation failures."""

    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"Validation error for '{field}': {message}", {"field": field})
