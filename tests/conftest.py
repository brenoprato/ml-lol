"""Pytest test fixtures and mock data."""

import pytest
from src.config.settings import Settings


@pytest.fixture
def test_settings(tmp_path) -> Settings:
    """Provide isolated test settings pointing to temporary data directory."""
    return Settings(
        RIOT_API_KEY="RGAPI-mocked-test-key-12345678",
        DEFAULT_PLATFORM="BR1",
        DEFAULT_REGION="americas",
        TARGET_QUEUE_ID=420,
        DATA_DIR=tmp_path / "data",
        BATCH_SIZE=5,
    )


@pytest.fixture
def sample_match_payload() -> dict:
    """Provide a realistic sample match JSON structure."""
    participants = []
    for i in range(10):
        participants.append({
            "puuid": f"puuid-sample-player-{i}",
            "summonerName": f"Player_{i}",
            "participantId": i + 1,
            "teamId": 100 if i < 5 else 200,
            "teamPosition": ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"][i % 5],
            "championId": 100 + i,
            "championName": f"Champion_{i}",
            "champLevel": 16,
            "win": True if i < 5 else False,
            "kills": 5 + i,
            "deaths": 2 + (i % 3),
            "assists": 8,
            "totalDamageDealtToChampions": 25000 + (i * 1000),
            "physicalDamageDealtToChampions": 15000,
            "magicDamageDealtToChampions": 8000,
            "trueDamageDealtToChampions": 2000,
            "totalDamageTaken": 18000,
            "damageSelfMitigated": 12000,
            "timeCCingOthers": 24,
            "totalTimeSpentDead": 60,
            "damageDealtToBuildings": 4500,
            "damageDealtToObjectives": 12000,
            "turretKills": 2,
            "inhibitorKills": 1,
            "firstTowerKill": (i == 0),
            "firstTowerAssist": False,
            "firstBloodKill": (i == 0),
            "firstBloodAssist": False,
            "goldEarned": 14500,
            "goldSpent": 13200,
            "totalMinionsKilled": 210,
            "neutralMinionsKilled": 20,
            "visionScore": 42,
            "wardsPlaced": 15,
            "wardsKilled": 6,
            "visionWardsBoughtInGame": 4,
            "item0": 3078,
            "item1": 3053,
            "item2": 3047,
            "item3": 0,
            "item4": 0,
            "item5": 0,
            "item6": 3340,
            "summoner1Id": 4,
            "summoner2Id": 12,
            "perks": {
                "styles": [
                    {"description": "primaryStyle", "style": 8000, "selections": []},
                    {"description": "subStyle", "style": 8400, "selections": []},
                ]
            },
        })

    return {
        "metadata": {
            "matchId": "BR1_9999999999",
            "participants": [p["puuid"] for p in participants],
        },
        "info": {
            "gameCreation": 1709400000000,
            "gameDuration": 1800,  # 30 minutes
            "gameVersion": "14.4.1.1234",
            "queueId": 420,
            "participants": participants,
            "teams": [{"teamId": 100, "win": True}, {"teamId": 200, "win": False}],
        },
    }
