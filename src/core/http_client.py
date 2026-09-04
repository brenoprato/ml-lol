"""Resilient HTTP client wrapper for Riot Games API with retries and rate limit management."""

import random
import time
from typing import Any, Mapping, Optional
import httpx
from loguru import logger

from src.core.exceptions import (
    AuthenticationException,
    RateLimitException,
    ResourceNotFoundException,
    RiotAPIException,
)
from src.core.rate_limiter import SlidingWindowRateLimiter


class ResilientHTTPClient:
    """Thread-safe HTTP client with proactive rate limiting, retries, and backoff."""

    def __init__(
        self,
        api_key: str,
        rate_limiter: Optional[SlidingWindowRateLimiter] = None,
        max_retries: int = 4,
        timeout: float = 20.0,
    ) -> None:
        self._api_key = api_key
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter()
        self.max_retries = max_retries
        self._client = httpx.Client(
            headers={
                "X-Riot-Token": self._api_key,
                "Accept": "application/json",
                "User-Agent": "ml-lol-crawler/1.0",
            },
            timeout=httpx.Timeout(timeout, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        )

    def get(
        self,
        url: str,
        params: Optional[Mapping[str, Any]] = None,
    ) -> httpx.Response:
        """Execute a GET request with proactive rate-limiting and resilient retries."""
        for attempt in range(1, self.max_retries + 1):
            self.rate_limiter.acquire()

            try:
                response = self._client.get(url, params=params)

                # Sync headers if available
                self.rate_limiter.sync_headers(response.headers)

                if response.status_code == 200:
                    return response

                if response.status_code in (401, 403):
                    logger.error(f"Authentication failed ({response.status_code}) for URL: {url}")
                    raise AuthenticationException(
                        f"Riot API Key is invalid or expired (HTTP {response.status_code}). "
                        "Please update RIOT_API_KEY in .env."
                    )

                if response.status_code == 404:
                    logger.debug(f"Resource not found (404): {url}")
                    raise ResourceNotFoundException(f"Resource at {url} was not found.")

                if response.status_code == 429:
                    retry_header = response.headers.get("Retry-After")
                    retry_after = float(retry_header) if retry_header else 5.0
                    logger.warning(
                        f"HTTP 429 encountered (attempt {attempt}/{self.max_retries}). "
                        f"Retry-After: {retry_after}s"
                    )
                    self.rate_limiter.handle_retry_after(retry_after)
                    continue

                if 500 <= response.status_code < 600:
                    backoff = (2**attempt) + random.uniform(0.1, 0.5)
                    logger.warning(
                        f"Server error {response.status_code} on {url} (attempt {attempt}/{self.max_retries}). "
                        f"Retrying in {backoff:.2f}s..."
                    )
                    time.sleep(backoff)
                    continue

                # Other HTTP errors
                raise RiotAPIException(
                    message=f"Riot API returned error: {response.text}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            except (httpx.TransportError, httpx.TimeoutException) as network_err:
                backoff = (2**attempt) + random.uniform(0.2, 0.8)
                logger.warning(
                    f"Network transport error on {url}: {network_err} "
                    f"(attempt {attempt}/{self.max_retries}). Retrying in {backoff:.2f}s..."
                )
                time.sleep(backoff)

        raise RateLimitException(
            f"Failed to fetch {url} after {self.max_retries} attempts due to rate limiting or server errors."
        )

    def close(self) -> None:
        """Close the underlying HTTP client session."""
        self._client.close()

    def __enter__(self) -> "ResilientHTTPClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return "<ResilientHTTPClient: [API_KEY_REDACTED]>"
