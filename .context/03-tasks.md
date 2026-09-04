# Execution Task Checklist: League of Legends ML Dataset Pipeline

This checklist outlines the atomic execution steps required to build, test, and verify the data collection and ML dataset generation pipeline.

---

## Phase 1: Environment, Security & Configuration

- [x] **Task 1.1: Project Skeleton & Dependency Management**
  - Create project directory layout (`src/`, `tests/`, `data/`).
  - Create `pyproject.toml` or `requirements.txt` with pinned dependencies (`httpx`, `pydantic`, `pydantic-settings`, `pandas`, `pyarrow`, `loguru`, `pytest`, `pytest-mock`, `respx`, `tqdm`).
  - Create `.gitignore` to explicitly ignore `.env`, `data/`, `*.parquet`, `*.csv`, `__pycache__/`, `.pytest_cache/`.
  - Create `.env.example` with template variables (`RIOT_API_KEY`, `DEFAULT_PLATFORM`, `DEFAULT_REGION`, `TARGET_QUEUE_ID`, `BATCH_SIZE`).
  - **Verification:** Run `pytest --version` and verify no syntax or dependency issues.

- [x] **Task 1.2: Settings & Secret Validation Module**
  - Implement `src/config/settings.py` using `pydantic-settings` to load and validate environment variables.
  - Implement key validation (checking key prefix, length, and preventing empty strings).
  - Add secret masking in `__repr__` and logging to ensure secrets are never leaked.
  - **Verification:** Unit tests in `tests/test_config.py` verifying correct parsing and error raising on missing/invalid keys.

---

## Phase 2: Resilient HTTP Client & Rate Limiting

- [x] **Task 2.1: Dual-Window Token Bucket Rate Limiter**
  - Implement `src/core/rate_limiter.py` managing both 1-second (20 req) and 120-second (100 req) sliding windows.
  - Implement thread-safe token acquisition and synchronization methods.
  - Support dynamic header updates from `X-App-Rate-Limit` and `X-App-Rate-Limit-Count`.
  - **Verification:** Unit tests in `tests/test_rate_limiter.py` simulating bursts and asserting correct sleep durations.

- [x] **Task 2.2: Resilient HTTP Client Wrapper**
  - Implement `src/core/http_client.py` wrapping `httpx.Client` with automatic rate limiter integration.
  - Implement retry logic with exponential backoff and jitter for network failures and HTTP 5xx errors.
  - Implement reactive handling of HTTP 429 using `Retry-After` header.
  - Implement strict error handling for HTTP 401/403 (Invalid/Expired API Key) with clear user feedback.
  - **Verification:** Mock tests in `tests/test_http_client.py` using `respx` simulating 200 OK, 429 Too Many Requests, and 503 Service Unavailable.

---

## Phase 3: Riot API Domain Modules & Routing

- [x] **Task 3.1: Region & Platform Routing Mapping**
  - Implement `src/riot/routing.py` to map platform identifiers (e.g., `BR1`, `NA1`, `EUW1`) to their corresponding regional routing endpoints (`americas`, `europe`, `asia`).
  - **Verification:** Unit tests in `tests/test_routing.py` ensuring correct mapping and raising ValueError on unsupported regions.

- [x] **Task 3.2: League-v4 Seed Harvester**
  - Implement `src/riot/league_api.py` to query high-tier ranked leagues (`/lol/league/v4/challengerleagues/by-queue/{queue}`, `grandmasterleagues`, `masterleagues`) to harvest seed player PUUIDs/summoner IDs.
  - **Verification:** Unit tests with mocked League-v4 JSON responses in `tests/test_league_api.py`.

- [x] **Task 3.3: Match-v5 Match History & Details Fetcher**
  - Implement `src/riot/match_api.py` with:
    - Method to fetch match IDs for a given PUUID filtered by queue (e.g., queue `420` for Solo/Duo).
    - Method to fetch complete match details by `matchId`.
  - **Verification:** Unit tests with mocked Match-v5 responses in `tests/test_match_api.py`.

---

## Phase 4: Data Models & ML Feature Normalization

- [x] **Task 4.1: Pydantic Data Models & Validation**
  - Implement `src/models/api_models.py` for raw Riot API response schemas.
  - Implement `src/models/dataset_models.py` specifying the exact tabular schema for ML participant records (damage to buildings/turrets, individual gold, vision, KDA, items, runes, win/loss).
  - **Verification:** Unit tests parsing sample Riot match JSON into validated models.

- [x] **Task 4.2: Feature Normalizer & Extractor**
  - Implement `src/pipeline/normalizer.py` to extract and compute derived features (e.g., KDA, CS per minute, gold per minute, building damage) for all 10 participants per match.
  - Ensure missing or optional fields are safely imputed with default values without breaking execution.
  - **Verification:** Unit tests in `tests/test_normalizer.py` verifying accurate feature calculation against known match payloads.

---

## Phase 5: State Persistence & Storage Engine

- [x] **Task 5.1: State Manager & Deduplication Tracker**
  - Implement `src/pipeline/state_manager.py` using JSON / SQLite to record visited PUUIDs, queued PUUIDs, and processed match IDs.
  - Provide resume capability so interrupting and restarting the pipeline never re-queries existing matches.
  - **Verification:** Unit tests in `tests/test_state_manager.py` asserting state persistence and deduplication logic.

- [x] **Task 5.2: Parquet / CSV Batch Storage Engine**
  - Implement `src/pipeline/storage.py` to accumulate participant records in memory batches and append them to a partitioned or unified `data/ranked_matches.parquet` (with optional CSV export).
  - Enforce atomic file writes to prevent corrupted datasets.
  - **Verification:** Unit tests in `tests/test_storage.py` testing batch writes, file creation, and schema consistency with `pyarrow` / `pandas`.

---

## Phase 6: Pipeline Orchestration & CLI Interface

- [x] **Task 6.1: Pipeline Orchestrator**
  - Implement `src/pipeline/orchestrator.py` integrating Seed Harvesting -> Match ID Queuing -> Match Fetching -> Feature Normalization -> Batch Storage -> State Saving.
  - Add interactive progress reporting using `tqdm` (showing matches collected, requests/sec, and rate limit status).
  - **Verification:** Integration tests with mocked end-to-end API calls.

- [x] **Task 6.2: CLI Interface Entry Point**
  - Implement `src/main.py` allowing command-line arguments:
    - `--region` (default: `BR1`)
    - `--queue` (default: `420` - Ranked Solo)
    - `--target-matches` (e.g., `100`, `1000`)
    - `--output-format` (`parquet` or `csv`)
    - `--reset-state` (flag to clear checkpoint)
  - **Verification:** Test CLI execution with `--help` and dry-run parameters.

---

## Phase 7: Verification, Documentation & ML Readiness

- [x] **Task 7.1: End-to-End Live / Mock Verification**
  - Run the full test suite (`pytest -v --cov=src`).
  - Execute a test run against Riot API with a valid key for a small sample (e.g., 5 matches), validating generated Parquet file contents and column schemas.
  - **Verification:** Load generated `data/ranked_matches.parquet` with pandas and assert 0 nulls on critical features and exactly 10 rows per match.

- [x] **Task 7.2: Champion Clustering & Playstyle Exploration Notebook**
  - Create a starter Jupyter notebook / exploration script (`notebooks/01_champion_clustering.ipynb` or `src/ml/clustering.py`).
  - Compute normalized champion feature profiles (damage split %, objective focus, turret focus, CC score, gold share).
  - Run baseline clustering algorithms (e.g., K-Means / PCA / UMAP) to identify distinct champion playstyle archetypes (e.g., Split-pushers, Engage Frontline, Enchanters, Poke, Assassins).
  - Aggregate team composition archetypes to demonstrate team playstyle classification feasibility.
  - **Verification:** Generate cluster visual plots and cluster summary tables.

- [x] **Task 7.3: Comprehensive Documentation & Setup Guide**
  - Create `README.md` containing:
    - Setup instructions (virtualenv, installation, `.env` setup).
    - How to get a Riot API key and configure it.
    - CLI usage examples.
    - Detailed dataset column dictionary and ML use-case suggestions.
  - **Verification:** Review documentation for completeness and clarity.
