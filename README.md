# League of Legends Ranked Dataset Pipeline

Automated, resilient, and rate-limit compliant interactive CLI and data extraction pipeline designed to harvest League of Legends match datasets across configurable regions, ranked tiers, queues, and gameplay filters using the official Riot Games API for academic research and machine learning applications.

[Versao em Portugues (README.pt-BR.md)](README.pt-BR.md)

---

## 1. Overview

The pipeline extracts granular match and participant statistics, normalizing the raw Riot API payload into a structured tabular dataset containing **108 features per participant** (up to 10 rows per match).

### Key Features
- **Interactive CLI & Pre-Request Filter Wizard:** Configure regions, ranked tiers, divisions, queues, time windows, match durations, surrender exclusions, champions, roles, map side, and discovery modes interactively before dispatching any API requests.
- **Full Ranked Tier & Multi-Region Coverage:** Harvests player seeds across Apex tiers (`CHALLENGER`, `GRANDMASTER`, `MASTER`) and Standard tiers (`DIAMOND` through `IRON`, divisions `I` to `IV`), supporting single or multi-platform runs (`BR1,KR,NA1,EUW1`, etc.).
- **Rate Limit Compliance:** Sliding-window token bucket limiter enforcing both Riot short (20 req/1s) and long (100 req/120s) rate limits with a 10% safety margin, combined with reactive backoff for HTTP 429 (`Retry-After`).
- **Player Diversity Modes:** Choose between breadth-first Snowball Graph discovery (enqueuing match participants) or strict seed-tier-only crawling (`--no-discover`).
- **Checkpointing & Deduplication:** Atomic state persistence (`data/state_<platform>.json`) preventing duplicate queries and supporting pause/resume.
- **Dual Storage & Offline Filtering:** Synchronous writing to columnar Snappy-compressed Apache Parquet and CSV, plus an offline `filter` command to slice and export existing datasets.

---

## 2. Directory Layout

```
ml-lol/
├── .context/
│   ├── 01-spec.md               # Functional specifications and dataset schema
│   ├── 02-plan.md               # Architecture design and module responsibilities
│   └── 03-tasks.md              # Engineering checklist and verification records
├── .env                         # Local environment configuration (gitignored)
├── .env.example                 # Environment template
├── .gitignore                   # Version control exclusion rules
├── README.md                    # Project documentation (English)
├── README.pt-BR.md              # Project documentation (Portuguese)
├── requirements.txt             # Pinned project dependencies
├── pyproject.toml               # Python packaging metadata
├── data/
│   ├── README.md                # Dataset dictionary and codebook (English)
│   ├── README.pt-BR.md          # Dataset dictionary and codebook (Portuguese)
│   ├── ranked_matches.parquet   # Compressed columnar dataset
│   ├── ranked_matches.csv       # Delimited tabular dataset
│   └── state_br1.json           # Crawler state and checkpoint tracker
├── src/
│   ├── main.py                  # CLI entry point (interactive, collect, filter, export, status)
│   ├── cli/
│   │   └── interactive.py       # Interactive menus, filter wizard & pre-flight summary
│   ├── config/settings.py       # Pydantic environment configuration
│   ├── core/
│   │   ├── rate_limiter.py      # Dual-window Token Bucket rate limiter
│   │   ├── http_client.py       # Resilient HTTP client with backoff
│   │   └── exceptions.py        # Domain exception classes
│   ├── riot/
│   │   ├── routing.py           # Platform to regional cluster mapper
│   │   ├── league_api.py        # League-v4 seed harvester (Apex & Standard tiers)
│   │   └── match_api.py         # Match-v5 match list and details fetcher
│   ├── models/
│   │   ├── api_models.py        # Raw Riot API DTO models
│   │   ├── dataset_models.py    # 108-feature tabular schema model
│   │   └── filter_models.py     # CollectionFilterConfig & DatasetFilterConfig schemas
│   └── pipeline/
│       ├── normalizer.py        # Feature extraction & match/participant filter engine
│       ├── state_manager.py     # Checkpointing and deduplication manager
│       ├── storage.py           # Atomic Parquet/CSV writer and offline filter exporter
│       └── orchestrator.py      # Single/multi-platform pipeline orchestrator
└── tests/                       # Unit and integration test suite
```

---

## 3. Installation & Setup

### Requirements
- Python 3.11 or higher
- Valid Riot Games API Key ([Riot Developer Portal](https://developer.riotgames.com/))

### Steps
1. Clone the repository and navigate to the project root:
   ```bash
   git clone <repository_url>
   cd ml-lol
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and insert your Riot API key:
   ```env
   RIOT_API_KEY=RGAPI-your-api-key-here
   DEFAULT_PLATFORM=BR1
   DEFAULT_REGION=americas
   TARGET_QUEUE_ID=420
   ```

---

## 4. Usage

### 4.1 Interactive CLI Mode (Recommended)

Run the script with no arguments (or with `interactive` / `collect -i`) to open the interactive menu and step-by-step filter wizard. No Riot API requests are sent until you review the configuration summary and confirm:

```bash
# Open interactive main menu
python3 src/main.py

# Or jump directly into the interactive filter wizard
python3 src/main.py collect -i
```

### 4.2 Flag-Based Data Collection & Filter Options

You can also pass all filters directly as CLI flags (useful for automation or background runs with `-y` to skip the confirmation prompt):

```bash
# Multi-region collection (Brazil + Korea), Diamond+ only, last 7 days, no surrenders
python3 src/main.py collect -p BR1,KR --tiers CHALLENGER,GRANDMASTER,MASTER,DIAMOND --divisions I --days-back 7 --exclude-surrenders --hours 8.0 -y

# Collect 200 matches featuring specific champions on patch 14.4
python3 src/main.py collect -p BR1 --patch 14.4 --champions Ahri,LeeSin --positions MIDDLE,JUNGLE -n 200 -y

# Strict mode: query only Challenger players without discovering teammates/opponents
python3 src/main.py collect -p BR1 --only-challenger --no-discover --dataset-name challenger_strict -y

# Run in background on Linux
nohup python3 src/main.py collect --hours 8.0 -y > crawler.log 2>&1 &
```

#### Available `collect` Filter Flags

| Flag | Description | Default |
| :--- | :--- | :--- |
| `-i, --interactive` | Launch interactive filter wizard before collecting | `False` |
| `-p, --platform` | Single or comma-separated platforms (e.g. `BR1`, `BR1,KR,NA1`) | `BR1` |
| `-r, --region` | Regional routing override for single platform (`americas`, `europe`, `asia`, `sea`) | Auto-resolved |
| `--tiers` | Comma-separated tiers (`CHALLENGER` down to `IRON`) | `CHALLENGER,GRANDMASTER,MASTER` |
| `--divisions` | Comma-separated divisions for standard tiers (`I,II,III,IV`) | `I` |
| `--max-pages` | Max API pages per division for standard tiers (`1`-`20`) | `1` |
| `-q, --queue` | Queue ID (`420`: Solo/Duo, `440`: Flex, `400`: Normal, `450`: ARAM, `0`: All) | `420` |
| `--match-type` | Match-v5 type (`ranked`, `normal`, `tourney`, `tutorial`, `all`) | Auto-inferred |
| `--days-back` | Only collect matches from the last N days | None |
| `--start-time` / `--end-time` | Epoch timestamp bounds in seconds for Match-v5 | None |
| `--min-duration` / `--max-duration` | Match duration bounds in seconds | `300` / None |
| `--exclude-surrenders` | Skip matches that ended in surrender | `False` |
| `--patch` | Filter by game version prefix (e.g. `14.4`) | None |
| `--champions` | Comma-separated champion names to filter matches by | None |
| `--positions` | Comma-separated roles (`TOP,JUNGLE,MIDDLE,BOTTOM,UTILITY`) | None |
| `--side` | Filter participant map side (`BLUE` or `RED`) | None |
| `--no-discover` | Disable snowball participant discovery (seed players only) | `False` |
| `--hours` | Maximum execution duration in hours (`0` for unlimited) | `8.0` |
| `-n, --target-matches` | Target number of unique matches to collect | Unlimited |
| `--format` | Output format (`both`, `parquet`, `csv`) | `both` |
| `--dataset-name` | Output filename prefix inside `data/` | `ranked_matches` |
| `--max-per-player` | Max matches sampled per player (`1`-`100`) | `10` |
| `--only-challenger` | Shortcut for `--tiers CHALLENGER` | `False` |
| `--reset-state` | Clear checkpoint state before starting | `False` |
| `-y, --yes` | Skip confirmation prompt | `False` |

### 4.3 Offline Dataset Filtering

Filter an already collected Parquet or CSV dataset without making any API calls:

```bash
python3 src/main.py filter --champions Ahri,Orianna --positions MIDDLE --side BLUE --win 1 --min-duration 1200 -o data/ahri_blue_wins.csv
```

### 4.4 Status Inspection
View collected matches, visited players, queue size, and dataset file sizes:
```bash
python3 src/main.py status
```

### 4.5 Exporting Parquet to CSV
Export the accumulated Parquet dataset to CSV at any time:
```bash
python3 src/main.py export -o data/ranked_matches.csv
```

---

## 5. Testing

Execute the automated test suite:
```bash
pytest -v
```

---

## 6. Dataset Documentation

Detailed definitions for all 108 features, data types, and reference code tables are available in:
- [data/README.md](data/README.md) (English)
- [data/README.pt-BR.md](data/README.pt-BR.md) (Portuguese)
