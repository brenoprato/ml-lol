"""Custom domain exceptions for the ML League of Legends pipeline."""

from typing import Any, Optional


class MLLoLException(Exception):
    """Base exception for all domain errors."""


class AuthenticationException(MLLoLException):
    """Raised when the Riot API key is invalid, missing, or expired (HTTP 401/403)."""


class RateLimitException(MLLoLException):
    """Raised when rate limits are exceeded and retries exhausted."""

    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ResourceNotFoundException(MLLoLException):
    """Raised when a requested resource (e.g. match, summoner) is not found (HTTP 404)."""


class RiotAPIException(MLLoLException):
    """Raised for unexpected HTTP error responses from Riot Games API."""

    def __init__(
        self,
        message: str,
        status_code: int,
        response_body: Optional[Any] = None,
    ) -> None:
        super().__init__(f"[{status_code}] {message}")
        self.status_code = status_code
        self.response_body = response_body


class SchemaValidationException(MLLoLException):
    """Raised when API payload does not match expected schema."""


class StatePersistenceException(MLLoLException):
    """Raised when state serialization or deserialization fails."""
