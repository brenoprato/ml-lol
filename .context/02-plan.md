# Technical Plan & Architecture: League of Legends Academic Dataset Pipeline

## 1. System Architecture Overview

The system is designed as a modular, resilient pipeline following Clean Architecture and SOLID principles:

```mermaid
flowchart TD
    subgraph Configuration & Secrets
        ENV[".env / Environment Variables"] --> Config[Settings Config (Pydantic Settings)]
    end

    subgraph Core Network & Rate Limiting
        Config --> RateLimiter[Sliding Window Rate Limiter (Dual Token Bucket)]
        RateLimiter --> HTTPClient[Resilient HTTP Client (Retry, Backoff, 429 Handler)]
        HTTPClient --> RiotAPI[Riot Games API Endpoints]
    end

    subgraph Ingestion & Crawling
        RiotAPI --> SeedHarvest[League-v4: Challenger / GM / Master Seeds]
        SeedHarvest --> MatchCrawler[Match-v5: Player Match Histories & Details]
        MatchCrawler --> StateTracker[(State Manager: Visited PUUIDs & Processed Matches)]
    end

    subgraph Normalization & ML Feature Extraction
        MatchCrawler --> Normalizer[Match Normalizer: 108 Granular Features Extractor]
        Normalizer --> DatasetValidator[Pydantic MLParticipantRecord Schema Validator]
    end

    subgraph Storage & Output Engine
        DatasetValidator --> BatchBuffer[Batch Storage Buffer]
        BatchBuffer --> ParquetWriter[Atomic Parquet Writer (Snappy Compressed)]
        BatchBuffer --> CSVWriter[CSV Appender / Exporter]
        ParquetWriter --> ParquetDataset[(data/ranked_matches.parquet)]
        CSVWriter --> CSVDataset[(data/ranked_matches.csv)]
    end
```

---

## 2. Directory Structure & Module Layout

All code, variables, functions, and logs are written strictly in **English**.

```
ml-lol/
├── .context/
│   ├── 01-spec.md               # Functional requirements & full 108 feature schema
│   ├── 02-plan.md               # Architecture, module descriptions & workflow
│   └── 03-tasks.md              # Task checklist & verification status
├── .env                         # Local configuration with Riot API Key (gitignored)
├── .env.example                 # Template configuration file
├── .gitignore                   # Excludes .env, data/, cache, and binaries
├── README.md                    # Setup and execution guide
├── pyproject.toml               # Project metadata and dependencies
├── requirements.txt             # Pinned pip requirements
├── data/                        # Generated datasets and checkpoints (gitignored)
│   ├── ranked_matches.parquet   # Primary compressed columnar dataset
│   ├── ranked_matches.csv       # Spreadsheet-ready CSV dataset
│   └── state_br1.json           # Checkpoint state (visited players, processed matches)
├── src/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py          # Pydantic Settings, secret masking & validation
│   ├── core/
│   │   ├── __init__.py
│   │   ├── exceptions.py        # Domain exceptions (Authentication, RateLimit, etc.)
│   │   ├── rate_limiter.py      # Dual-window Token Bucket rate limiter (safety margin)
│   │   └── http_client.py       # Resilient HTTP Client (exponential backoff & 429 sync)
│   ├── riot/
│   │   ├── __init__.py
│   │   ├── routing.py           # Platform (BR1, KR, NA1) to Region routing mapper
│   │   ├── league_api.py        # League-v4 client (Challenger, GM, Master harvesting)
│   │   └── match_api.py         # Match-v5 client (Match history & Match detail fetcher)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── api_models.py        # Raw Riot API DTO models (MatchDTO, ParticipantDTO)
│   │   └── dataset_models.py    # Tabular 108-feature schema (MLParticipantRecord)
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── normalizer.py        # Raw JSON to 108 ML features transformer
│   │   ├── state_manager.py     # Checkpoint tracker & match deduplicator
│   │   ├── storage.py           # Atomic Parquet & CSV batch writer
│   │   └── orchestrator.py      # Crawler coordinator with graceful shutdown
│   └── main.py                  # CLI Orchestrator (collect, export, status)
└── tests/
    ├── __init__.py
    ├── conftest.py              # Mock fixtures and sample match payloads
    ├── test_config.py           # Configuration tests
    ├── test_rate_limiter.py     # Rate limiter throttling & 429 tests
    ├── test_http_client.py      # HTTP client retry & mock tests
    ├── test_routing.py          # Platform to regional routing tests
    ├── test_normalizer.py       # Feature normalization tests
    ├── test_state_manager.py    # State persistence & deduplication tests
    ├── test_storage.py          # Parquet/CSV storage tests
    └── test_pipeline.py         # End-to-end mocked crawler integration test
```

---

## 3. Detailed Component Responsibilities

1. **`src/config/settings.py`**:
   - Loads environment variables from `.env` using `pydantic-settings`.
   - Validates `RIOT_API_KEY` format (`RGAPI-...`) and prevents empty strings.
   - Masks sensitive secrets from string representations and logs.

2. **`src/core/rate_limiter.py`**:
   - Implements a proactive sliding-log algorithm for both 1-second (20 req) and 120-second (100 req) windows.
   - Configured with a `0.9` safety margin to proactively throttle before reaching Riot's strict limits.
   - Reactively parses `X-App-Rate-Limit-Count` and handles `429 Too Many Requests` using the `Retry-After` header.

3. **`src/core/http_client.py`**:
   - Wraps `httpx.Client` with connection pooling and timeouts.
   - Injects the `X-Riot-Token` header.
   - Implements exponential backoff with random jitter for transient network or 5xx server errors.

4. **`src/riot/routing.py`**:
   - Maps platform identifiers (e.g. `BR1`, `NA1`, `EUW1`, `KR`, `JP1`) to their regional clusters (`americas`, `europe`, `asia`, `sea`).

5. **`src/riot/league_api.py`**:
   - Harvests player PUUIDs from apex ranked leagues (Challenger, Grandmaster, Master) for Ranked Solo/Duo (`RANKED_SOLO_5x5`).

6. **`src/riot/match_api.py`**:
   - Queries Match-v5 endpoints to retrieve match IDs for a player PUUID and download full match detail payloads.

7. **`src/pipeline/normalizer.py` & `src/models/dataset_models.py`**:
   - Parses the raw Match JSON and extracts all 108 granular features per participant (combat, damage, objectives, economy, vision, skillshots, spells, pings, runes, items, side, win/loss).

8. **`src/pipeline/state_manager.py`**:
   - Persists crawler state to `data/state_{platform}.json`.
   - Ensures no match is ever queried or saved twice.
   - Allows safe resume after interruption (`Ctrl+C`).

9. **`src/pipeline/storage.py`**:
   - Buffers participant rows in RAM batches.
   - Flushes atomically to `data/ranked_matches.parquet` using Snappy compression and appends to `data/ranked_matches.csv`.

10. **`src/pipeline/orchestrator.py`**:
    - Coordinates breadth-first player traversal for high diversity.
    - Handles duration and match limits.
    - Captures `SIGINT` (Ctrl+C) / `SIGTERM` to safely flush buffered data before exiting.

11. **`src/main.py`**:
    - CLI entry point supporting `collect`, `export`, and `status` subcommands.
