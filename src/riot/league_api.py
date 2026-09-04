"""Client for Riot Games League-v4 API endpoints to harvest high-tier player seeds."""

from typing import Any, Optional
from loguru import logger

from src.core.http_client import ResilientHTTPClient
from src.riot.routing import get_platform_base_url


class LeagueAPIClient:
    """Provides methods to query apex league tiers (Challenger, Grandmaster, Master) for player seeds."""

    def __init__(self, http_client: ResilientHTTPClient, platform: str = "BR1") -> None:
        self.http_client = http_client
        self.platform = platform.upper()
        self.base_url = get_platform_base_url(self.platform)

    def get_challenger_league(self, queue: str = "RANKED_SOLO_5x5") -> dict[str, Any]:
        """Fetch all entries in the Challenger tier for the specified queue."""
        url = f"{self.base_url}/lol/league/v4/challengerleagues/by-queue/{queue}"
        response = self.http_client.get(url)
        return response.json()

    def get_grandmaster_league(self, queue: str = "RANKED_SOLO_5x5") -> dict[str, Any]:
        """Fetch all entries in the Grandmaster tier for the specified queue."""
        url = f"{self.base_url}/lol/league/v4/grandmasterleagues/by-queue/{queue}"
        response = self.http_client.get(url)
        return response.json()

    def get_master_league(self, queue: str = "RANKED_SOLO_5x5") -> dict[str, Any]:
        """Fetch all entries in the Master tier for the specified queue."""
        url = f"{self.base_url}/lol/league/v4/masterleagues/by-queue/{queue}"
        response = self.http_client.get(url)
        return response.json()

    def harvest_seed_puuids(
        self,
        queue: str = "RANKED_SOLO_5x5",
        include_grandmaster: bool = False,
        include_master: bool = False,
    ) -> list[str]:
        """Harvest unique player PUUIDs from apex ranked tiers.

        Returns:
            List of unique player PUUIDs.
        """
        logger.info(f"Harvesting Challenger seeds from {self.platform} ({queue})...")
        puuids: set[str] = set()

        challenger_data = self.get_challenger_league(queue=queue)
        for entry in challenger_data.get("entries", []):
            puuid = entry.get("puuid")
            if puuid:
                puuids.add(puuid)

        if include_grandmaster:
            logger.info(f"Harvesting Grandmaster seeds from {self.platform} ({queue})...")
            gm_data = self.get_grandmaster_league(queue=queue)
            for entry in gm_data.get("entries", []):
                puuid = entry.get("puuid")
                if puuid:
                    puuids.add(puuid)

        if include_master:
            logger.info(f"Harvesting Master seeds from {self.platform} ({queue})...")
            master_data = self.get_master_league(queue=queue)
            for entry in master_data.get("entries", []):
                puuid = entry.get("puuid")
                if puuid:
                    puuids.add(puuid)

        logger.info(f"Harvested {len(puuids)} unique seed PUUIDs from {self.platform}.")
        return list(puuids)
