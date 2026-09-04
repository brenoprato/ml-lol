"""Pydantic models representing raw Riot API Match-v5 responses."""

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class PerkSelectionDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")
    perk: int = 0
    var1: int = 0
    var2: int = 0
    var3: int = 0


class PerkStyleDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: Optional[str] = None
    selections: list[PerkSelectionDTO] = Field(default_factory=list)
    style: int = 0


class PerksDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")
    styles: list[PerkStyleDTO] = Field(default_factory=list)


class ParticipantDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")

    puuid: str
    summoner_name: Optional[str] = Field(default=None, alias="summonerName")
    riot_id_game_name: Optional[str] = Field(default=None, alias="riotIdGameName")
    riot_id_tagline: Optional[str] = Field(default=None, alias="riotIdTagline")
    participant_id: int = Field(default=0, alias="participantId")
    team_id: int = Field(default=100, alias="teamId")
    team_position: str = Field(default="", alias="teamPosition")
    individual_position: str = Field(default="", alias="individualPosition")
    champion_id: int = Field(default=0, alias="championId")
    champion_name: str = Field(default="Unknown", alias="championName")
    champ_level: int = Field(default=1, alias="champLevel")
    win: bool = False

    # KDA & Combat
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    double_kills: int = Field(default=0, alias="doubleKills")
    triple_kills: int = Field(default=0, alias="tripleKills")
    quadra_kills: int = Field(default=0, alias="quadraKills")
    penta_kills: int = Field(default=0, alias="pentaKills")
    first_blood_kill: bool = Field(default=False, alias="firstBloodKill")
    first_blood_assist: bool = Field(default=False, alias="firstBloodAssist")
    largest_killing_spree: int = Field(default=0, alias="largestKillingSpree")
    largest_multi_kill: int = Field(default=0, alias="largestMultiKill")
    longest_time_spent_living: int = Field(default=0, alias="longestTimeSpentLiving")
    total_time_spent_dead: int = Field(default=0, alias="totalTimeSpentDead")

    # Damage Dealt
    total_damage_dealt_to_champions: int = Field(default=0, alias="totalDamageDealtToChampions")
    physical_damage_dealt_to_champions: int = Field(default=0, alias="physicalDamageDealtToChampions")
    magic_damage_dealt_to_champions: int = Field(default=0, alias="magicDamageDealtToChampions")
    true_damage_dealt_to_champions: int = Field(default=0, alias="trueDamageDealtToChampions")
    total_damage_dealt: int = Field(default=0, alias="totalDamageDealt")

    # Damage Taken, Mitigated, Heals & Shields
    total_damage_taken: int = Field(default=0, alias="totalDamageTaken")
    physical_damage_taken: int = Field(default=0, alias="physicalDamageTaken")
    magic_damage_taken: int = Field(default=0, alias="magicDamageTaken")
    true_damage_taken: int = Field(default=0, alias="trueDamageTaken")
    damage_self_mitigated: int = Field(default=0, alias="damageSelfMitigated")
    total_heal: int = Field(default=0, alias="totalHeal")
    total_heals_on_teammates: int = Field(default=0, alias="totalHealsOnTeammates")
    total_damage_shielded_on_teammates: int = Field(default=0, alias="totalDamageShieldedOnTeammates")
    time_ccing_others: int = Field(default=0, alias="timeCCingOthers")
    total_time_cc_dealt: int = Field(default=0, alias="totalTimeCCDealt")

    # Structures & Objectives
    damage_dealt_to_buildings: int = Field(default=0, alias="damageDealtToBuildings")
    damage_dealt_to_turrets: int = Field(default=0, alias="damageDealtToTurrets")
    damage_dealt_to_objectives: int = Field(default=0, alias="damageDealtToObjectives")
    turret_kills: int = Field(default=0, alias="turretKills")
    turret_takedowns: int = Field(default=0, alias="turretTakedowns")
    turrets_lost: int = Field(default=0, alias="turretsLost")
    inhibitor_kills: int = Field(default=0, alias="inhibitorKills")
    inhibitor_takedowns: int = Field(default=0, alias="inhibitorTakedowns")
    first_tower_kill: bool = Field(default=False, alias="firstTowerKill")
    first_tower_assist: bool = Field(default=False, alias="firstTowerAssist")
    dragon_kills: int = Field(default=0, alias="dragonKills")
    baron_kills: int = Field(default=0, alias="baronKills")
    objectives_stolen: int = Field(default=0, alias="objectivesStolen")

    # Economy & CS
    gold_earned: int = Field(default=0, alias="goldEarned")
    gold_spent: int = Field(default=0, alias="goldSpent")
    total_minions_killed: int = Field(default=0, alias="totalMinionsKilled")
    neutral_minions_killed: int = Field(default=0, alias="neutralMinionsKilled")
    total_ally_jungle_minions_killed: int = Field(default=0, alias="totalAllyJungleMinionsKilled")
    total_enemy_jungle_minions_killed: int = Field(default=0, alias="totalEnemyJungleMinionsKilled")

    # Vision
    vision_score: int = Field(default=0, alias="visionScore")
    wards_placed: int = Field(default=0, alias="wardsPlaced")
    wards_killed: int = Field(default=0, alias="wardsKilled")
    vision_wards_bought_in_game: int = Field(default=0, alias="visionWardsBoughtInGame")

    # Spells & Casts
    spell1_casts: int = Field(default=0, alias="spell1Casts")
    spell2_casts: int = Field(default=0, alias="spell2Casts")
    spell3_casts: int = Field(default=0, alias="spell3Casts")
    spell4_casts: int = Field(default=0, alias="spell4Casts")
    summoner1_casts: int = Field(default=0, alias="summoner1Casts")
    summoner2_casts: int = Field(default=0, alias="summoner2Casts")

    # Pings
    enemy_missing_pings: int = Field(default=0, alias="enemyMissingPings")
    danger_pings: int = Field(default=0, alias="dangerPings")
    on_my_way_pings: int = Field(default=0, alias="onMyWayPings")
    assist_me_pings: int = Field(default=0, alias="assistMePings")
    all_in_pings: int = Field(default=0, alias="allInPings")
    push_pings: int = Field(default=0, alias="pushPings")
    retreat_pings: int = Field(default=0, alias="retreatPings")

    # Items & Runes
    item0: int = 0
    item1: int = 0
    item2: int = 0
    item3: int = 0
    item4: int = 0
    item5: int = 0
    item6: int = 0
    summoner1_id: int = Field(default=0, alias="summoner1Id")
    summoner2_id: int = Field(default=0, alias="summoner2Id")
    perks: Optional[PerksDTO] = None

    # Challenges (Advanced Riot Metrics)
    challenges: dict[str, Any] = Field(default_factory=dict)


class MetadataDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")
    match_id: str = Field(alias="matchId")
    participants: list[str] = Field(default_factory=list)


class InfoDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")
    game_creation: int = Field(default=0, alias="gameCreation")
    game_duration: int = Field(default=0, alias="gameDuration")
    game_version: str = Field(default="", alias="gameVersion")
    queue_id: int = Field(default=0, alias="queueId")
    game_ended_in_surrender: bool = Field(default=False, alias="gameEndedInSurrender")
    game_ended_in_early_surrender: bool = Field(default=False, alias="gameEndedInEarlySurrender")
    participants: list[ParticipantDTO] = Field(default_factory=list)
    teams: list[dict[str, Any]] = Field(default_factory=list)


class MatchDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")
    metadata: MetadataDTO
    info: InfoDTO
