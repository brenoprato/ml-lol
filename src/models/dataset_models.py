"""Pydantic model representing the comprehensive ML participant feature row."""

from typing import Optional
from pydantic import BaseModel, ConfigDict


class MLParticipantRecord(BaseModel):
    """Tabular schema for exhaustive ML participant records extracted from League of Legends matches."""

    model_config = ConfigDict(extra="forbid")

    # Match Context
    match_id: str
    game_version: str
    game_duration: int
    queue_id: int
    game_creation: int
    game_ended_in_surrender: bool

    # Participant Identity & Side
    puuid: str
    summoner_name: Optional[str]
    team_id: int
    side: str  # "BLUE" (100) or "RED" (200)
    team_position: str  # TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY
    individual_position: str
    champion_id: int
    champion_name: str
    champ_level: int
    win: int  # 1 (Victory) or 0 (Defeat)

    # Combat & KDA
    kills: int
    deaths: int
    assists: int
    kda: float
    kill_participation: float
    solo_kills: int
    double_kills: int
    triple_kills: int
    quadra_kills: int
    penta_kills: int
    first_blood_kill: bool
    first_blood_assist: bool
    largest_killing_spree: int
    largest_multi_kill: int
    longest_time_spent_living: int
    total_time_spent_dead: int

    # Damage Breakdown
    total_damage_dealt_to_champions: int
    physical_damage_dealt_to_champions: int
    magic_damage_dealt_to_champions: int
    true_damage_dealt_to_champions: int
    team_damage_percentage: float
    damage_per_minute: float
    total_damage_taken: int
    physical_damage_taken: int
    magic_damage_taken: int
    true_damage_taken: int
    damage_self_mitigated: int
    total_heal: int
    total_heals_on_teammates: int
    total_damage_shielded_on_teammates: int
    time_ccing_others: int
    total_time_cc_dealt: int

    # Structures & Objectives
    damage_dealt_to_buildings: int
    damage_dealt_to_turrets: int
    damage_dealt_to_objectives: int
    turret_kills: int
    turret_takedowns: int
    turrets_lost: int
    turret_plates_taken: int
    inhibitor_kills: int
    inhibitor_takedowns: int
    first_tower_kill: bool
    first_tower_assist: bool
    dragon_kills: int
    baron_kills: int
    objectives_stolen: int

    # Economy & Farming Pace
    gold_earned: int
    gold_spent: int
    gold_per_minute: float
    bounty_gold: int
    total_minions_killed: int
    neutral_minions_killed: int
    total_ally_jungle_minions_killed: int
    total_enemy_jungle_minions_killed: int
    total_cs: int
    cs_per_minute: float
    lane_minions_first_10_minutes: int
    jungle_cs_before_10_minutes: int
    early_laning_phase_gold_exp_advantage: int

    # Vision & Map Control
    vision_score: int
    vision_score_per_minute: float
    wards_placed: int
    wards_killed: int
    vision_wards_bought_in_game: int
    control_wards_placed: int

    # Mechanics & Skillshots
    skillshots_dodged: int
    skillshots_hit: int
    enemy_champion_immobilizations: int

    # Spells & Pings
    spell1_casts: int
    spell2_casts: int
    spell3_casts: int
    spell4_casts: int
    summoner1_casts: int
    summoner2_casts: int
    enemy_missing_pings: int
    danger_pings: int
    on_my_way_pings: int
    assist_me_pings: int
    all_in_pings: int
    push_pings: int
    retreat_pings: int

    # Items & Runes
    item0: int
    item1: int
    item2: int
    item3: int
    item4: int
    item5: int
    item6: int
    summoner1_id: int
    summoner2_id: int
    primary_rune_tree: int
    secondary_rune_tree: int
