"""Unit tests for BatchStorage and Parquet/CSV persistence."""

from pathlib import Path
import pandas as pd
from src.models.dataset_models import MLParticipantRecord
from src.pipeline.storage import BatchStorage


def make_sample_record(match_id: str, puuid: str) -> MLParticipantRecord:
    return MLParticipantRecord(
        match_id=match_id,
        game_version="14.4.1",
        game_duration=1800,
        queue_id=420,
        game_creation=1700000000,
        game_ended_in_surrender=False,
        puuid=puuid,
        summoner_name=f"Summoner_{puuid}",
        team_id=100,
        side="BLUE",
        team_position="TOP",
        individual_position="TOP",
        champion_id=266,
        champion_name="Aatrox",
        champ_level=16,
        win=1,
        kills=6,
        deaths=2,
        assists=5,
        kda=5.5,
        kill_participation=0.55,
        solo_kills=2,
        double_kills=1,
        triple_kills=0,
        quadra_kills=0,
        penta_kills=0,
        first_blood_kill=False,
        first_blood_assist=False,
        largest_killing_spree=4,
        largest_multi_kill=2,
        longest_time_spent_living=700,
        total_time_spent_dead=45,
        total_damage_dealt_to_champions=24000,
        physical_damage_dealt_to_champions=22000,
        magic_damage_dealt_to_champions=1000,
        true_damage_dealt_to_champions=1000,
        team_damage_percentage=0.28,
        damage_per_minute=800.0,
        total_damage_taken=20000,
        physical_damage_taken=12000,
        magic_damage_taken=7000,
        true_damage_taken=1000,
        damage_self_mitigated=15000,
        total_heal=3500,
        total_heals_on_teammates=0,
        total_damage_shielded_on_teammates=0,
        time_ccing_others=30,
        total_time_cc_dealt=120,
        damage_dealt_to_buildings=5000,
        damage_dealt_to_turrets=4500,
        damage_dealt_to_objectives=8000,
        turret_kills=2,
        turret_takedowns=3,
        turrets_lost=2,
        turret_plates_taken=2,
        inhibitor_kills=1,
        inhibitor_takedowns=1,
        first_tower_kill=True,
        first_tower_assist=False,
        dragon_kills=0,
        baron_kills=0,
        objectives_stolen=0,
        gold_earned=14000,
        gold_spent=13000,
        gold_per_minute=466.67,
        bounty_gold=300,
        total_minions_killed=200,
        neutral_minions_killed=10,
        total_ally_jungle_minions_killed=8,
        total_enemy_jungle_minions_killed=2,
        total_cs=210,
        cs_per_minute=7.0,
        lane_minions_first_10_minutes=75,
        jungle_cs_before_10_minutes=0,
        early_laning_phase_gold_exp_advantage=1,
        vision_score=25,
        vision_score_per_minute=0.83,
        wards_placed=10,
        wards_killed=4,
        vision_wards_bought_in_game=3,
        control_wards_placed=2,
        skillshots_dodged=15,
        skillshots_hit=22,
        enemy_champion_immobilizations=14,
        spell1_casts=60,
        spell2_casts=40,
        spell3_casts=35,
        spell4_casts=12,
        summoner1_casts=4,
        summoner2_casts=3,
        enemy_missing_pings=3,
        danger_pings=2,
        on_my_way_pings=5,
        assist_me_pings=1,
        all_in_pings=2,
        push_pings=3,
        retreat_pings=1,
        item0=3078,
        item1=3053,
        item2=3047,
        item3=0,
        item4=0,
        item5=0,
        item6=3340,
        summoner1_id=4,
        summoner2_id=12,
        primary_rune_tree=8000,
        secondary_rune_tree=8400,
    )


def test_batch_storage_parquet_and_csv(tmp_path: Path) -> None:
    storage = BatchStorage(data_dir=tmp_path, output_format="both", batch_size_matches=1)

    records_m1 = [make_sample_record("M1", f"P{i}") for i in range(10)]
    storage.add_records(records_m1)
    storage.flush()

    assert storage.parquet_path.exists()
    assert storage.csv_path.exists()

    df_parquet = pd.read_parquet(storage.parquet_path)
    assert len(df_parquet) == 10
    assert df_parquet["match_id"].iloc[0] == "M1"
    assert df_parquet["champion_name"].iloc[0] == "Aatrox"
    assert df_parquet["side"].iloc[0] == "BLUE"

    # Append second match
    records_m2 = [make_sample_record("M2", f"P{i}") for i in range(10)]
    storage.add_records(records_m2)
    storage.flush()

    df_parquet_updated = pd.read_parquet(storage.parquet_path)
    assert len(df_parquet_updated) == 20
