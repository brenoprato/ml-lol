"""Unit tests for MatchNormalizer and feature extraction."""

from src.pipeline.normalizer import MatchNormalizer


def test_normalize_valid_match(sample_match_payload: dict) -> None:
    records = MatchNormalizer.normalize_match(sample_match_payload)
    assert len(records) == 10

    first = records[0]
    assert first.match_id == "BR1_9999999999"
    assert first.team_position == "TOP"
    assert first.win == 1
    assert first.kda == round((5 + 8) / 2, 3)
    assert first.total_cs == 230  # 210 + 20
    assert first.cs_per_minute == round(230 / 30.0, 2)
    assert first.gold_per_minute == round(14500 / 30.0, 2)
    assert first.damage_dealt_to_buildings == 4500
    assert first.primary_rune_tree == 8000
    assert first.secondary_rune_tree == 8400


def test_normalize_short_remake_match(sample_match_payload: dict) -> None:
    sample_match_payload["info"]["gameDuration"] = 200  # < 300s
    records = MatchNormalizer.normalize_match(sample_match_payload)
    assert records == []
