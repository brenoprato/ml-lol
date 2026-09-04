"""Integration tests for the complete crawling pipeline."""

import pytest
import respx
import httpx
from src.config.settings import Settings
from src.pipeline.orchestrator import MatchPipelineOrchestrator


@respx.mock
def test_full_crawler_pipeline_execution(tmp_path, sample_match_payload) -> None:
    settings = Settings(
        RIOT_API_KEY="RGAPI-mock-key-12345",
        DEFAULT_PLATFORM="BR1",
        DEFAULT_REGION="americas",
        TARGET_QUEUE_ID=420,
        DATA_DIR=tmp_path / "data",
        BATCH_SIZE=2,
    )

    # Mock League-v4 Challenger, Grandmaster, Master
    respx.get("https://br1.api.riotgames.com/lol/league/v4/challengerleagues/by-queue/RANKED_SOLO_5x5").respond(
        status_code=200,
        json={
            "tier": "CHALLENGER",
            "entries": [
                {"puuid": "puuid-seed-1", "summonerId": "sum1", "leaguePoints": 800},
            ],
        },
    )
    respx.get("https://br1.api.riotgames.com/lol/league/v4/grandmasterleagues/by-queue/RANKED_SOLO_5x5").respond(
        status_code=200,
        json={
            "tier": "GRANDMASTER",
            "entries": [
                {"puuid": "puuid-seed-2", "summonerId": "sum2", "leaguePoints": 600},
            ],
        },
    )
    respx.get("https://br1.api.riotgames.com/lol/league/v4/masterleagues/by-queue/RANKED_SOLO_5x5").respond(
        status_code=200,
        json={
            "tier": "MASTER",
            "entries": [],
        },
    )

    # Mock Match-v5 match list for puuid-seed-1
    respx.get("https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/puuid-seed-1/ids").respond(
        status_code=200,
        json=["BR1_1111111111", "BR1_2222222222"],
    )

    # Mock Match-v5 match details
    m1_payload = dict(sample_match_payload)
    m1_payload["metadata"]["matchId"] = "BR1_1111111111"
    respx.get("https://americas.api.riotgames.com/lol/match/v5/matches/BR1_1111111111").respond(
        status_code=200,
        json=m1_payload,
    )

    m2_payload = dict(sample_match_payload)
    m2_payload["metadata"]["matchId"] = "BR1_2222222222"
    respx.get("https://americas.api.riotgames.com/lol/match/v5/matches/BR1_2222222222").respond(
        status_code=200,
        json=m2_payload,
    )

    orchestrator = MatchPipelineOrchestrator(
        settings=settings,
        platform="BR1",
        region="americas",
        queue_id=420,
        output_format="both",
    )

    # Run crawler for target of 2 matches
    orchestrator.run(target_matches=2)

    # Assert results
    assert orchestrator.state_manager.is_match_processed("BR1_1111111111")
    assert orchestrator.state_manager.is_match_processed("BR1_2222222222")
    assert orchestrator.storage.parquet_path.exists()
    assert orchestrator.storage.csv_path.exists()
    assert orchestrator.storage.total_rows == 20
