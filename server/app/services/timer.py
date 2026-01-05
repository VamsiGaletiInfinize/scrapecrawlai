import time
from contextlib import contextmanager
from typing import Generator
from dataclasses import dataclass, field

from ..models.crawl import TimingMetrics


@dataclass
class TimerService:
    """
    High-precision timing service for tracking crawl operations.

    Uses time.perf_counter() for accurate microsecond-level timing.
    All times are stored and reported in milliseconds.
    """

    # Accumulated times in milliseconds
    url_discovery_ms: float = 0.0
    crawling_ms: float = 0.0
    scraping_ms: float = 0.0
    total_ms: float = 0.0

    # Internal tracking
    _total_start: float = field(default=0.0, repr=False)
    _active_timers: dict = field(default_factory=dict, repr=False)

    def start_total(self) -> None:
        """Start the total execution timer."""
        self._total_start = time.perf_counter()

    def stop_total(self) -> float:
        """Stop the total execution timer and return elapsed milliseconds."""
        if self._total_start > 0:
            self.total_ms = (time.perf_counter() - self._total_start) * 1000
        return self.total_ms

    @contextmanager
    def track(self, category: str) -> Generator[None, None, None]:
        """
        Context manager for tracking time in a specific category.

        Usage:
            with timer.track('crawling'):
                await fetch_page(url)

        Args:
            category: One of 'url_discovery', 'crawling', 'scraping'
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._add_time(category, elapsed_ms)

    def _add_time(self, category: str, milliseconds: float) -> None:
        """Add time to a specific category."""
        if category == 'url_discovery':
            self.url_discovery_ms += milliseconds
        elif category == 'crawling':
            self.crawling_ms += milliseconds
        elif category == 'scraping':
            self.scraping_ms += milliseconds

    def start_timer(self, name: str) -> None:
        """Start a named timer for manual tracking."""
        self._active_timers[name] = time.perf_counter()

    def stop_timer(self, name: str, category: str) -> float:
        """
        Stop a named timer and add elapsed time to category.

        Args:
            name: Timer name (must have been started)
            category: Category to add time to

        Returns:
            Elapsed milliseconds
        """
        if name in self._active_timers:
            elapsed_ms = (time.perf_counter() - self._active_timers[name]) * 1000
            del self._active_timers[name]
            self._add_time(category, elapsed_ms)
            return elapsed_ms
        return 0.0

    def record_page_timing(self, timing_ms: float, is_scraping: bool = False) -> None:
        """
        Record timing for a single page operation.

        Args:
            timing_ms: Time spent processing the page
            is_scraping: If True, adds to scraping time, else to crawling
        """
        if is_scraping:
            self.scraping_ms += timing_ms
        else:
            self.crawling_ms += timing_ms

    def to_metrics(self) -> TimingMetrics:
        """Convert to TimingMetrics Pydantic model."""
        return TimingMetrics(
            url_discovery_ms=round(self.url_discovery_ms, 2),
            crawling_ms=round(self.crawling_ms, 2),
            scraping_ms=round(self.scraping_ms, 2),
            total_ms=round(self.total_ms, 2),
        )

    def get_breakdown(self) -> dict:
        """Get timing breakdown as a dictionary."""
        return {
            "url_discovery_ms": round(self.url_discovery_ms, 2),
            "crawling_ms": round(self.crawling_ms, 2),
            "scraping_ms": round(self.scraping_ms, 2),
            "total_ms": round(self.total_ms, 2),
            "overhead_ms": round(
                max(0, self.total_ms - self.url_discovery_ms - self.crawling_ms - self.scraping_ms),
                2
            ),
        }

    def reset(self) -> None:
        """Reset all timers to zero."""
        self.url_discovery_ms = 0.0
        self.crawling_ms = 0.0
        self.scraping_ms = 0.0
        self.total_ms = 0.0
        self._total_start = 0.0
        self._active_timers.clear()


def measure_time(func):
    """
    Decorator to measure function execution time.

    Returns a tuple of (result, elapsed_ms).
    """
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return result, elapsed_ms
    return wrapper


class PageTimer:
    """
    Simple timer for measuring single page processing time.

    Usage:
        timer = PageTimer()
        timer.start()
        # ... process page ...
        elapsed = timer.stop()
    """

    def __init__(self):
        self._start: float = 0.0
        self._elapsed_ms: float = 0.0

    def start(self) -> None:
        """Start the timer."""
        self._start = time.perf_counter()

    def stop(self) -> float:
        """Stop the timer and return elapsed milliseconds."""
        if self._start > 0:
            self._elapsed_ms = (time.perf_counter() - self._start) * 1000
            self._start = 0.0
        return self._elapsed_ms

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed milliseconds (after stop() is called)."""
        return round(self._elapsed_ms, 2)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
