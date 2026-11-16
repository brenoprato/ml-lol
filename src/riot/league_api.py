"""Client for Riot Games League-v4 API endpoints to harvest ranked player seeds."""

from typing import Any, Optional
from loguru import logger

from src.core.http_client import ResilientHTTPClient
from src.models.filter_models import APEX_TIERS, STANDARD_TIERS
from src.riot.routing import get_platform_base_url


class LeagueAPIClient:
    """Provides methods to query ranked leagues (Challenger through Iron) for player seeds."""

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

    def get_league_entries(
        self,
        queue: str,
        tier: str,
        division: str = "I",
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """Fetch ranked entries for a standard tier (Diamond through Iron) and division."""
        norm_tier = tier.strip().upper()
        norm_div = division.strip().upper()
        url = f"{self.base_url}/lol/league/v4/entries/{queue}/{norm_tier}/{norm_div}"
        response = self.http_client.get(url, params={"page": page})
        data = response.json()
        if not isinstance(data, list):
            logger.warning(f"Unexpected response type for league entries: {type(data)}")
            return []
        return data

    def harvest_seed_puuids(
        self,
        queue: str = "RANKED_SOLO_5x5",
        include_grandmaster: bool = False,
        include_master: bool = False,
        tiers: Optional[list[str]] = None,
        divisions: Optional[list[str]] = None,
        max_pages_per_division: int = 1,
    ) -> list[str]:
        """Harvest unique player PUUIDs from configured ranked tiers and divisions.

        Returns:
            List of unique player PUUIDs in deterministic discovery order.
        """
        if tiers is None:
            tiers_to_fetch = ["CHALLENGER"]
            if include_grandmaster:
                tiers_to_fetch.append("GRANDMASTER")
            if include_master:
                tiers_to_fetch.append("MASTER")
        else:
            tiers_to_fetch = [t.strip().upper() for t in tiers if t.strip()]

        target_divisions = [d.strip().upper() for d in (divisions or ["I"]) if d.strip()]
        seen_puuids: set[str] = set()
        ordered_puuids: list[str] = []

        def _collect_entries(entries: list[dict[str, Any]]) -> None:
            for entry in entries:
                puuid = entry.get("puuid")
                if puuid and puuid not in seen_puuids:
                    seen_puuids.add(puuid)
                    ordered_puuids.append(puuid)

        apex_fetchers = {
            "CHALLENGER": self.get_challenger_league,
            "GRANDMASTER": self.get_grandmaster_league,
            "MASTER": self.get_master_league,
        }

        for tier in tiers_to_fetch:
            if tier in APEX_TIERS:
                logger.info(f"Harvesting {tier.title()} seeds from {self.platform} ({queue})...")
                league_data = apex_fetchers[tier](queue=queue)
                _collect_entries(league_data.get("entries", []))
            elif tier in STANDARD_TIERS:
                for div in target_divisions:
                    for page in range(1, max_pages_per_division + 1):
                        logger.info(
                            f"Harvesting {tier.title()} {div} (page {page}) seeds from {self.platform} ({queue})..."
                        )
                        entries = self.get_league_entries(
                            queue=queue, tier=tier, division=div, page=page
                        )
                        if not entries:
                            break
                        _collect_entries(entries)
            else:
                raise ValueError(f"Unsupported ranked tier '{tier}'.")

        logger.info(f"Harvested {len(ordered_puuids)} unique seed PUUIDs from {self.platform}.")
        return ordered_puuids
