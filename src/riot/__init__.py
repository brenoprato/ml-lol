"""Riot API domain clients and routing utilities."""

from src.riot.league_api import LeagueAPIClient
from src.riot.match_api import MatchAPIClient
from src.riot.routing import (
    PLATFORM_TO_REGION_MAP,
    get_platform_base_url,
    get_regional_base_url,
    platform_to_region,
)

__all__ = [
    "LeagueAPIClient",
    "MatchAPIClient",
    "PLATFORM_TO_REGION_MAP",
    "get_platform_base_url",
    "get_regional_base_url",
    "platform_to_region",
]
