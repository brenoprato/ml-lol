"""Normalizer to transform raw Riot Match-v5 JSON payloads into ML-ready tabular records."""

from typing import Any
from loguru import logger

from src.core.exceptions import SchemaValidationException
from src.models.api_models import MatchDTO
from src.models.dataset_models import MLParticipantRecord


class MatchNormalizer:
    """Transforms and normalizes Riot Match-v5 data into comprehensive ML feature rows."""

    @staticmethod
    def normalize_match(
        raw_match: dict[str, Any],
        min_game_duration_sec: int = 300,
    ) -> list[MLParticipantRecord]:
        """Convert a raw Riot Match-v5 response dict into a list of MLParticipantRecord rows.

        Args:
            raw_match: Raw JSON dict returned from Riot Match-v5 endpoint.
            min_game_duration_sec: Threshold below which matches are treated as remakes (default: 300s / 5m).

        Returns:
            List of 10 MLParticipantRecord objects (or fewer if non-standard).
        """
        try:
            match_dto = MatchDTO.model_validate(raw_match)
        except Exception as err:
            raise SchemaValidationException(f"Failed to validate raw match payload: {err}") from err

        info = match_dto.info
        metadata = match_dto.metadata

        # Exclude remakes or truncated matches
        if info.game_duration < min_game_duration_sec:
            logger.debug(
                f"Skipping match {metadata.match_id}: duration too short ({info.game_duration}s < {min_game_duration_sec}s)"
            )
            return []

        duration_minutes = max(1.0, info.game_duration / 60.0)
        records: list[MLParticipantRecord] = []

        for p in info.participants:
            ch = p.challenges or {}

            # Derived stats
            kda = round((p.kills + p.assists) / max(1, p.deaths), 3)
            gold_per_minute = round(p.gold_earned / duration_minutes, 2)
            total_cs = p.total_minions_killed + p.neutral_minions_killed
            cs_per_minute = round(total_cs / duration_minutes, 2)

            # Challenges stats
            kill_participation = float(ch.get("killParticipation", 0.0))
            solo_kills = int(ch.get("soloKills", 0))
            team_damage_percentage = float(ch.get("teamDamagePercentage", 0.0))
            damage_per_minute = float(ch.get("damagePerMinute", round(p.total_damage_dealt_to_champions / duration_minutes, 2)))
            turret_plates_taken = int(ch.get("turretPlatesTaken", 0))
            bounty_gold = int(ch.get("bountyGold", 0))
            lane_minions_first_10 = int(ch.get("laneMinionsFirst10Minutes", 0))
            jungle_cs_before_10 = int(ch.get("jungleCsBefore10Minutes", 0))
            early_lead = int(ch.get("earlyLaningPhaseGoldExpAdvantage", 0))
            vision_score_per_min = float(ch.get("visionScorePerMinute", round(p.vision_score / duration_minutes, 2)))
            control_wards_placed = int(ch.get("controlWardsPlaced", 0))
            skillshots_dodged = int(ch.get("skillshotsDodged", 0))
            skillshots_hit = int(ch.get("skillshotsHit", 0))
            immobilizations = int(ch.get("enemyChampionImmobilizations", 0))

            # Runes
            primary_rune_tree = 0
            secondary_rune_tree = 0
            if p.perks and p.perks.styles:
                if len(p.perks.styles) > 0:
                    primary_rune_tree = p.perks.styles[0].style
                if len(p.perks.styles) > 1:
                    secondary_rune_tree = p.perks.styles[1].style

            position = p.team_position or p.individual_position or "UNKNOWN"
            side = "BLUE" if p.team_id == 100 else "RED"

            record = MLParticipantRecord(
                match_id=metadata.match_id,
                game_version=info.game_version,
                game_duration=info.game_duration,
                queue_id=info.queue_id,
                game_creation=info.game_creation,
                game_ended_in_surrender=info.game_ended_in_surrender,
                puuid=p.puuid,
                summoner_name=p.summoner_name or p.riot_id_game_name,
                team_id=p.team_id,
                side=side,
                team_position=position.upper(),
                individual_position=p.individual_position or "",
                champion_id=p.champion_id,
                champion_name=p.champion_name,
                champ_level=p.champ_level,
                win=1 if p.win else 0,
                kills=p.kills,
                deaths=p.deaths,
                assists=p.assists,
                kda=kda,
                kill_participation=round(kill_participation, 4),
                solo_kills=solo_kills,
                double_kills=p.double_kills,
                triple_kills=p.triple_kills,
                quadra_kills=p.quadra_kills,
                penta_kills=p.penta_kills,
                first_blood_kill=p.first_blood_kill,
                first_blood_assist=p.first_blood_assist,
                largest_killing_spree=p.largest_killing_spree,
                largest_multi_kill=p.largest_multi_kill,
                longest_time_spent_living=p.longest_time_spent_living,
                total_time_spent_dead=p.total_time_spent_dead,
                total_damage_dealt_to_champions=p.total_damage_dealt_to_champions,
                physical_damage_dealt_to_champions=p.physical_damage_dealt_to_champions,
                magic_damage_dealt_to_champions=p.magic_damage_dealt_to_champions,
                true_damage_dealt_to_champions=p.true_damage_dealt_to_champions,
                team_damage_percentage=round(team_damage_percentage, 4),
                damage_per_minute=round(damage_per_minute, 2),
                total_damage_taken=p.total_damage_taken,
                physical_damage_taken=p.physical_damage_taken,
                magic_damage_taken=p.magic_damage_taken,
                true_damage_taken=p.true_damage_taken,
                damage_self_mitigated=p.damage_self_mitigated,
                total_heal=p.total_heal,
                total_heals_on_teammates=p.total_heals_on_teammates,
                total_damage_shielded_on_teammates=p.total_damage_shielded_on_teammates,
                time_ccing_others=p.time_ccing_others,
                total_time_cc_dealt=p.total_time_cc_dealt,
                damage_dealt_to_buildings=p.damage_dealt_to_buildings,
                damage_dealt_to_turrets=p.damage_dealt_to_turrets,
                damage_dealt_to_objectives=p.damage_dealt_to_objectives,
                turret_kills=p.turret_kills,
                turret_takedowns=p.turret_takedowns,
                turrets_lost=p.turrets_lost,
                turret_plates_taken=turret_plates_taken,
                inhibitor_kills=p.inhibitor_kills,
                inhibitor_takedowns=p.inhibitor_takedowns,
                first_tower_kill=p.first_tower_kill,
                first_tower_assist=p.first_tower_assist,
                dragon_kills=p.dragon_kills,
                baron_kills=p.baron_kills,
                objectives_stolen=p.objectives_stolen,
                gold_earned=p.gold_earned,
                gold_spent=p.gold_spent,
                gold_per_minute=gold_per_minute,
                bounty_gold=bounty_gold,
                total_minions_killed=p.total_minions_killed,
                neutral_minions_killed=p.neutral_minions_killed,
                total_ally_jungle_minions_killed=p.total_ally_jungle_minions_killed,
                total_enemy_jungle_minions_killed=p.total_enemy_jungle_minions_killed,
                total_cs=total_cs,
                cs_per_minute=cs_per_minute,
                lane_minions_first_10_minutes=lane_minions_first_10,
                jungle_cs_before_10_minutes=jungle_cs_before_10,
                early_laning_phase_gold_exp_advantage=early_lead,
                vision_score=p.vision_score,
                vision_score_per_minute=round(vision_score_per_min, 2),
                wards_placed=p.wards_placed,
                wards_killed=p.wards_killed,
                vision_wards_bought_in_game=p.vision_wards_bought_in_game,
                control_wards_placed=control_wards_placed,
                skillshots_dodged=skillshots_dodged,
                skillshots_hit=skillshots_hit,
                enemy_champion_immobilizations=immobilizations,
                spell1_casts=p.spell1_casts,
                spell2_casts=p.spell2_casts,
                spell3_casts=p.spell3_casts,
                spell4_casts=p.spell4_casts,
                summoner1_casts=p.summoner1_casts,
                summoner2_casts=p.summoner2_casts,
                enemy_missing_pings=p.enemy_missing_pings,
                danger_pings=p.danger_pings,
                on_my_way_pings=p.on_my_way_pings,
                assist_me_pings=p.assist_me_pings,
                all_in_pings=p.all_in_pings,
                push_pings=p.push_pings,
                retreat_pings=p.retreat_pings,
                item0=p.item0,
                item1=p.item1,
                item2=p.item2,
                item3=p.item3,
                item4=p.item4,
                item5=p.item5,
                item6=p.item6,
                summoner1_id=p.summoner1_id,
                summoner2_id=p.summoner2_id,
                primary_rune_tree=primary_rune_tree,
                secondary_rune_tree=secondary_rune_tree,
            )
            records.append(record)

        return records
