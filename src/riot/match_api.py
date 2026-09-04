"""Client for Riot Games Match-v5 API endpoints."""

from typing import Any, Optional
from loguru import logger

from src.core.http_client import ResilientHTTPClient
from src.riot.routing import get_regional_base_url


class MatchAPIClient:
    """Provides methods to query match lists and full match details via Match-v5."""

    def __init__(self, http_client: ResilientHTTPClient, region: str = "americas") -> None:
        self.http_client = http_client
        self.region = region.lower()
        self.base_url = get_regional_base_url(self.region)

    def get_match_ids_by_puuid(
        self,
        puuid: str,
        queue: Optional[int] = 420,
        count: int = 20,
        start: int = 0,
        match_type: Optional[str] = "ranked",
    ) -> list[str]:
        """Fetch list of match IDs for a given player PUUID.

        Args:
            puuid: Player's encrypted PUUID.
            queue: Filter by queue ID (e.g. 420 for Solo/Duo).
            count: Number of match IDs to return (1-100).
            start: Start index for pagination.
            match_type: Type of match ("ranked", "normal", "tourney", "tutorial").

        Returns:
            List of match ID strings (e.g. ['BR1_2893821019']).
        """
        url = f"{self.base_url}/lol/match/v5/matches/by-puuid/{puuid}/ids"
        params: dict[str, Any] = {
            "start": start,
            "count": min(max(1, count), 100),
        }
        if queue is not None:
            params["queue"] = queue
        if match_type is not None:
            params["type"] = match_type

        response = self.http_client.get(url, params=params)
        match_ids = response.json()
        if not isinstance(match_ids, list):
            logger.warning(f"Unexpected response type for match IDs: {type(match_ids)}")
            return []
        return match_ids

    def get_match_by_id(self, match_id: str) -> dict[str, Any]:
        """Fetch complete match details by match ID.

        Args:
            match_id: Riot Match ID (e.g. 'BR1_2893821019').

        Returns:
            Dictionary containing match metadata, info, participants, and team stats.
        """
        url = f"{self.base_url}/lol/match/v5/matches/{match_id}"
        response = self.http_client.get(url)
        return response.json()
