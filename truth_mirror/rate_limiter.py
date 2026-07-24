"""Adaptive rate limiter for API calls."""

import asyncio
import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class AdaptiveRateLimiter:
    """
    Token-bucket rate limiter that adapts based on whether
    the last API call to a provider was rate-limited or not.
    
    - If the last call succeeded: delay is 0 (no wait).
    - If the last call was rate-limited (429): apply exponential backoff
      starting at base_delay, doubling each consecutive 429, capped at max_delay.
    - Resets backoff on next success.
    """
    
    def __init__(self, base_delay: float = 2.0, max_delay: float = 30.0):
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._consecutive_429: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
    
    def record_success(self, provider: str) -> None:
        """Reset backoff counter for a provider after a successful call."""
        self._consecutive_429[provider] = 0
    
    def record_rate_limit(self, provider: str) -> None:
        """Increment backoff counter for a provider after a 429."""
        self._consecutive_429[provider] += 1
    
    async def wait_if_needed(self, provider: str) -> float:
        """
        Wait adaptively based on recent rate-limit history for this provider.
        Returns the number of seconds actually waited.
        """
        count = self._consecutive_429.get(provider, 0)
        if count == 0:
            return 0.0
        
        delay = min(self._base_delay * (2 ** (count - 1)), self._max_delay)
        logger.info(
            f"[RateLimiter] Waiting {delay:.1f}s for {provider} "
            f"(consecutive 429s: {count})"
        )
        await asyncio.sleep(delay)
        return delay


# Module-level singleton — shared across all pipeline stages within a run.
# Thread-safe because asyncio is single-threaded within an event loop.
rate_limiter = AdaptiveRateLimiter()
