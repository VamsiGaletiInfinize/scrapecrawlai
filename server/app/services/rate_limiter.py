"""
Per-domain rate limiting service.

Ensures polite crawling by limiting request frequency
to each domain, respecting robots.txt crawl-delay directives.
"""

import asyncio
import time
from collections import defaultdict
from urllib.parse import urlparse


class DomainRateLimiter:
    """
    Async rate limiter that enforces per-domain request delays.

    Features:
    - Configurable default delay between requests
    - Per-domain custom delays (from robots.txt)
    - Async-safe with per-domain locks
    """

    def __init__(self, default_delay: float = 0.25):
        """
        Initialize the rate limiter.

        Args:
            default_delay: Default delay between requests in seconds
        """
        self.default_delay = default_delay
        self._last_request: dict[str, float] = defaultdict(float)
        self._locks: dict[str, asyncio.Lock] = {}
        self._custom_delays: dict[str, float] = {}
        self._global_lock = asyncio.Lock()

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        return urlparse(url).netloc

    async def _get_lock(self, domain: str) -> asyncio.Lock:
        """Get or create lock for domain."""
        async with self._global_lock:
            if domain not in self._locks:
                self._locks[domain] = asyncio.Lock()
            return self._locks[domain]

    def set_delay(self, domain: str, delay: float) -> None:
        """
        Set custom delay for a domain.

        Args:
            domain: Domain name (e.g., example.com)
            delay: Delay in seconds
        """
        self._custom_delays[domain] = max(delay, self.default_delay)

    def get_delay(self, domain: str) -> float:
        """Get the delay for a domain."""
        return self._custom_delays.get(domain, self.default_delay)

    async def acquire(self, url: str) -> float:
        """
        Wait until we can make a request to the URL's domain.

        Args:
            url: URL to acquire rate limit for

        Returns:
            Time waited in seconds
        """
        domain = self._get_domain(url)
        lock = await self._get_lock(domain)

        async with lock:
            delay = self._custom_delays.get(domain, self.default_delay)
            elapsed = time.time() - self._last_request[domain]

            wait_time = 0.0
            if elapsed < delay:
                wait_time = delay - elapsed
                await asyncio.sleep(wait_time)

            self._last_request[domain] = time.time()
            return wait_time

    async def acquire_url(self, url: str) -> float:
        """Alias for acquire() for clarity."""
        return await self.acquire(url)

    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        return {
            "domains_tracked": len(self._last_request),
            "custom_delays": dict(self._custom_delays),
            "default_delay": self.default_delay,
        }


class AdaptiveRateLimiter(DomainRateLimiter):
    """
    Adaptive rate limiter that adjusts delays based on server response.

    Increases delay on errors/slow responses, decreases on fast responses.
    """

    def __init__(
        self,
        default_delay: float = 0.25,
        min_delay: float = 0.1,
        max_delay: float = 5.0,
    ):
        super().__init__(default_delay)
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._response_times: dict[str, list[float]] = defaultdict(list)

    def record_response(self, url: str, response_time: float, success: bool) -> None:
        """
        Record a response to adapt rate limiting.

        Args:
            url: URL that was requested
            response_time: Time taken in seconds
            success: Whether request was successful
        """
        domain = self._get_domain(url)

        # Keep last 10 response times
        self._response_times[domain].append(response_time)
        if len(self._response_times[domain]) > 10:
            self._response_times[domain] = self._response_times[domain][-10:]

        # Adjust delay based on response
        current_delay = self._custom_delays.get(domain, self.default_delay)

        if not success:
            # Increase delay on failure (up to max)
            new_delay = min(current_delay * 1.5, self.max_delay)
        elif response_time > 2.0:
            # Increase delay if server is slow
            new_delay = min(current_delay * 1.2, self.max_delay)
        elif response_time < 0.5 and len(self._response_times[domain]) >= 5:
            # Decrease delay if consistently fast
            avg_time = sum(self._response_times[domain]) / len(self._response_times[domain])
            if avg_time < 0.5:
                new_delay = max(current_delay * 0.9, self.min_delay)
            else:
                new_delay = current_delay
        else:
            new_delay = current_delay

        self._custom_delays[domain] = new_delay


# Global instance
rate_limiter = DomainRateLimiter()
