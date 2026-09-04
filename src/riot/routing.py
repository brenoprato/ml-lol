"""Routing utilities mapping platform IDs to regional routing endpoints for Riot API."""

PLATFORM_TO_REGION_MAP: dict[str, str] = {
    # Americas
    "BR1": "americas",
    "NA1": "americas",
    "LA1": "americas",
    "LA2": "americas",
    "OC1": "americas",
    # Europe
    "EUW1": "europe",
    "EUN1": "europe",
    "TR1": "europe",
    "RU": "europe",
    "ME1": "europe",
    # Asia
    "KR": "asia",
    "JP1": "asia",
    # Southeast Asia
    "SG2": "sea",
    "TW2": "sea",
    "VN2": "sea",
    "PH2": "sea",
    "TH2": "sea",
}


def platform_to_region(platform: str) -> str:
    """Resolve regional host for a given platform ID (e.g. BR1 -> americas)."""
    norm = platform.strip().upper()
    if norm not in PLATFORM_TO_REGION_MAP:
        raise ValueError(
            f"Unsupported platform '{platform}'. "
            f"Supported platforms: {list(PLATFORM_TO_REGION_MAP.keys())}"
        )
    return PLATFORM_TO_REGION_MAP[norm]


def get_platform_base_url(platform: str) -> str:
    """Return platform base URL for League-v4, Summoner-v4, etc."""
    norm = platform.strip().lower()
    return f"https://{norm}.api.riotgames.com"


def get_regional_base_url(region: str) -> str:
    """Return regional base URL for Match-v5, Account-v1, etc."""
    norm = region.strip().lower()
    return f"https://{norm}.api.riotgames.com"
