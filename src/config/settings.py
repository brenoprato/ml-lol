"""Application configuration and settings management using Pydantic."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    riot_api_key: SecretStr = Field(
        ...,
        alias="RIOT_API_KEY",
        description="Riot Games API key (Development or Production key)",
    )
    default_platform: str = Field(
        default="BR1",
        alias="DEFAULT_PLATFORM",
        description="Default platform routing value (e.g. BR1, NA1, EUW1, KR)",
    )
    default_region: str = Field(
        default="americas",
        alias="DEFAULT_REGION",
        description="Default regional routing value (e.g. americas, europe, asia)",
    )
    target_queue_id: int = Field(
        default=420,
        alias="TARGET_QUEUE_ID",
        description="Target queue ID (420: Ranked Solo/Duo, 440: Ranked Flex)",
    )

    # Rate Limiting Configuration (Defaults to conservative safety margin for Dev keys)
    rate_limit_short_max: int = Field(
        default=18,
        alias="RATE_LIMIT_SHORT_MAX",
        description="Max requests in short sliding window (Riot default: 20 per 1s)",
    )
    rate_limit_short_window_sec: float = Field(
        default=1.0,
        alias="RATE_LIMIT_SHORT_WINDOW_SEC",
        description="Short window size in seconds",
    )
    rate_limit_long_max: int = Field(
        default=95,
        alias="RATE_LIMIT_LONG_MAX",
        description="Max requests in long sliding window (Riot default: 100 per 120s)",
    )
    rate_limit_long_window_sec: float = Field(
        default=120.0,
        alias="RATE_LIMIT_LONG_WINDOW_SEC",
        description="Long window size in seconds",
    )
    rate_limit_safety_margin: float = Field(
        default=0.9,
        alias="RATE_LIMIT_SAFETY_MARGIN",
        description="Multiplier for rate limit thresholds to guarantee safety",
    )

    # Storage and Pipeline
    data_dir: Path = Field(
        default=Path("data"),
        alias="DATA_DIR",
        description="Directory where datasets and state checkpoints are saved",
    )
    output_format: Literal["parquet", "csv", "both"] = Field(
        default="both",
        alias="OUTPUT_FORMAT",
        description="Output dataset file format",
    )
    batch_size: int = Field(
        default=50,
        alias="BATCH_SIZE",
        description="Number of matches per flush to disk",
    )
    max_matches_per_player: int = Field(
        default=10,
        alias="MAX_MATCHES_PER_PLAYER",
        description="Max matches to crawl per player PUUID to ensure diverse sample",
    )

    @field_validator("riot_api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr) -> SecretStr:
        """Validate API key format and non-emptiness."""
        secret_value = value.get_secret_value().strip()
        if not secret_value:
            raise ValueError("RIOT_API_KEY must not be empty.")
        if not secret_value.startswith("RGAPI-"):
            raise ValueError("RIOT_API_KEY must start with 'RGAPI-'.")
        if len(secret_value) < 15:
            raise ValueError("RIOT_API_KEY appears invalid (too short).")
        return value

    @field_validator("default_platform")
    @classmethod
    def normalize_platform(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("default_region")
    @classmethod
    def normalize_region(cls, value: str) -> str:
        return value.strip().lower()


@lru_cache
def get_settings() -> Settings:
    """Retrieve cached instance of application settings."""
    return Settings()
