"""Unit tests for sliding window rate limiter."""

import time
from src.core.rate_limiter import SlidingWindowRateLimiter


def test_rate_limiter_instant_acquire() -> None:
    limiter = SlidingWindowRateLimiter(
        short_limit=5,
        short_window_sec=1.0,
        long_limit=10,
        long_window_sec=5.0,
        safety_margin=1.0,
    )
    # First acquire should not sleep
    slept = limiter.acquire()
    assert slept == 0.0


def test_rate_limiter_short_window_throttling() -> None:
    # 2 requests per 0.2s window
    limiter = SlidingWindowRateLimiter(
        short_limit=2,
        short_window_sec=0.2,
        long_limit=10,
        long_window_sec=5.0,
        safety_margin=1.0,
    )
    limiter.acquire()
    limiter.acquire()

    # 3rd acquire should wait for short window to expire
    start = time.monotonic()
    limiter.acquire()
    elapsed = time.monotonic() - start

    assert elapsed >= 0.15


def test_rate_limiter_handle_429() -> None:
    limiter = SlidingWindowRateLimiter()
    start = time.monotonic()
    limiter.handle_retry_after(0.1)
    elapsed = time.monotonic() - start
    assert elapsed >= 0.1
