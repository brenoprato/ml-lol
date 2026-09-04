"""Dual-window sliding log rate limiter with reactive header synchronization."""

from collections import deque
import random
import threading
import time
from typing import Mapping, Optional
from loguru import logger


class SlidingWindowRateLimiter:
    """Thread-safe proactive sliding window rate limiter designed for Riot API limits.

    Manages two concurrent windows:
    1. Short window (default: 20 requests / 1 second)
    2. Long window (default: 100 requests / 120 seconds)
    """

    def __init__(
        self,
        short_limit: int = 18,
        short_window_sec: float = 1.0,
        long_limit: int = 95,
        long_window_sec: float = 120.0,
        safety_margin: float = 0.9,
    ) -> None:
        # Apply safety margin to prevent hitting strict border limits
        self.short_limit = max(1, int(short_limit * safety_margin))
        self.short_window_sec = short_window_sec
        self.long_limit = max(1, int(long_limit * safety_margin))
        self.long_window_sec = long_window_sec

        self._short_timestamps: deque[float] = deque()
        self._long_timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """Block until a request token is available in both sliding windows.

        Returns:
            The total sleep time in seconds (0.0 if token was available immediately).
        """
        total_slept = 0.0

        while True:
            with self._lock:
                now = time.monotonic()

                # 1. Prune timestamps outside windows
                while (
                    self._short_timestamps
                    and (now - self._short_timestamps[0]) >= self.short_window_sec
                ):
                    self._short_timestamps.popleft()

                while (
                    self._long_timestamps
                    and (now - self._long_timestamps[0]) >= self.long_window_sec
                ):
                    self._long_timestamps.popleft()

                # 2. Check limits
                short_wait = 0.0
                if len(self._short_timestamps) >= self.short_limit:
                    short_wait = (
                        self.short_window_sec - (now - self._short_timestamps[0]) + 0.01
                    )

                long_wait = 0.0
                if len(self._long_timestamps) >= self.long_limit:
                    long_wait = (
                        self.long_window_sec - (now - self._long_timestamps[0]) + 0.05
                    )

                wait_time = max(short_wait, long_wait)

                if wait_time <= 0:
                    # Token available!
                    current_time = time.monotonic()
                    self._short_timestamps.append(current_time)
                    self._long_timestamps.append(current_time)
                    return total_slept

            # Outside lock: sleep then retry
            logger.debug(
                f"Rate limit throttle: waiting {wait_time:.2f}s "
                f"(Short: {len(self._short_timestamps)}/{self.short_limit}, "
                f"Long: {len(self._long_timestamps)}/{self.long_limit})"
            )
            time.sleep(wait_time)
            total_slept += wait_time

    def sync_headers(self, headers: Mapping[str, str]) -> None:
        """Parse Riot API response headers and reactively adjust if needed."""
        # Riot headers: X-App-Rate-Limit-Count: e.g. "18:1,94:120"
        app_count = headers.get("X-App-Rate-Limit-Count") or headers.get("x-app-rate-limit-count")
        if not app_count:
            return

        try:
            parts = app_count.split(",")
            for part in parts:
                count_str, window_str = part.strip().split(":")
                count = int(count_str)
                window = int(window_str)

                if window <= 1 and count >= self.short_limit:
                    time.sleep(0.1 + random.uniform(0.02, 0.08))
                elif window >= 100 and count >= self.long_limit:
                    logger.warning(
                        f"Approaching long window rate limit: {count}/{self.long_limit}. Adding brief cooling delay."
                    )
                    time.sleep(1.0 + random.uniform(0.1, 0.5))
        except Exception as err:
            logger.trace(f"Could not parse rate limit headers: {err}")

    def handle_retry_after(self, retry_after_sec: Optional[float] = None) -> None:
        """Handle 429 Too Many Requests response with backoff and jitter."""
        wait = (retry_after_sec or 5.0) + random.uniform(0.2, 0.8)
        logger.warning(f"HTTP 429 received! Backing off for {wait:.2f} seconds...")
        time.sleep(wait)
        # Clear timestamps to prevent compounding lag
        with self._lock:
            self._short_timestamps.clear()
