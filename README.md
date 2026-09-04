# 🎮 League of Legends ML Dataset Pipeline & Champion Clustering

An automated, resilient, and rate-limit compliant data extraction and preprocessing pipeline in Python to build Machine Learning datasets from high-tier League of Legends ranked matches (Challenger / Grandmaster / Master) using the Riot Games API.

---

## 🚀 Key Features

- **⚡ Strict Rate Limiting Compliance:** Proactive dual-window sliding rate limiter (20 req/1s and 100 req/120s) with 10% safety margins and reactive HTTP 429 backoff.
- **🌐 Player Diversity Crawling:** Breadth-first crawl sampling recent games across Challenger players and discovering new high-MMR participants recursively rather than exhausting single accounts.
- **🔄 Checkpointing & Deduplication:** Atomic state persistence (`data/state_br1.json`) allowing safe pause/resume (`Ctrl+C` / restart) without duplicate requests or corrupted data.
- **📦 High-Performance Storage (Parquet & CSV):** Atomic writes to compressed columnar `Parquet` format (preserving strict data types and 5-10x smaller than CSV) with automatic or one-command `CSV` export.
- **🧠 ML-Ready Extracted Features:** 50+ granular metrics per participant (building damage, CC duration, individual gold/min, CS/min, vision score, runes, win/loss).
- **🏆 Unsupervised Archetype Clustering:** Built-in ML clustering script to segment champions into playstyle archetypes (Split-pushers, Engagers, Supports, Assassins, Marksmen).

---

## ⚙️ Installation & Setup

1. **Clone and setup virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure Riot API Key:**
   Create a `.env` file (copied from `.env.example`):
   ```env
   RIOT_API_KEY=RGAPI-your-riot-api-key
   DEFAULT_PLATFORM=BR1
   DEFAULT_REGION=americas
   TARGET_QUEUE_ID=420
   ```

---

## 📖 CLI Usage Guide

### 1. Start Continuous Match Collection (e.g. for 8 Hours)
```bash
# Run for the next 8 hours collecting Challenger matches from BR1
python3 src/main.py collect --hours 8.0

# Run for 8 hours including Grandmaster seeds as well
python3 src/main.py collect --hours 8.0 --include-gm

# Collect a specific target number of matches (e.g., 500 matches)
python3 src/main.py collect -n 500
```

### 2. Check Crawler & Dataset Status
```bash
python3 src/main.py status
```

### 3. Export Parquet Dataset to CSV
```bash
python3 src/main.py export -o data/ranked_matches.csv
```

### 4. Run Champion Playstyle Clustering (Unsupervised ML)
```bash
python3 src/ml/clustering.py
```

---

## 📊 Dataset Schema Overview

Each row in `data/ranked_matches.parquet` represents a participant in a ranked 5v5 match (10 rows per match):

| Field | Type | Description |
| :--- | :--- | :--- |
| `match_id` | `str` | Unique Riot Match ID |
| `game_version` | `str` | Patch version (e.g. `14.4.1`) |
| `game_duration` | `int` | Match duration in seconds |
| `puuid` | `str` | Player PUUID |
| `team_id` | `int` | `100` (Blue) or `200` (Red) |
| `team_position` | `str` | Role (`TOP`, `JUNGLE`, `MIDDLE`, `BOTTOM`, `UTILITY`) |
| `champion_name` | `str` | Champion name |
| `win` | `int` | Target: `1` for Win, `0` for Defeat |
| `kda` | `float` | `(kills + assists) / max(1, deaths)` |
| `damage_dealt_to_buildings` | `int` | **Damage to turrets & inhibitors** (Split-push indicator) |
| `damage_dealt_to_objectives` | `int` | Damage to Dragons, Barons, Heralds, Voidgrubs |
| `time_ccing_others` | `int` | **Crowd control score** (Frontline/Engage indicator) |
| `gold_per_minute` | `float` | Individual gold generation rate |
| `cs_per_minute` | `float` | Farming pace |
| `vision_score` | `int` | Vision contribution score |
| `item0` .. `item6` | `int` | Equipped item IDs |
| `primary_rune_tree` | `int` | Primary Perk tree ID |
| `secondary_rune_tree` | `int` | Secondary Perk tree ID |

---

## 🧪 Testing

Run unit and integration test suite:
```bash
pytest -v
```
