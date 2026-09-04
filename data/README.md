# League of Legends Dataset Dictionary & Codebook

Official Data Dictionary and Codebook for the dataset collected via the Riot Games API for Academic Scientific Research (*Iniciacao Cientifica - IC*) and Machine Learning applications.

[Versao em Portugues (README.pt-BR.md)](README.pt-BR.md)

---

## 1. Dataset Metadata

- **Data Source:** Official Riot Games API (`LEAGUE-V4` and `MATCH-V5`).
- **Target Tiers:** Apex Ranked Solo/Duo (Challenger, Grandmaster, Master).
- **Target Queue:** Queue ID `420` (`RANKED_SOLO_5x5`).
- **Granularity:** **10 rows per match** (each row represents 1 unique participant in that match).
- **File Formats:**
  - `data/ranked_matches.parquet`: Column-oriented, Snappy-compressed format preserving strict data types (recommended for Python, Pandas, Polars, Scikit-learn).
  - `data/ranked_matches.csv`: Standard delimited UTF-8 tabular CSV format (recommended for Excel, Google Sheets, or spreadsheet inspection).
- **State Checkpoint:** `data/state_<platform>.json` (Tracks visited PUUIDs and processed Match IDs to ensure zero duplicate matches across runs).

---

## 2. Complete Feature Dictionary (108 Columns)

### 2.1 Match Identification, Context & Side (10 columns)
| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `match_id` | `string` | Unique Riot Match identifier (e.g. `BR1_3275903146`). |
| `game_version` | `string` | Game patch version (e.g. `14.4.1`). |
| `game_duration` | `int64` | Total match duration in **seconds**. |
| `queue_id` | `int64` | Queue type identifier (`420` for Ranked Solo/Duo). |
| `game_creation` | `int64` | Epoch timestamp (milliseconds) of match creation. |
| `game_ended_in_surrender` | `bool` | `True` if the match ended early via surrender vote. |
| `puuid` | `string` | Encrypted, persistent player identifier from Riot Games. |
| `summoner_name` | `string` | Player Riot ID / In-game Summoner name. |
| `team_id` | `int64` | Team identifier: `100` for Blue Side, `200` for Red Side. |
| `side` | `string` | Explicit map side: **`BLUE`** or **`RED`**. |

### 2.2 Player Role, Champion & Target Variable (6 columns)
| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `team_position` | `string` | Primary assigned role: `TOP`, `JUNGLE`, `MIDDLE`, `BOTTOM` (ADC), or `UTILITY` (Support). |
| `individual_position` | `string` | Role detected algorithmically by Riot matchmaking. |
| `champion_id` | `int64` | Riot numerical Champion ID. |
| `champion_name` | `string` | Champion name (e.g. `Aatrox`, `Ahri`, `Yasuo`). |
| `champ_level` | `int64` | Final level reached by the champion (1 - 18). |
| `win` | `int64` | **Target Variable:** `1` for Victory, `0` for Defeat. |

### 2.3 Combat, KDA & Multikills (16 columns)
| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `kills` | `int64` | Number of enemy champions killed. |
| `deaths` | `int64` | Number of times the player died. |
| `assists` | `int64` | Number of assists on enemy champion kills. |
| `kda` | `double` | Calculated ratio: `(kills + assists) / max(1, deaths)`. |
| `kill_participation` | `double` | Player's kill participation percentage in team's total kills (`0.0` to `1.0`). |
| `solo_kills` | `int64` | Number of solo 1v1 kills achieved without teammate assistance. |
| `double_kills` | `int64` | Number of 2-kill streaks. |
| `triple_kills` | `int64` | Number of 3-kill streaks. |
| `quadra_kills` | `int64` | Number of 4-kill streaks. |
| `penta_kills` | `int64` | Number of 5-kill streaks (Ace). |
| `first_blood_kill` | `bool` | `True` if the player scored the First Blood kill. |
| `first_blood_assist` | `bool` | `True` if the player assisted in the First Blood kill. |
| `largest_killing_spree` | `int64` | Maximum consecutive kills without dying. |
| `largest_multi_kill` | `int64` | Maximum simultaneous multikill score in a fight. |
| `longest_time_spent_living` | `int64` | Longest single continuous lifespan during the match (in seconds). |
| `total_time_spent_dead` | `int64` | Cumulative time spent waiting to respawn (in seconds). |

### 2.4 Damage Breakdown, Healing, Shielding & CC (16 columns)
| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `total_damage_dealt_to_champions` | `int64` | Total damage dealt to enemy champions. |
| `physical_damage_dealt_to_champions` | `int64` | Physical damage dealt to enemy champions. |
| `magic_damage_dealt_to_champions` | `int64` | Magic damage dealt to enemy champions. |
| `true_damage_dealt_to_champions` | `int64` | True damage dealt to enemy champions (ignores armor/MR). |
| `team_damage_percentage` | `double` | Share of total team damage dealt by this player (`0.0` to `1.0`). |
| `damage_per_minute` | `double` | DPM (Damage dealt to champions per minute). |
| `total_damage_taken` | `int64` | Total damage absorbed from all sources. |
| `physical_damage_taken` | `int64` | Physical damage taken. |
| `magic_damage_taken` | `int64` | Magic damage taken. |
| `true_damage_taken` | `int64` | True damage taken. |
| `damage_self_mitigated` | `int64` | Damage prevented via armor, magic resist, and self shields. |
| `total_heal` | `int64` | Total health restored to self. |
| `total_heals_on_teammates` | `int64` | Total healing applied to allied champions. |
| `total_damage_shielded_on_teammates` | `int64` | Total damage absorbed by shields granted to allies. |
| `time_ccing_others` | `int64` | Total duration (in seconds) of Crowd Control applied to enemies. |
| `total_time_cc_dealt` | `int64` | Total CC and debuff time applied in game. |

### 2.5 Structures, Turrets & Neutral Objectives (14 columns)
| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `damage_dealt_to_buildings` | `int64` | Total damage dealt to structures (turrets + inhibitors). |
| `damage_dealt_to_turrets` | `int64` | Specific damage dealt to enemy turrets. |
| `damage_dealt_to_objectives` | `int64` | Damage dealt to neutral epic monsters (Dragons, Barons, Heralds, Voidgrubs). |
| `turret_kills` | `int64` | Number of turrets directly destroyed (last hit). |
| `turret_takedowns` | `int64` | Number of turret destructions participated in. |
| `turrets_lost` | `int64` | Number of turrets lost by the player's lane. |
| `turret_plates_taken` | `int64` | Number of turret barricade plates destroyed before 14:00. |
| `inhibitor_kills` | `int64` | Number of inhibitors directly destroyed. |
| `inhibitor_takedowns` | `int64` | Number of inhibitor destructions participated in. |
| `first_tower_kill` | `bool` | `True` if the player destroyed the First Turret of the game. |
| `first_tower_assist` | `bool` | `True` if the player assisted in destroying the First Turret. |
| `dragon_kills` | `int64` | Number of Dragons killed by the player. |
| `baron_kills` | `int64` | Number of Barons killed by the player. |
| `objectives_stolen` | `int64` | Number of epic monsters stolen from the enemy team (*steals*). |

### 2.6 Economy, CS & Early Game Laning Pace (13 columns)
| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `gold_earned` | `int64` | Total gold accumulated throughout the match. |
| `gold_spent` | `int64` | Total gold spent on item purchases. |
| `gold_per_minute` | `double` | Gold earned per minute (GPM). |
| `bounty_gold` | `int64` | Extra gold earned from collecting champion shutdowns. |
| `total_minions_killed` | `int64` | Lane minions killed (Lane CS). |
| `neutral_minions_killed` | `int64` | Jungle monsters killed (Jungle CS). |
| `total_ally_jungle_minions_killed` | `int64` | Monsters killed in allied jungle. |
| `total_enemy_jungle_minions_killed` | `int64` | **Monsters killed in enemy jungle (*Counter-Jungling*)**. |
| `total_cs` | `int64` | Total CS (`total_minions_killed + neutral_minions_killed`). |
| `cs_per_minute` | `double` | Creep Score per minute (CS/min). |
| `lane_minions_first_10_minutes` | `int64` | Lane minions killed in the first 10 minutes of play. |
| `jungle_cs_before_10_minutes` | `int64` | Jungle monsters killed in the first 10 minutes of play. |
| `early_laning_phase_gold_exp_advantage`| `int64` | Riot score indicating gold/experience lead achieved during early laning. |

### 2.7 Vision & Map Influence (6 columns)
| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `vision_score` | `int64` | Official Riot in-game Vision Score. |
| `vision_score_per_minute` | `double` | Vision score generated per minute. |
| `wards_placed` | `int64` | Total stealth and control wards placed on the map. |
| `wards_killed` | `int64` | Total enemy wards discovered and cleared. |
| `control_wards_placed` | `int64` | Control wards (*Pink Wards*) placed. |
| `vision_wards_bought_in_game` | `int64` | Control wards purchased with gold from the shop. |

### 2.8 Mechanics, Skillshots & Pings (16 columns)
| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `skillshots_dodged` | `int64` | **Number of enemy skillshot projectiles dodged.** |
| `skillshots_hit` | `int64` | **Number of skillshot projectiles successfully hit on enemies.** |
| `enemy_champion_immobilizations` | `int64` | Number of times enemy champions were immobilized (Stun, Root, Knockup). |
| `spell1_casts` | `int64` | Total number of times **Q** was cast. |
| `spell2_casts` | `int64` | Total number of times **W** was cast. |
| `spell3_casts` | `int64` | Total number of times **E** was cast. |
| `spell4_casts` | `int64` | Total number of times **R (Ultimate)** was cast. |
| `summoner1_casts` | `int64` | Number of times Summoner Spell 1 (e.g. Flash) was activated. |
| `summoner2_casts` | `int64` | Number of times Summoner Spell 2 (e.g. Ignite/TP) was activated. |
| `enemy_missing_pings` | `int64` | "Enemy Missing" (`?`) pings issued. |
| `danger_pings` | `int64` | "Danger" (`!`) pings issued. |
| `on_my_way_pings` | `int64` | "On My Way" pings issued. |
| `assist_me_pings` | `int64` | "Assist Me" pings issued. |
| `all_in_pings` | `int64` | "All-in" pings issued. |
| `push_pings` | `int64` | "Push Lane" pings issued. |
| `retreat_pings` | `int64` | "Retreat / Yellow Danger" pings issued. |

### 2.9 Build, Summoner Spells & Rune IDs (11 columns)
| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `item0` | `int64` | **Item ID** in inventory slot 1 (`0` if empty). |
| `item1` | `int64` | **Item ID** in inventory slot 2. |
| `item2` | `int64` | **Item ID** in inventory slot 3. |
| `item3` | `int64` | **Item ID** in inventory slot 4. |
| `item4` | `int64` | **Item ID** in inventory slot 5. |
| `item5` | `int64` | **Item ID** in inventory slot 6. |
| `item6` | `int64` | **Item ID of Trinket/Ward** (e.g. `3340` Yellow, `3364` Red Oracle, `3363` Blue). |
| `summoner1_id` | `int64` | **ID of Summoner Spell 1** (e.g. `4` = Flash, `14` = Ignite). |
| `summoner2_id` | `int64` | **ID of Summoner Spell 2**. |
| `primary_rune_tree` | `int64` | **Primary Rune Tree ID** (`8000`: Precision, `8100`: Domination, `8200`: Sorcery, `8300`: Inspiration, `8400`: Resolve). |
| `secondary_rune_tree` | `int64` | **Secondary Rune Tree ID**. |

---

## 3. Reference Tables

### 3.1 Summoner Spell IDs
| ID | English Name | Portuguese Name |
| :--- | :--- | :--- |
| `1` | Cleanse | Purificar |
| `3` | Exhaust | Exaustao |
| `4` | Flash | Flash |
| `6` | Ghost | Fantasma |
| `7` | Heal | Curar |
| `11` | Smite | Golpear |
| `12` | Teleport | Teleporte |
| `14` | Ignite | Incendiar |
| `21` | Barrier | Barreira |

### 3.2 Rune Tree IDs
| ID | Tree Name | Theme |
| :--- | :--- | :--- |
| `8000` | Precision | Attack speed, sustained combat damage, and executes. |
| `8100` | Domination | Burst damage, target access, and assassination. |
| `8200` | Sorcery | Resource scaling, ability power, and cooldown reduction. |
| `8300` | Inspiration | Utility, economy bonuses, and creative tools. |
| `8400` | Resolve | Durability, health scaling, and crowd control resistance. |

---

## 4. Python Loading Example (Pandas & Polars)

```python
import pandas as pd

# Load the full compressed Parquet dataset
df = pd.read_parquet("data/ranked_matches.parquet")

print(f"Total participant rows: {len(df):,}")
print(f"Total unique matches:   {df['match_id'].nunique():,}")

# Example: Filter TOP laners and examine building damage vs gold
top_laners = df[df["team_position"] == "TOP"]
print(top_laners[["champion_name", "win", "damage_dealt_to_buildings", "gold_per_minute"]].head())
```
