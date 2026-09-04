# League of Legends Ranked Dataset Pipeline

Automated, resilient, and rate-limit compliant data extraction pipeline designed to harvest high-tier League of Legends ranked match datasets (Challenger, Grandmaster, Master) using the official Riot Games API for academic research and machine learning applications.

[Versao em Portugues (README.pt-BR.md)](README.pt-BR.md)

---

## 1. Overview

The pipeline extracts granular match and participant statistics from high-MMR matches, normalizing the raw API payload into a structured tabular dataset containing **108 features per participant** (10 rows per match).

### Key Features
- **Rate Limit Compliance:** Sliding-window token bucket limiter enforcing both Riot short (20 req/1s) and long (100 req/120s) rate limits with a 10% safety margin, combined with reactive backoff for HTTP 429 (`Retry-After`).
- **Player Diversity:** Breadth-first graph traversal starting from Apex tier player seeds (Challenger, Grandmaster, Master) and discovering match participants dynamically.
- **Checkpointing & Deduplication:** Atomic state persistence (`data/state_<platform>.json`) preventing duplicate queries and supporting pause/resume.
- **Dual Storage Persistence:** Synchronous writing to columnar Snappy-compressed Apache Parquet (`data/ranked_matches.parquet`) and standard tabular CSV (`data/ranked_matches.csv`).
- **Comprehensive Feature Set:** 108 columns per participant record covering identity, map side, combat, damage distribution, structures, early game economy, vision, skillshot mechanics, ability casts, pings, items, and runes.

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
│   ├── main.py                  # CLI entry point
│   ├── config/settings.py       # Pydantic environment configuration
│   ├── core/
│   │   ├── rate_limiter.py      # Dual-window Token Bucket rate limiter
│   │   ├── http_client.py       # Resilient HTTP client with backoff
│   │   └── exceptions.py        # Domain exception classes
│   ├── riot/
│   │   ├── routing.py           # Platform to regional cluster mapper
│   │   ├── league_api.py        # League-v4 seed harvester
│   │   └── match_api.py         # Match-v5 match list and details fetcher
│   ├── models/
│   │   ├── api_models.py        # Raw Riot API DTO models
│   │   └── dataset_models.py    # 108-feature tabular schema model
│   └── pipeline/
│       ├── normalizer.py        # Feature extraction and transformation engine
│       ├── state_manager.py     # Checkpointing and deduplication manager
│       ├── storage.py           # Atomic Parquet and CSV writer
│       └── orchestrator.py      # Main pipeline orchestration loop
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

### 4.1 Data Collection

Run the collection pipeline with a duration limit:
```bash
# Run continuous crawler for 8 hours (default: Challenger, GM, Master from BR1)
python3 src/main.py collect --hours 8.0

# Run in background on Linux
nohup python3 src/main.py collect --hours 8.0 > crawler.log 2>&1 &
```

Collect from other regional platforms:
```bash
# Korea (KR)
python3 src/main.py collect -p KR --hours 8.0

# North America (NA1)
python3 src/main.py collect -p NA1 --hours 8.0

# Europe West (EUW1)
python3 src/main.py collect -p EUW1 --hours 8.0
```

Collect a fixed number of matches:
```bash
python3 src/main.py collect -n 500
```

### 4.2 Status Inspection
View collected matches, visited players, queue size, and dataset file sizes:
```bash
python3 src/main.py status
```

### 4.3 Exporting Parquet to CSV
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
