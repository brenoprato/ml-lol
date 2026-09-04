"""CLI entry point for League of Legends Match Data Collection & Dataset Generation."""

import argparse
from pathlib import Path
import sys

# Ensure project root is on sys.path for direct script execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

from src.config.settings import get_settings
from src.pipeline.orchestrator import MatchPipelineOrchestrator
from src.pipeline.state_manager import StateManager
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


def cmd_collect(args: argparse.Namespace) -> None:
    """Run data collection pipeline."""
    settings = get_settings()

    if args.reset_state:
        state_path = settings.data_dir / f"state_{args.platform.lower()}.json"
        if state_path.exists():
            state_path.unlink()
            logger.warning(f"Reset checkpoint state file: {state_path}")

    orchestrator = MatchPipelineOrchestrator(
        settings=settings,
        platform=args.platform,
        region=args.region,
        queue_id=args.queue,
        output_format=args.format,
        max_matches_per_player=args.max_per_player,
    )

    include_apex = not args.only_challenger
    orchestrator.run(
        target_matches=args.target_matches,
        max_duration_hours=args.hours,
        include_grandmaster=include_apex,
        include_master=include_apex,
    )


def cmd_export(args: argparse.Namespace) -> None:
    """Export existing Parquet dataset to CSV."""
    settings = get_settings()
    storage = BatchStorage(data_dir=settings.data_dir)
    target_csv = Path(args.output) if args.output else None
    exported = storage.export_to_csv(target_csv)
    logger.info(f"Dataset exported to: {exported}")


def cmd_status(args: argparse.Namespace) -> None:
    """Display crawler progress and dataset statistics."""
    settings = get_settings()
    platform = (args.platform or settings.default_platform).lower()
    state_file = settings.data_dir / f"state_{platform}.json"
    parquet_file = settings.data_dir / "ranked_matches.parquet"
    csv_file = settings.data_dir / "ranked_matches.csv"

    print("\n" + "=" * 50)
    print("📊 DATASET & CRAWLER STATUS SUMMARY")
    print("=" * 50)

    if state_file.exists():
        sm = StateManager(state_file)
        print(f"Platform:            {platform.upper()}")
        print(f"Visited Players:     {len(sm.visited_puuids):,}")
        print(f"Queued Players:      {len(sm.queued_puuids):,}")
        print(f"Processed Matches:   {len(sm.processed_match_ids):,}")
        print(f"Failed Matches:      {len(sm.failed_match_ids):,}")
    else:
        print(f"Platform:            {platform.upper()} (No state file yet)")

    print("-" * 50)
    if parquet_file.exists():
        size_mb = parquet_file.stat().st_size / (1024 * 1024)
        import pyarrow.parquet as pq
        table = pq.read_table(parquet_file)
        print(f"Parquet Dataset:     {parquet_file} ({size_mb:.2f} MB)")
        print(f"Total Rows:          {table.num_rows:,} ({table.num_rows // 10:,} matches)")
    else:
        print("Parquet Dataset:     Not created yet")

    if csv_file.exists():
        size_mb = csv_file.stat().st_size / (1024 * 1024)
        print(f"CSV Dataset:         {csv_file} ({size_mb:.2f} MB)")
    print("=" * 50 + "\n")


def main() -> None:
    """CLI Parser and dispatcher."""
    parser = argparse.ArgumentParser(
        description="League of Legends ML Dataset Crawler & Feature Extraction Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Collect Command
    collect_parser = subparsers.add_parser("collect", help="Start or resume ranked match crawler")
    collect_parser.add_argument("-p", "--platform", default="BR1", help="Platform routing (e.g. BR1, NA1, KR, EUW1)")
    collect_parser.add_argument("-r", "--region", default=None, help="Regional routing (auto-resolved if omitted)")
    collect_parser.add_argument("-q", "--queue", type=int, default=420, help="Queue ID (420: Solo/Duo, 440: Flex)")
    collect_parser.add_argument("--hours", type=float, default=8.0, help="Maximum running time in hours")
    collect_parser.add_argument("-n", "--target-matches", type=int, default=None, help="Target number of unique matches to collect")
    collect_parser.add_argument("--format", choices=["parquet", "csv", "both"], default="both", help="Dataset storage format (default: both)")
    collect_parser.add_argument("--max-per-player", type=int, default=10, help="Max matches to sample per player for diversity")
    collect_parser.add_argument("--only-challenger", action="store_true", help="Harvest only Challenger (skip GM and Master)")
    collect_parser.add_argument("--reset-state", action="store_true", help="Reset crawler state and start fresh")

    # Export Command
    export_parser = subparsers.add_parser("export", help="Export Parquet dataset to CSV")
    export_parser.add_argument("-o", "--output", default="data/ranked_matches.csv", help="Destination CSV file path")

    # Status Command
    status_parser = subparsers.add_parser("status", help="Show current crawler state and dataset stats")
    status_parser.add_argument("-p", "--platform", default="BR1", help="Platform routing")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command == "collect":
        cmd_collect(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
