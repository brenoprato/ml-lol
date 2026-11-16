"""Unit and integration tests for filter models, interactive CLI, standard tiers, and offline filtering."""

from pathlib import Path
import pandas as pd
import pytest
from pydantic import ValidationError
import respx

from src.cli.interactive import prompt_collection_filters
from src.config.settings import Settings
from src.core.http_client import ResilientHTTPClient
from src.main import build_filter_config_from_args, build_parser
from src.models.filter_models import CollectionFilterConfig
from src.pipeline.normalizer import MatchNormalizer
from src.pipeline.orchestrator import run_multi_platform_collection
from src.pipeline.storage import BatchStorage
from src.riot.league_api import LeagueAPIClient
from src.riot.match_api import MatchAPIClient
from tests.test_storage import make_sample_record


def test_collection_filter_config_validation_and_cli_command() -> None:
    cfg = CollectionFilterConfig(
        platforms=["br1", "kr", "BR1"],
        tiers=["challenger", "diamond"],
        divisions=["i", "ii"],
        max_pages_per_division=2,
        queue_id=420,
        min_duration_sec=600,
        max_duration_sec=2400,
        exclude_surrenders=True,
        patch_prefix="14.4",
        champions=["Ahri", "LeeSin"],
        positions=["middle", "jungle"],
        side="blue",
        discover_participants=False,
        target_matches=50,
        max_duration_hours=4.0,
        output_format="parquet",
        dataset_name="custom_run",
    )

    assert cfg.platforms == ["BR1", "KR"]
    assert cfg.tiers == ["CHALLENGER", "DIAMOND"]
    assert cfg.divisions == ["I", "II"]
    assert cfg.positions == ["MIDDLE", "JUNGLE"]
    assert cfg.side == "BLUE"
    assert cfg.has_standard_tiers is True

    cmd = cfg.to_cli_command()
    assert "-p BR1,KR" in cmd
    assert "--tiers CHALLENGER,DIAMOND" in cmd
    assert "--divisions I,II" in cmd
    assert "--max-pages 2" in cmd
    assert "--exclude-surrenders" in cmd
    assert "--patch 14.4" in cmd
    assert "--champions Ahri,LeeSin" in cmd
    assert "--positions MIDDLE,JUNGLE" in cmd
    assert "--side BLUE" in cmd
    assert "--no-discover" in cmd
    assert "--dataset-name custom_run" in cmd

    # Verify parser round-trip compatibility with CLI args
    parser = build_parser()
    raw_args = cmd.replace("python3 src/main.py ", "").split()
    parsed = parser.parse_args(raw_args)
    reconstructed = build_filter_config_from_args(parsed)
    assert reconstructed.platforms == cfg.platforms
    assert reconstructed.tiers == cfg.tiers
    assert reconstructed.divisions == cfg.divisions
    assert reconstructed.exclude_surrenders is True
    assert reconstructed.side == "BLUE"
    assert reconstructed.discover_participants is False


def test_collection_filter_config_invalid_inputs() -> None:
    with pytest.raises(ValidationError):
        CollectionFilterConfig(platforms=["UNKNOWN_SERVER"])

    with pytest.raises(ValidationError):
        CollectionFilterConfig(tiers=["CHALLENGED"])

    with pytest.raises(ValidationError):
        CollectionFilterConfig(min_duration_sec=1000, max_duration_sec=500)

    with pytest.raises(ValidationError):
        CollectionFilterConfig(dataset_name="../escape")


@respx.mock
def test_league_api_harvest_apex_and_standard_tiers() -> None:
    respx.get("https://br1.api.riotgames.com/lol/league/v4/challengerleagues/by-queue/RANKED_SOLO_5x5").respond(
        status_code=200,
        json={"entries": [{"puuid": "p-chall-1"}]},
    )
    respx.get("https://br1.api.riotgames.com/lol/league/v4/entries/RANKED_SOLO_5x5/DIAMOND/I?page=1").respond(
        status_code=200,
        json=[{"puuid": "p-dia-1"}, {"puuid": "p-dia-2"}],
    )
    respx.get("https://br1.api.riotgames.com/lol/league/v4/entries/RANKED_SOLO_5x5/DIAMOND/I?page=2").respond(
        status_code=200,
        json=[],
    )

    with ResilientHTTPClient(api_key="RGAPI-test-key-12345") as http_client:
        league_client = LeagueAPIClient(http_client, platform="BR1")
        puuids = league_client.harvest_seed_puuids(
            queue="RANKED_SOLO_5x5",
            tiers=["CHALLENGER", "DIAMOND"],
            divisions=["I"],
            max_pages_per_division=3,
        )

    assert puuids == ["p-chall-1", "p-dia-1", "p-dia-2"]


@respx.mock
def test_match_api_time_window_params() -> None:
    route = respx.get(
        "https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/puuid-1/ids"
    ).respond(status_code=200, json=["BR1_100"])

    with ResilientHTTPClient(api_key="RGAPI-test-key-12345") as http_client:
        match_client = MatchAPIClient(http_client, region="americas")
        ids = match_client.get_match_ids_by_puuid(
            puuid="puuid-1",
            queue=420,
            count=10,
            start_time=1700000000,
            end_time=1700086400,
        )

    assert ids == ["BR1_100"]
    request = route.calls[0].request
    assert request.url.params["startTime"] == "1700000000"
    assert request.url.params["endTime"] == "1700086400"


def test_normalizer_filters(sample_match_payload: dict) -> None:
    # 1. Max duration filter
    assert MatchNormalizer.normalize_match(sample_match_payload, max_game_duration_sec=1200) == []

    # 2. Exclude surrenders filter
    surrender_payload = dict(sample_match_payload)
    surrender_payload["info"] = dict(sample_match_payload["info"], gameEndedInSurrender=True)
    assert MatchNormalizer.normalize_match(surrender_payload, exclude_surrenders=True) == []

    # 3. Patch prefix filter
    assert MatchNormalizer.normalize_match(sample_match_payload, patch_prefix="14.5") == []
    assert len(MatchNormalizer.normalize_match(sample_match_payload, patch_prefix="14.4")) == 10

    # 4. Champions filter (case-insensitive match-level)
    assert MatchNormalizer.normalize_match(sample_match_payload, champions=["Ahri"]) == []
    assert len(MatchNormalizer.normalize_match(sample_match_payload, champions=["champion_0"])) == 10

    # 5. Positions and side filters
    filtered_top_blue = MatchNormalizer.normalize_match(
        sample_match_payload,
        positions=["TOP"],
        side="BLUE",
    )
    assert len(filtered_top_blue) == 1
    assert filtered_top_blue[0].team_position == "TOP"
    assert filtered_top_blue[0].side == "BLUE"


def test_interactive_wizard_builds_filters_before_api_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulated user responses step by step
    answers = iter([
        "5",              # Step 1: Custom / Multi-region
        "BR1,KR",         # Platforms
        "5",              # Step 2: Custom tiers
        "CHALLENGER,DIAMOND",  # Tiers
        "I,II",           # Divisions
        "2",              # Max pages per division
        "1",              # Step 3: Ranked Solo/Duo (420)
        "7",              # Step 4: Last 7 days
        "14.4",           # Patch prefix
        "600",            # Min duration
        "2400",           # Max duration
        "y",              # Exclude surrenders
        "Ahri,LeeSin",    # Champions
        "TOP,MIDDLE",     # Positions
        "BLUE",           # Map side
        "2",              # Strict seed tiers only (no snowball discovery)
        "4",              # Step 5: 4 hours
        "50",             # Target matches
        "5",              # Max matches per player
        "parquet",        # Output format
        "ic_filtered",    # Dataset filename
        "n",              # Do not reset state
        "y",              # Pre-flight confirmation: Start collection now?
    ])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    config = prompt_collection_filters()
    assert config is not None
    assert config.platforms == ["BR1", "KR"]
    assert config.tiers == ["CHALLENGER", "DIAMOND"]
    assert config.divisions == ["I", "II"]
    assert config.max_pages_per_division == 2
    assert config.queue_id == 420
    assert config.start_time is not None
    assert config.patch_prefix == "14.4"
    assert config.min_duration_sec == 600
    assert config.max_duration_sec == 2400
    assert config.exclude_surrenders is True
    assert config.champions == ["Ahri", "LeeSin"]
    assert config.positions == ["TOP", "MIDDLE"]
    assert config.side == "BLUE"
    assert config.discover_participants is False
    assert config.max_duration_hours == 4.0
    assert config.target_matches == 50
    assert config.max_matches_per_player == 5
    assert config.output_format == "parquet"
    assert config.dataset_name == "ic_filtered"


def test_interactive_wizard_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter([
        "1",   # BR1
        "1",   # Apex tiers
        "1",   # Solo/Duo
        "",    # Days back
        "",    # Patch
        "",    # Min duration
        "",    # Max duration
        "n",   # Exclude surrenders
        "",    # Champions
        "",    # Positions
        "",    # Side
        "1",   # Snowball
        "",    # Hours
        "",    # Target matches
        "",    # Max per player
        "",    # Format
        "",    # Dataset name
        "n",   # Reset state
        "n",   # Cancel at confirmation!
    ])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert prompt_collection_filters() is None


def test_batch_storage_filter_and_export(tmp_path: Path) -> None:
    storage = BatchStorage(data_dir=tmp_path, output_format="parquet", batch_size_matches=1)

    rec1 = make_sample_record("M1", "P1")
    rec2 = make_sample_record("M1", "P2").model_copy(
        update={"champion_name": "Ahri", "team_position": "MIDDLE", "side": "RED", "win": 0}
    )
    rec3 = make_sample_record("M2", "P3").model_copy(
        update={"champion_name": "Ahri", "team_position": "MIDDLE", "side": "BLUE", "win": 1, "game_version": "14.5.1"}
    )
    storage.add_records([rec1, rec2, rec3])
    storage.flush()

    out_csv = tmp_path / "ahri_blue_14_4.csv"
    count, paths = storage.filter_and_export(
        output_path=out_csv,
        output_format="both",
        champions=["Ahri"],
        positions=["MIDDLE"],
        patch_prefix="14.4",
    )

    assert count == 1
    assert len(paths) == 2
    df = pd.read_csv(out_csv)
    assert len(df) == 1
    assert df["champion_name"].iloc[0] == "Ahri"
    assert df["side"].iloc[0] == "RED"


@respx.mock
def test_multi_platform_collection_strict_mode(tmp_path: Path, sample_match_payload: dict) -> None:
    settings = Settings(
        RIOT_API_KEY="RGAPI-mock-key-12345",
        DATA_DIR=tmp_path / "data",
        BATCH_SIZE=2,
    )

    # BR1 routes
    respx.get("https://br1.api.riotgames.com/lol/league/v4/challengerleagues/by-queue/RANKED_SOLO_5x5").respond(
        status_code=200, json={"entries": [{"puuid": "br-seed-1"}]}
    )
    respx.get("https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/br-seed-1/ids").respond(
        status_code=200, json=["BR1_1"]
    )
    m_br = dict(sample_match_payload)
    m_br["metadata"] = dict(sample_match_payload["metadata"], matchId="BR1_1")
    respx.get("https://americas.api.riotgames.com/lol/match/v5/matches/BR1_1").respond(
        status_code=200, json=m_br
    )

    # KR routes
    respx.get("https://kr.api.riotgames.com/lol/league/v4/challengerleagues/by-queue/RANKED_SOLO_5x5").respond(
        status_code=200, json={"entries": [{"puuid": "kr-seed-1"}]}
    )
    respx.get("https://asia.api.riotgames.com/lol/match/v5/matches/by-puuid/kr-seed-1/ids").respond(
        status_code=200, json=["KR_1"]
    )
    m_kr = dict(sample_match_payload)
    m_kr["metadata"] = dict(sample_match_payload["metadata"], matchId="KR_1")
    respx.get("https://asia.api.riotgames.com/lol/match/v5/matches/KR_1").respond(
        status_code=200, json=m_kr
    )

    config = CollectionFilterConfig(
        platforms=["BR1", "KR"],
        tiers=["CHALLENGER"],
        discover_participants=False,
        target_matches=2,
        output_format="both",
        dataset_name="multi_region",
    )

    run_multi_platform_collection(settings, config)

    parquet_path = settings.data_dir / "multi_region.parquet"
    assert parquet_path.exists()
    df = pd.read_parquet(parquet_path)
    assert len(df) == 20
    assert set(df["match_id"].unique()) == {"BR1_1", "KR_1"}
