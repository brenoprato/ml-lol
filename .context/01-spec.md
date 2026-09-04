# Specification: League of Legends Academic Dataset Pipeline (IC)

## 1. Executive Summary & Problem Statement
The objective of this project is to develop an automated, resilient, and rate-limit compliant data extraction and feature preprocessing pipeline in Python to construct a comprehensive tabular dataset of high-tier League of Legends ranked matches using the official Riot Games API for Academic Scientific Research (Iniciação Científica - IC).

The pipeline extracts **108 granular in-game metrics per participant** across apex tiers (Challenger, Grandmaster, Master), supporting any Riot server region, and storing the dataset simultaneously in **Parquet** (optimized, typed, compressed) and **CSV** (spreadsheet-ready).

---

## 2. Functional Requirements & Scope

### 2.1 Filtering & Scope
- **Queue Filtering:** Extract ranked matches (Queue ID `420` for `RANKED_SOLO_5x5` and `440` for `RANKED_FLEX_SR`).
- **Apex Tier Harvesting:** Automatically harvest seed player PUUIDs from **Challenger, Grandmaster, and Master** leagues via `LEAGUE-V4`.
- **Multi-Region Support:** Automatic mapping from platform routing (e.g. `BR1`, `NA1`, `KR`, `EUW1`) to regional clusters (`americas`, `europe`, `asia`, `sea`).
- **Player Diversity:** Breadth-first crawl sampling recent games per player and discovering the other 9 participants dynamically.
- **Deduplication & Resume:** Atomic checkpointing of visited PUUIDs and processed Match IDs to allow pausing and resuming without duplicate requests or data loss.

### 2.2 Complete Tabular Dataset Schema (108 Features)

1. **Match Context (6):**
   - `match_id`: Unique Riot match identifier (e.g. `BR1_3275903146`).
   - `game_version`: Patch version (e.g. `14.4.1`).
   - `game_duration`: Total match duration in seconds.
   - `queue_id`: Queue identifier (`420` for Solo/Duo).
   - `game_creation`: Epoch timestamp of game creation.
   - `game_ended_in_surrender`: Boolean indicator if the match ended in surrender.

2. **Participant Identity, Role & Side (8):**
   - `puuid`: Encrypted player PUUID.
   - `summoner_name`: Riot ID / Summoner name.
   - `team_id`: Team ID (`100` for Blue, `200` for Red).
   - `side`: Explicit side designation (`BLUE` or `RED`).
   - `team_position`: Primary role (`TOP`, `JUNGLE`, `MIDDLE`, `BOTTOM`, `UTILITY`).
   - `individual_position`: Position assigned by Riot matchmaking.
   - `champion_id`: Numeric champion ID.
   - `champion_name`: Champion name (e.g. `Aatrox`, `Ahri`).
   - `champ_level`: Final champion level (1 to 18).
   - `win`: **Target variable (`1` for Victory, `0` for Defeat)**.

3. **Combat, KDA & Multi-Kills (14):**
   - `kills`, `deaths`, `assists`, `kda`: Basic and calculated combat efficiency.
   - `kill_participation`: Percentage of team kills participated in.
   - `solo_kills`: Solo 1v1 kills without ally assists.
   - `double_kills`, `triple_kills`, `quadra_kills`, `penta_kills`: Multikill counts.
   - `first_blood_kill`, `first_blood_assist`: First blood participation.
   - `largest_killing_spree`, `largest_multi_kill`: Peak combat streaks.
   - `longest_time_spent_living`, `total_time_spent_dead`: Lifespan and death duration.

4. **Damage Dealt, Taken, Heals & Shields (16):**
   - `total_damage_dealt_to_champions`, `physical_damage_dealt_to_champions`, `magic_damage_dealt_to_champions`, `true_damage_dealt_to_champions`.
   - `team_damage_percentage`: Player's damage contribution to total team damage.
   - `damage_per_minute` (DPM): Normalized damage output.
   - `total_damage_taken`, `physical_damage_taken`, `magic_damage_taken`, `true_damage_taken`.
   - `damage_self_mitigated`: Damage absorbed via armor, magic resist, and personal shields.
   - `total_heal`, `total_heals_on_teammates`, `total_damage_shielded_on_teammates`.
   - `time_ccing_others`, `total_time_cc_dealt`: Crowd control score and debuff durations.

5. **Structures & Neutral Objectives (14):**
   - `damage_dealt_to_buildings`: Total damage to turrets and inhibitors.
   - `damage_dealt_to_turrets`: Turret specific damage.
   - `damage_dealt_to_objectives`: Damage to epic monsters (Dragons, Barons, Heralds, Voidgrubs).
   - `turret_kills`, `turret_takedowns`, `turrets_lost`.
   - `turret_plates_taken`: Turret barricade plates destroyed before 14 minutes.
   - `inhibitor_kills`, `inhibitor_takedowns`.
   - `first_tower_kill`, `first_tower_assist`.
   - `dragon_kills`, `baron_kills`, `objectives_stolen`.

6. **Economy & Farming / CS (13):**
   - `gold_earned`, `gold_spent`, `gold_per_minute`, `bounty_gold`.
   - `total_minions_killed`: Lane CS.
   - `neutral_minions_killed`: Jungle CS.
   - `total_ally_jungle_minions_killed`, `total_enemy_jungle_minions_killed` (Counter-jungling).
   - `total_cs`, `cs_per_minute`.
   - `lane_minions_first_10_minutes`, `jungle_cs_before_10_minutes`: Early game CS pace.
   - `early_laning_phase_gold_exp_advantage`: Laning advantage indicator.

7. **Vision & Map Control (6):**
   - `vision_score`, `vision_score_per_minute`.
   - `wards_placed`, `wards_killed`, `control_wards_placed`, `vision_wards_bought_in_game`.

8. **Skillshots & Mechanics (3):**
   - `skillshots_dodged`, `skillshots_hit`, `enemy_champion_immobilizations`.

9. **Spells & Pings (13):**
   - `spell1_casts`, `spell2_casts`, `spell3_casts`, `spell4_casts`: Q/W/E/R ability usage counts.
   - `summoner1_casts`, `summoner2_casts`: Flash/Ignite/Teleport usage counts.
   - `enemy_missing_pings`, `danger_pings`, `on_my_way_pings`, `assist_me_pings`, `all_in_pings`, `push_pings`, `retreat_pings`.

10. **Build & Runes (11):**
    - `item0` through `item6`: Item IDs.
    - `summoner1_id`, `summoner2_id`: Summoner spell IDs.
    - `primary_rune_tree`, `secondary_rune_tree`: Rune tree IDs.

---

## 3. Rate Limiting & Non-Functional Requirements

### 3.1 Riot API Limits & Margins
- **Development Key Limits:** 20 req/1s and 100 req/120s.
- **Safety Margin:** 10% reduction (`safety_margin=0.9`) to guarantee requests stay within limits.
- **Reactive 429 Handling:** Reads `Retry-After` header with jitter and backoff.

### 3.2 Dual Output Persistence
- Saves simultaneously to `data/ranked_matches.parquet` (compressed with Snappy) and `data/ranked_matches.csv` (for immediate spreadsheet view).
