"""Unit tests for Riot API routing and platform mapping."""

import pytest
from src.riot.routing import (
    get_platform_base_url,
    get_regional_base_url,
    platform_to_region,
)


def test_platform_to_region_mappings() -> None:
    assert platform_to_region("BR1") == "americas"
    assert platform_to_region("na1") == "americas"
    assert platform_to_region("EUW1") == "europe"
    assert platform_to_region("kr") == "asia"


def test_invalid_platform_routing() -> None:
    with pytest.raises(ValueError):
        platform_to_region("INVALID_REGION")


def test_base_urls() -> None:
    assert get_platform_base_url("BR1") == "https://br1.api.riotgames.com"
    assert get_regional_base_url("americas") == "https://americas.api.riotgames.com"
