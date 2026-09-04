"""Unit tests for settings and configuration validation."""

import pytest
from pydantic import ValidationError
from src.config.settings import Settings


def test_valid_settings() -> None:
    settings = Settings(
        RIOT_API_KEY="RGAPI-valid-key-abcdef-12345",
        DEFAULT_PLATFORM="br1",
        DEFAULT_REGION="AMERICAS",
    )
    assert settings.riot_api_key.get_secret_value() == "RGAPI-valid-key-abcdef-12345"
    assert settings.default_platform == "BR1"
    assert settings.default_region == "americas"
    # Verify secret is masked in repr
    assert "RGAPI-valid-key" not in repr(settings)


def test_invalid_api_key_format() -> None:
    with pytest.raises(ValidationError):
        Settings(RIOT_API_KEY="INVALID_KEY_WITHOUT_PREFIX")


def test_empty_api_key() -> None:
    with pytest.raises(ValidationError):
        Settings(RIOT_API_KEY="")
