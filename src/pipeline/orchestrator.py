"""Pipeline orchestrator coordinating seed harvesting, match crawling, feature extraction, and storage."""

import signal
import sys
import time
from typing import Optional
from loguru import logger
from tqdm import tqdm

from src.config.settings import Settings
from src.core.http_client import ResilientHTTPClient
from src.core.rate_limiter import SlidingWindowRateLimiter
from src.pipeline.normalizer import MatchNormalizer
from src.pipeline.state_manager import StateManager
from src.pipeline.storage import BatchStorage
from src.riot.league_api import LeagueAPIClient
from src.riot.match_api import MatchAPIClient
from src.riot.routing import platform_to_region


class MatchPipelineOrchestrator:
    """Orchestrates continuous ranked match collection with player diversity, deduplication, and rate-limiting."""

    def __init__(
        self,
        settings: Settings,
        platform: Optional[str] = None,
        region: Optional[str] = None,
        queue_id: Optional[int] = None,
        output_format: Optional[str] = None,
        max_matches_per_player: Optional[int] = None,
    ) -> None:
        self.settings = settings
        self.platform = (platform or settings.default_platform).upper()
        self.region = (region or platform_to_region(self.platform)).lower()
        self.queue_id = queue_id if queue_id is not None else settings.target_queue_id
        self.max_matches_per_player = max_matches_per_player or settings.max_matches_per_player

        # Rate Limiter with safety margins
        self.rate_limiter = SlidingWindowRateLimiter(
            short_limit=settings.rate_limit_short_max,
            short_window_sec=settings.rate_limit_short_window_sec,
            long_limit=settings.rate_limit_long_max,
            long_window_sec=settings.rate_limit_long_window_sec,
            safety_margin=settings.rate_limit_safety_margin,
        )

        # HTTP and Riot clients
        self.http_client = ResilientHTTPClient(
            api_key=settings.riot_api_key.get_secret_value(),
            rate_limiter=self.rate_limiter,
        )
        self.league_api = LeagueAPIClient(self.http_client, platform=self.platform)
        self.match_api = MatchAPIClient(self.http_client, region=self.region)

        # State and Storage
        state_path = settings.data_dir / f"state_{self.platform.lower()}.json"
        self.state_manager = StateManager(state_path)
        self.storage = BatchStorage(
            data_dir=settings.data_dir,
            output_format=output_format or settings.output_format,  # type: ignore
            batch_size_matches=settings.batch_size,
        )
        self.normalizer = MatchNormalizer()

        self._shutdown_requested = False
        self._setup_signals()

    def _setup_signals(self) -> None:
        """Register graceful shutdown handlers."""
        def handler(sig, frame):
            logger.warning("\nShutdown signal received! Finishing current batch and saving state...")
            self._shutdown_requested = True

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def run(
        self,
        target_matches: Optional[int] = None,
        max_duration_hours: Optional[float] = None,
        include_grandmaster: bool = True,
        include_master: bool = True,
    ) -> None:
        """Execute continuous match crawler."""
        logger.info("=" * 60)
        logger.info(f"Starting League of Legends Match Crawler [{self.platform} -> {self.region}]")
        logger.info(f"Queue ID: {self.queue_id} (Ranked Solo/Duo)")
        logger.info(f"Target Matches: {target_matches or 'Continuous'}")
        logger.info(f"Max Duration: {f'{max_duration_hours:.1f} hours' if max_duration_hours else 'Unlimited'}")
        logger.info(f"Storage: {self.storage.parquet_path} (Format: {self.storage.output_format})")
        logger.info("=" * 60)

        # 1. Populate seeds if queue is empty
        if not self.state_manager.queued_puuids:
            seed_puuids = self.league_api.harvest_seed_puuids(
                queue="RANKED_SOLO_5x5" if self.queue_id == 420 else "RANKED_FLEX_SR",
                include_grandmaster=include_grandmaster,
                include_master=include_master,
            )
            added = self.state_manager.add_queued_puuids(seed_puuids)
            self.state_manager.save_state()
            logger.info(f"Enqueued {added} initial player seeds.")

        start_time = time.time()
        max_seconds = max_duration_hours * 3600.0 if max_duration_hours else None
        matches_collected_session = 0

        pbar = tqdm(
            total=target_matches,
            desc="Matches Collected",
            unit="match",
            dynamic_ncols=True,
        )

        try:
            while not self._shutdown_requested:
                # Check duration limit
                elapsed_sec = time.time() - start_time
                if max_seconds and elapsed_sec >= max_seconds:
                    logger.info(f"Reached configured duration limit ({max_duration_hours} hours). Stopping.")
                    break

                # Check match limit
                if target_matches and matches_collected_session >= target_matches:
                    logger.info(f"Reached target match count ({target_matches}). Stopping.")
                    break

                # Get next player from queue
                puuid = self.state_manager.pop_next_puuid()
                if not puuid:
                    logger.info("Queue is empty. Refreshing apex seeds...")
                    seed_puuids = self.league_api.harvest_seed_puuids(
                        include_grandmaster=True,
                        include_master=include_master,
                    )
                    added = self.state_manager.add_queued_puuids(seed_puuids)
                    if added == 0:
                        logger.warning("No new seeds discovered. Sleeping 60s before retrying...")
                        time.sleep(60)
                    continue

                # Fetch match IDs for this player
                try:
                    match_ids = self.match_api.get_match_ids_by_puuid(
                        puuid=puuid,
                        queue=self.queue_id,
                        count=self.max_matches_per_player,
                    )
                except Exception as err:
                    logger.warning(f"Error fetching match list for PUUID {puuid[:8]}...: {err}")
                    self.state_manager.mark_puuid_visited(puuid)
                    continue

                # Process unique matches
                for match_id in match_ids:
                    if self._shutdown_requested:
                        break

                    if self.state_manager.is_match_processed(match_id):
                        continue

                    # Fetch match detail
                    try:
                        raw_match = self.match_api.get_match_by_id(match_id)
                    except Exception as err:
                        logger.warning(f"Failed to fetch match {match_id}: {err}")
                        self.state_manager.mark_match_failed(match_id)
                        continue

                    # Normalize and extract ML features
                    records = self.normalizer.normalize_match(raw_match)
                    if records:
                        self.storage.add_records(records)
                        self.state_manager.mark_match_processed(match_id)
                        matches_collected_session += 1
                        pbar.update(1)

                        # Enqueue newly discovered participants for player diversity
                        discovered_puuids = [r.puuid for r in records]
                        self.state_manager.add_queued_puuids(discovered_puuids)
                    else:
                        self.state_manager.mark_match_failed(match_id)

                    # Periodically save state
                    if matches_collected_session % 10 == 0:
                        self.state_manager.save_state()

                self.state_manager.mark_puuid_visited(puuid)

        finally:
            pbar.close()
            logger.info("Flushing final records and saving state...")
            self.storage.flush()
            self.state_manager.save_state()
            self.http_client.close()

            total_time_min = (time.time() - start_time) / 60.0
            logger.info(
                f"Crawl session completed in {total_time_min:.1f} minutes. "
                f"Collected {matches_collected_session} matches "
                f"({matches_collected_session * 10} participant rows). "
                f"Total dataset size: {self.storage.total_rows} rows."
            )
