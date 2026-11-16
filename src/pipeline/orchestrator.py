"""Pipeline orchestrator coordinating seed harvesting, match crawling, feature extraction, and storage."""

import signal
import threading
import time
from typing import Optional
from loguru import logger
from tqdm import tqdm

from src.config.settings import Settings
from src.core.http_client import ResilientHTTPClient
from src.core.rate_limiter import SlidingWindowRateLimiter
from src.models.filter_models import CollectionFilterConfig, QUEUE_MAP
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
        filter_config: Optional[CollectionFilterConfig] = None,
    ) -> None:
        self.settings = settings
        self.filter_config = filter_config

        default_plat = filter_config.platforms[0] if filter_config else settings.default_platform
        self.platform = (platform or default_plat).upper()
        self.region = (region or platform_to_region(self.platform)).lower()

        if queue_id is not None:
            self.queue_id: Optional[int] = queue_id
        elif filter_config is not None:
            self.queue_id = filter_config.queue_id
        else:
            self.queue_id = settings.target_queue_id

        if max_matches_per_player is not None:
            self.max_matches_per_player = max_matches_per_player
        elif filter_config is not None:
            self.max_matches_per_player = filter_config.max_matches_per_player
        else:
            self.max_matches_per_player = settings.max_matches_per_player

        resolved_format = output_format or (
            filter_config.output_format if filter_config else settings.output_format
        )
        dataset_name = filter_config.dataset_name if filter_config else "ranked_matches"

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
            output_format=resolved_format,  # type: ignore[arg-type]
            batch_size_matches=settings.batch_size,
            dataset_name=dataset_name,
        )
        self.normalizer = MatchNormalizer()

        self._shutdown_requested = False
        self.last_session_matches = 0
        self._setup_signals()

    @property
    def shutdown_requested(self) -> bool:
        """Whether a termination signal was received during execution."""
        return self._shutdown_requested

    def _setup_signals(self) -> None:
        """Register graceful shutdown handlers when running on main thread."""
        if threading.current_thread() is not threading.main_thread():
            return

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
        """Execute continuous match crawler with configured filters."""
        cfg = self.filter_config
        eff_target_matches = (
            target_matches if target_matches is not None else (cfg.target_matches if cfg else None)
        )
        eff_max_hours = (
            max_duration_hours
            if max_duration_hours is not None
            else (cfg.max_duration_hours if cfg else None)
        )
        tiers = cfg.tiers if cfg else None
        divisions = cfg.divisions if cfg else None
        max_pages = cfg.max_pages_per_division if cfg else 1
        league_queue = (
            cfg.league_queue_name
            if cfg
            else ("RANKED_FLEX_SR" if self.queue_id == 440 else "RANKED_SOLO_5x5")
        )
        match_type = cfg.match_type if cfg else "ranked"
        start_time = cfg.start_time if cfg else None
        end_time = cfg.end_time if cfg else None
        min_dur = cfg.min_duration_sec if cfg else 300
        max_dur = cfg.max_duration_sec if cfg else None
        exclude_surrenders = cfg.exclude_surrenders if cfg else False
        patch_prefix = cfg.patch_prefix if cfg else None
        champions = cfg.champions if cfg else None
        positions = cfg.positions if cfg else None
        side = cfg.side if cfg else None
        discover_participants = cfg.discover_participants if cfg else True

        queue_label = QUEUE_MAP.get(self.queue_id, str(self.queue_id)) if self.queue_id else "All"
        tiers_label = ", ".join(tiers) if tiers else (
            "CHALLENGER"
            + (", GRANDMASTER" if include_grandmaster else "")
            + (", MASTER" if include_master else "")
        )

        logger.info("=" * 60)
        logger.info(f"Starting League of Legends Match Crawler [{self.platform} -> {self.region}]")
        logger.info(f"Queue: {self.queue_id or 'All'} ({queue_label}) | Tiers: {tiers_label}")
        logger.info(f"Target Matches: {eff_target_matches or 'Continuous'}")
        logger.info(
            f"Max Duration: {f'{eff_max_hours:.2f} hours' if eff_max_hours else 'Unlimited'}"
        )
        logger.info(f"Storage: {self.storage.parquet_path} (Format: {self.storage.output_format})")
        logger.info("=" * 60)

        # 1. Populate seeds if queue is empty
        if not self.state_manager.queued_puuids:
            seed_puuids = self.league_api.harvest_seed_puuids(
                queue=league_queue,
                include_grandmaster=include_grandmaster,
                include_master=include_master,
                tiers=tiers,
                divisions=divisions,
                max_pages_per_division=max_pages,
            )
            added = self.state_manager.add_queued_puuids(seed_puuids)
            self.state_manager.save_state()
            logger.info(f"Enqueued {added} initial player seeds.")

        start_time_clock = time.time()
        max_seconds = eff_max_hours * 3600.0 if eff_max_hours else None
        matches_collected_session = 0
        self.last_session_matches = 0

        pbar = tqdm(
            total=eff_target_matches,
            desc=f"Matches [{self.platform}]",
            unit="match",
            dynamic_ncols=True,
        )

        try:
            while not self._shutdown_requested:
                elapsed_sec = time.time() - start_time_clock
                if max_seconds and elapsed_sec >= max_seconds:
                    logger.info(
                        f"Reached configured duration limit ({eff_max_hours:.2f} hours). Stopping."
                    )
                    break

                if eff_target_matches and matches_collected_session >= eff_target_matches:
                    logger.info(f"Reached target match count ({eff_target_matches}). Stopping.")
                    break

                puuid = self.state_manager.pop_next_puuid()
                if not puuid:
                    logger.info("Queue is empty. Refreshing configured tier seeds...")
                    seed_puuids = self.league_api.harvest_seed_puuids(
                        queue=league_queue,
                        include_grandmaster=include_grandmaster,
                        include_master=include_master,
                        tiers=tiers,
                        divisions=divisions,
                        max_pages_per_division=max_pages,
                    )
                    added = self.state_manager.add_queued_puuids(seed_puuids)
                    if added == 0:
                        if not discover_participants:
                            logger.info(
                                "All seed players have been visited and participant discovery is disabled. Stopping."
                            )
                            break
                        logger.warning("No new seeds discovered. Sleeping 60s before retrying...")
                        time.sleep(60)
                    continue

                try:
                    match_ids = self.match_api.get_match_ids_by_puuid(
                        puuid=puuid,
                        queue=self.queue_id,
                        count=self.max_matches_per_player,
                        match_type=match_type,
                        start_time=start_time,
                        end_time=end_time,
                    )
                except Exception as err:
                    logger.warning(f"Error fetching match list for PUUID {puuid[:8]}...: {err}")
                    self.state_manager.mark_puuid_visited(puuid)
                    continue

                for match_id in match_ids:
                    if self._shutdown_requested:
                        break
                    if eff_target_matches and matches_collected_session >= eff_target_matches:
                        break
                    if max_seconds and (time.time() - start_time_clock) >= max_seconds:
                        break

                    if self.state_manager.is_match_processed(match_id):
                        continue

                    try:
                        raw_match = self.match_api.get_match_by_id(match_id)
                    except Exception as err:
                        logger.warning(f"Failed to fetch match {match_id}: {err}")
                        self.state_manager.mark_match_failed(match_id)
                        continue

                    records = self.normalizer.normalize_match(
                        raw_match,
                        min_game_duration_sec=min_dur,
                        max_game_duration_sec=max_dur,
                        exclude_surrenders=exclude_surrenders,
                        patch_prefix=patch_prefix,
                        champions=champions,
                        positions=positions,
                        side=side,
                    )
                    if records:
                        self.storage.add_records(records)
                        self.state_manager.mark_match_processed(match_id)
                        matches_collected_session += 1
                        pbar.update(1)

                        if discover_participants:
                            discovered_puuids = [r.puuid for r in records]
                            self.state_manager.add_queued_puuids(discovered_puuids)
                    else:
                        self.state_manager.mark_match_failed(match_id)

                    if matches_collected_session > 0 and matches_collected_session % 10 == 0:
                        self.state_manager.save_state()

                self.state_manager.mark_puuid_visited(puuid)

        finally:
            self.last_session_matches = matches_collected_session
            pbar.close()
            logger.info("Flushing final records and saving state...")
            self.storage.flush()
            self.state_manager.save_state()
            self.http_client.close()

            total_time_min = (time.time() - start_time_clock) / 60.0
            logger.info(
                f"Crawl session completed in {total_time_min:.1f} minutes. "
                f"Collected {matches_collected_session} matches. "
                f"Total dataset size: {self.storage.total_rows} rows."
            )


def run_multi_platform_collection(settings: Settings, config: CollectionFilterConfig) -> None:
    """Execute collection across one or more configured platforms sequentially."""
    platforms = config.platforms
    remaining_matches = config.target_matches
    total_deadline = (
        time.time() + (config.max_duration_hours * 3600.0)
        if config.max_duration_hours
        else None
    )

    if config.reset_state:
        for plat in platforms:
            state_path = settings.data_dir / f"state_{plat.lower()}.json"
            if state_path.exists():
                state_path.unlink()
                logger.warning(f"Reset checkpoint state file: {state_path}")

    for idx, platform in enumerate(platforms):
        if remaining_matches is not None and remaining_matches <= 0:
            break

        per_platform_hours: Optional[float] = None
        if total_deadline is not None:
            remaining_sec = total_deadline - time.time()
            if remaining_sec <= 0:
                logger.info("Total duration budget exhausted before next platform. Stopping.")
                break
            platforms_left = len(platforms) - idx
            per_platform_hours = (remaining_sec / platforms_left) / 3600.0

        orchestrator = MatchPipelineOrchestrator(
            settings=settings,
            platform=platform,
            filter_config=config,
        )
        orchestrator.run(
            target_matches=remaining_matches,
            max_duration_hours=per_platform_hours,
        )

        if remaining_matches is not None:
            remaining_matches -= orchestrator.last_session_matches

        if orchestrator.shutdown_requested:
            logger.warning("Stopping multi-platform collection due to user shutdown request.")
            break
