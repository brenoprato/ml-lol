"""CLI entry point for League of Legends Match Data Collection & Dataset Generation."""

import argparse
from pathlib import Path
import sys
import time
from typing import Optional

# Ensure project root is on sys.path for direct script execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger
from pydantic import ValidationError

from src.cli.interactive import (
    confirm_collection_start,
    display_pre_flight_summary,
    print_dataset_status,
    prompt_collection_filters,
    run_interactive_cli,
)
from src.config.settings import get_settings
from src.models.filter_models import CollectionFilterConfig, DatasetFilterConfig
from src.pipeline.orchestrator import MatchPipelineOrchestrator, run_multi_platform_collection
from src.pipeline.storage import BatchStorage


def setup_logging(verbose: bool = False) -> None:
    """Configure structured logging with Loguru."""
    logger.remove()
    log_level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level=log_level,
        colorize=True,
    )


def _split_csv_arg(value: Optional[str]) -> list[str]:
    """Split a comma-separated CLI argument string into stripped non-empty items."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def build_filter_config_from_args(args: argparse.Namespace) -> CollectionFilterConfig:
    """Construct and validate CollectionFilterConfig from parsed CLI flags."""
    platforms = _split_csv_arg(args.platform) or ["BR1"]

    if args.only_challenger:
        tiers = ["CHALLENGER"]
    elif args.tiers:
        tiers = _split_csv_arg(args.tiers)
    else:
        tiers = ["CHALLENGER", "GRANDMASTER", "MASTER"]

    divisions = _split_csv_arg(args.divisions) or ["I"]
    champions = _split_csv_arg(args.champions)
    positions = _split_csv_arg(args.positions)

    queue_id: Optional[int] = None if args.queue == 0 else args.queue

    match_type: Optional[str]
    if args.match_type is not None:
        match_type = None if args.match_type.lower() == "all" else args.match_type.lower()
    elif queue_id in (400, 450):
        match_type = "normal"
    elif queue_id is None:
        match_type = None
    else:
        match_type = "ranked"

    start_time = args.start_time
    if start_time is None and args.days_back is not None and args.days_back > 0:
        start_time = int(time.time() - (args.days_back * 86400))

    max_hours: Optional[float] = None if (args.hours is not None and args.hours <= 0) else args.hours

    return CollectionFilterConfig(
        platforms=platforms,
        tiers=tiers,
        divisions=divisions,
        max_pages_per_division=args.max_pages,
        queue_id=queue_id,
        match_type=match_type,
        start_time=start_time,
        end_time=args.end_time,
        min_duration_sec=args.min_duration,
        max_duration_sec=args.max_duration,
        exclude_surrenders=args.exclude_surrenders,
        patch_prefix=args.patch,
        champions=champions,
        positions=positions,
        side=args.side,
        discover_participants=not args.no_discover,
        target_matches=args.target_matches,
        max_duration_hours=max_hours,
        max_matches_per_player=args.max_per_player,
        output_format=args.format,
        dataset_name=args.dataset_name,
        reset_state=args.reset_state,
    )


def cmd_collect(args: argparse.Namespace) -> None:
    """Run data collection pipeline in interactive or flag-driven mode."""
    settings = get_settings()

    if args.interactive:
        config = prompt_collection_filters()
        if config is None:
            return
        run_multi_platform_collection(settings, config)
        return

    try:
        config = build_filter_config_from_args(args)
    except ValidationError as err:
        logger.error(f"Invalid collection filter configuration:\n{err}")
        sys.exit(2)

    if not args.yes and sys.stdin.isatty():
        if not confirm_collection_start(config):
            logger.info("Collection cancelled by user. No API requests were made.")
            return
    else:
        display_pre_flight_summary(config)

    if args.region and len(config.platforms) == 1:
        if config.reset_state:
            state_path = settings.data_dir / f"state_{config.platforms[0].lower()}.json"
            if state_path.exists():
                state_path.unlink()
                logger.warning(f"Reset checkpoint state file: {state_path}")
        orchestrator = MatchPipelineOrchestrator(
            settings=settings,
            platform=config.platforms[0],
            region=args.region,
            filter_config=config,
        )
        orchestrator.run()
        return

    run_multi_platform_collection(settings, config)


def cmd_filter(args: argparse.Namespace) -> None:
    """Filter an existing dataset on disk and export matching records."""
    settings = get_settings()
    try:
        filter_cfg = DatasetFilterConfig(
            input_path=Path(args.input),
            output_path=Path(args.output),
            output_format=args.format,
            champions=_split_csv_arg(args.champions),
            positions=_split_csv_arg(args.positions),
            side=args.side,
            win=args.win,
            patch_prefix=args.patch,
            min_duration_sec=args.min_duration,
            max_duration_sec=args.max_duration,
        )
    except ValidationError as err:
        logger.error(f"Invalid dataset filter configuration:\n{err}")
        sys.exit(2)

    storage = BatchStorage(data_dir=settings.data_dir)
    rows, written_paths = storage.filter_and_export(
        output_path=filter_cfg.output_path,
        output_format=filter_cfg.output_format,
        input_path=filter_cfg.input_path,
        champions=filter_cfg.champions,
        positions=filter_cfg.positions,
        side=filter_cfg.side,
        win=filter_cfg.win,
        patch_prefix=filter_cfg.patch_prefix,
        min_duration_sec=filter_cfg.min_duration_sec,
        max_duration_sec=filter_cfg.max_duration_sec,
    )
    logger.info(
        f"Filtered export complete: {rows:,} rows written to {[str(p) for p in written_paths]}"
    )


def cmd_export(args: argparse.Namespace) -> None:
    """Export existing Parquet dataset to CSV."""
    settings = get_settings()
    storage = BatchStorage(data_dir=settings.data_dir, dataset_name=args.dataset_name)
    target_csv = Path(args.output) if args.output else None
    exported = storage.export_to_csv(target_csv)
    logger.info(f"Dataset exported to: {exported}")


def cmd_status(args: argparse.Namespace) -> None:
    """Display crawler progress and dataset statistics."""
    settings = get_settings()
    print_dataset_status(settings, args.platform)


def build_parser() -> argparse.ArgumentParser:
    """Create and configure the top-level CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="League of Legends ML Dataset Crawler & Filter-Driven CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", required=False)

    # Interactive Command
    subparsers.add_parser(
        "interactive",
        help="Launch interactive menu & filter wizard (default when run with no arguments)",
    )

    # Collect Command
    collect_parser = subparsers.add_parser(
        "collect",
        help="Start or resume match crawler with pre-request filter options",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    collect_parser.add_argument(
        "-i", "--interactive", action="store_true", help="Launch interactive filter wizard before collecting"
    )
    collect_parser.add_argument(
        "-p", "--platform", default="BR1", help="Platform(s) comma-separated (e.g. BR1 or BR1,KR,NA1)"
    )
    collect_parser.add_argument(
        "-r", "--region", default=None, help="Regional routing override for single platform (americas, europe, asia, sea)"
    )
    collect_parser.add_argument(
        "--tiers",
        default="CHALLENGER,GRANDMASTER,MASTER",
        help="Comma-separated ranked tiers (CHALLENGER..IRON)",
    )
    collect_parser.add_argument(
        "--divisions",
        default="I",
        help="Comma-separated divisions for standard tiers (I,II,III,IV)",
    )
    collect_parser.add_argument(
        "--max-pages", type=int, default=1, help="Max API pages per division for standard tiers (1-20)"
    )
    collect_parser.add_argument(
        "-q", "--queue", type=int, default=420, help="Queue ID (420: Solo/Duo, 440: Flex, 400: Normal, 450: ARAM, 0: All)"
    )
    collect_parser.add_argument(
        "--match-type",
        choices=["ranked", "normal", "tourney", "tutorial", "all"],
        default=None,
        help="Match-v5 match type filter (auto-inferred from queue if omitted)",
    )
    collect_parser.add_argument(
        "--days-back", type=float, default=None, help="Only collect matches from the last N days"
    )
    collect_parser.add_argument(
        "--start-time", type=int, default=None, help="Match-v5 startTime epoch timestamp in seconds"
    )
    collect_parser.add_argument(
        "--end-time", type=int, default=None, help="Match-v5 endTime epoch timestamp in seconds"
    )
    collect_parser.add_argument(
        "--min-duration", type=int, default=300, help="Minimum match duration in seconds"
    )
    collect_parser.add_argument(
        "--max-duration", type=int, default=None, help="Maximum match duration in seconds"
    )
    collect_parser.add_argument(
        "--exclude-surrenders", action="store_true", help="Exclude matches that ended in surrender"
    )
    collect_parser.add_argument(
        "--patch", default=None, help="Filter matches by game version prefix (e.g. 14.4)"
    )
    collect_parser.add_argument(
        "--champions", default=None, help="Comma-separated champion names to filter matches by"
    )
    collect_parser.add_argument(
        "--positions",
        default=None,
        help="Comma-separated roles to keep (TOP,JUNGLE,MIDDLE,BOTTOM,UTILITY)",
    )
    collect_parser.add_argument(
        "--side", choices=["BLUE", "RED", "blue", "red"], default=None, help="Filter participant side (BLUE or RED)"
    )
    collect_parser.add_argument(
        "--no-discover",
        action="store_true",
        help="Disable snowball participant discovery (query only initial tier seed players)",
    )
    collect_parser.add_argument(
        "--hours", type=float, default=8.0, help="Maximum running time in hours (0 for unlimited)"
    )
    collect_parser.add_argument(
        "-n", "--target-matches", type=int, default=None, help="Target number of unique matches to collect"
    )
    collect_parser.add_argument(
        "--format", choices=["parquet", "csv", "both"], default="both", help="Dataset storage format"
    )
    collect_parser.add_argument(
        "--dataset-name", default="ranked_matches", help="Output dataset filename prefix inside data/"
    )
    collect_parser.add_argument(
        "--max-per-player", type=int, default=10, help="Max matches to sample per player (1-100)"
    )
    collect_parser.add_argument(
        "--only-challenger", action="store_true", help="Shortcut for --tiers CHALLENGER"
    )
    collect_parser.add_argument(
        "--reset-state", action="store_true", help="Reset crawler state and start fresh"
    )
    collect_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip interactive confirmation prompt"
    )

    # Filter Command (offline dataset filtering)
    filter_parser = subparsers.add_parser(
        "filter",
        help="Filter an existing Parquet/CSV dataset and export matching rows",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    filter_parser.add_argument(
        "--input", default="data/ranked_matches.parquet", help="Source dataset file path"
    )
    filter_parser.add_argument(
        "-o", "--output", default="data/filtered_matches.csv", help="Destination file path"
    )
    filter_parser.add_argument(
        "--format", choices=["csv", "parquet", "both"], default="csv", help="Export file format"
    )
    filter_parser.add_argument(
        "--champions", default=None, help="Comma-separated champion names"
    )
    filter_parser.add_argument(
        "--positions", default=None, help="Comma-separated roles (TOP,JUNGLE,MIDDLE,BOTTOM,UTILITY)"
    )
    filter_parser.add_argument(
        "--side", choices=["BLUE", "RED", "blue", "red"], default=None, help="Map side filter"
    )
    filter_parser.add_argument(
        "--win", type=int, choices=[0, 1], default=None, help="Match outcome (1=Win, 0=Loss)"
    )
    filter_parser.add_argument(
        "--patch", default=None, help="Game version prefix (e.g. 14.4)"
    )
    filter_parser.add_argument(
        "--min-duration", type=int, default=None, help="Minimum match duration in seconds"
    )
    filter_parser.add_argument(
        "--max-duration", type=int, default=None, help="Maximum match duration in seconds"
    )

    # Export Command
    export_parser = subparsers.add_parser(
        "export",
        help="Export Parquet dataset to CSV",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    export_parser.add_argument(
        "-o", "--output", default="data/ranked_matches.csv", help="Destination CSV file path"
    )
    export_parser.add_argument(
        "--dataset-name", default="ranked_matches", help="Source Parquet filename prefix inside data/"
    )

    # Status Command
    status_parser = subparsers.add_parser(
        "status",
        help="Show current crawler state and dataset stats",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    status_parser.add_argument("-p", "--platform", default="BR1", help="Platform routing")

    return parser


def main() -> None:
    """CLI Parser and dispatcher."""
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command is None or args.command == "interactive":
        run_interactive_cli()
    elif args.command == "collect":
        cmd_collect(args)
    elif args.command == "filter":
        cmd_filter(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
