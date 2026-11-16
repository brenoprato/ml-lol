"""Interactive CLI wizard and terminal UI helpers for configuring filters before API calls."""

from pathlib import Path
import time
from typing import Optional

from pydantic import ValidationError
import pyarrow.parquet as pq

from src.config.settings import Settings, get_settings
from src.models.filter_models import (
    ALL_DIVISIONS,
    ALL_TIERS,
    CollectionFilterConfig,
    DatasetFilterConfig,
    QUEUE_MAP,
    VALID_POSITIONS,
)
from src.pipeline.orchestrator import run_multi_platform_collection
from src.pipeline.state_manager import StateManager
from src.pipeline.storage import BatchStorage
from src.riot.routing import PLATFORM_TO_REGION_MAP


def _prompt_text(prompt: str, default: Optional[str] = None) -> str:
    """Prompt for a string value with optional default shown in brackets."""
    suffix = f" [{default}]" if default is not None else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    if not raw and default is not None:
        return default
    return raw


def _prompt_bool(prompt: str, default: bool = False) -> bool:
    """Prompt for a yes/no boolean value."""
    hint = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} [{hint}]: ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes", "s", "sim"):
            return True
        if raw in ("n", "no", "nao"):
            return False
        print("  Invalid choice. Please enter 'y' or 'n'.")


def _prompt_choice(prompt: str, valid_options: set[str], default: str) -> str:
    """Prompt for a menu choice from a set of valid option keys."""
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        choice = raw or default
        if choice in valid_options:
            return choice
        print(f"  Invalid selection '{choice}'. Valid options: {', '.join(sorted(valid_options))}")


def _prompt_int(
    prompt: str,
    default: Optional[int] = None,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None,
    allow_none: bool = False,
) -> Optional[int]:
    """Prompt for an integer with optional bounds and empty/none handling."""
    default_label = str(default) if default is not None else ("Unlimited" if allow_none else "")
    suffix = f" [{default_label}]" if default_label else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw:
            return default
        if allow_none and raw.lower() in ("none", "unlimited", "all", "0"):
            return None
        try:
            val = int(raw)
        except ValueError:
            print("  Invalid integer. Please try again.")
            continue
        if min_val is not None and val < min_val:
            print(f"  Value must be >= {min_val}.")
            continue
        if max_val is not None and val > max_val:
            print(f"  Value must be <= {max_val}.")
            continue
        return val


def _prompt_float(
    prompt: str,
    default: Optional[float] = None,
    min_val: Optional[float] = None,
    allow_none: bool = False,
) -> Optional[float]:
    """Prompt for a float with optional lower bound and empty/none handling."""
    default_label = str(default) if default is not None else ("None" if allow_none else "")
    suffix = f" [{default_label}]" if default_label else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw:
            return default
        if allow_none and raw.lower() in ("none", "unlimited", "all", "0"):
            return None
        try:
            val = float(raw)
        except ValueError:
            print("  Invalid number. Please try again.")
            continue
        if min_val is not None and val <= min_val:
            print(f"  Value must be > {min_val}.")
            continue
        return val


def _parse_indexed_or_named(raw: str, allowed: tuple[str, ...]) -> list[str]:
    """Parse comma-separated names or 1-based numeric indices against an allowed tuple."""
    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    resolved: list[str] = []
    for token in tokens:
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(allowed):
                resolved.append(allowed[idx])
                continue
        resolved.append(token.upper())
    return resolved


def _select_platforms() -> list[str]:
    """Interactive prompt for platform/region selection."""
    print("\n--- Step 1: Select Server Regions / Platforms ---")
    print("  [1] BR1  (Brazil - Americas)")
    print("  [2] KR   (Korea - Asia)")
    print("  [3] NA1  (North America - Americas)")
    print("  [4] EUW1 (Europe West - Europe)")
    print("  [5] Custom / Multi-Region Selection")

    choice = _prompt_choice("Select region preset", {"1", "2", "3", "4", "5"}, "1")
    preset_map = {"1": ["BR1"], "2": ["KR"], "3": ["NA1"], "4": ["EUW1"]}
    if choice in preset_map:
        return preset_map[choice]

    print("\nAvailable Platforms by Regional Cluster:")
    by_region: dict[str, list[str]] = {}
    for plat, reg in PLATFORM_TO_REGION_MAP.items():
        by_region.setdefault(reg, []).append(plat)
    for reg, plats in by_region.items():
        print(f"  {reg:<9}: {', '.join(plats)}")

    while True:
        raw = _prompt_text("Enter comma-separated platform codes (e.g. BR1,KR,NA1)", "BR1")
        selected = [p.strip().upper() for p in raw.split(",") if p.strip()]
        invalid = [p for p in selected if p not in PLATFORM_TO_REGION_MAP]
        if selected and not invalid:
            return selected
        print(f"  Invalid platform(s): {invalid or 'empty'}. Please try again.")


def _select_tiers_and_divisions() -> tuple[list[str], list[str], int]:
    """Interactive prompt for ranked tiers (elos), divisions, and pages."""
    print("\n--- Step 2: Select Ranked Tiers (Elos) ---")
    print("  [1] Apex Tiers (Challenger, Grandmaster, Master)")
    print("  [2] Challenger Only")
    print("  [3] Challenger + Grandmaster")
    print("  [4] Diamond+ (Challenger, Grandmaster, Master, Diamond)")
    print("  [5] Custom Tier Selection (Challenger down to Iron)")

    choice = _prompt_choice("Select tier preset", {"1", "2", "3", "4", "5"}, "1")
    if choice == "1":
        tiers = ["CHALLENGER", "GRANDMASTER", "MASTER"]
    elif choice == "2":
        tiers = ["CHALLENGER"]
    elif choice == "3":
        tiers = ["CHALLENGER", "GRANDMASTER"]
    elif choice == "4":
        tiers = ["CHALLENGER", "GRANDMASTER", "MASTER", "DIAMOND"]
    else:
        print("\nAvailable Tiers:")
        for idx, tier in enumerate(ALL_TIERS, start=1):
            print(f"  [{idx:>2}] {tier}")
        while True:
            raw = _prompt_text("Enter tier names or numbers (comma-separated)", "1,2,3")
            selected = _parse_indexed_or_named(raw, ALL_TIERS)
            invalid = [t for t in selected if t not in ALL_TIERS]
            if selected and not invalid:
                tiers = selected
                break
            print(f"  Invalid tier(s): {invalid or 'empty'}. Please try again.")

    divisions = ["I"]
    max_pages = 1
    if any(t not in ("CHALLENGER", "GRANDMASTER", "MASTER") for t in tiers):
        print("\nStandard tiers selected (Diamond or below). Configure divisions:")
        while True:
            raw_div = _prompt_text("Divisions (comma-separated from I, II, III, IV)", "I")
            parsed_divs = [d.strip().upper() for d in raw_div.split(",") if d.strip()]
            invalid_divs = [d for d in parsed_divs if d not in ALL_DIVISIONS]
            if parsed_divs and not invalid_divs:
                divisions = parsed_divs
                break
            print(f"  Invalid division(s): {invalid_divs or 'empty'}.")
        max_pages = _prompt_int(
            "Max API pages per division (205 players/page)",
            default=1,
            min_val=1,
            max_val=20,
        ) or 1

    return tiers, divisions, max_pages


def _select_queue_and_match_type() -> tuple[Optional[int], Optional[str]]:
    """Interactive prompt for queue ID and match type."""
    print("\n--- Step 3: Select Queue & Match Type ---")
    print("  [1] Ranked Solo/Duo (Queue 420, type: ranked)")
    print("  [2] Ranked Flex     (Queue 440, type: ranked)")
    print("  [3] Normal Draft    (Queue 400, type: normal)")
    print("  [4] ARAM            (Queue 450, type: normal)")
    print("  [5] All Queues      (No queue filter)")

    choice = _prompt_choice("Select queue", {"1", "2", "3", "4", "5"}, "1")
    mapping: dict[str, tuple[Optional[int], Optional[str]]] = {
        "1": (420, "ranked"),
        "2": (440, "ranked"),
        "3": (400, "normal"),
        "4": (450, "normal"),
        "5": (None, None),
    }
    return mapping[choice]


def _select_match_filters() -> dict:
    """Interactive prompt for temporal, duration, champion, role, side, and discovery filters."""
    print("\n--- Step 4: Match & Gameplay Filters ---")

    days_back = _prompt_float(
        "Collect matches from last N days (Enter or 0 for all available)",
        default=None,
        min_val=0.0,
        allow_none=True,
    )
    start_time = int(time.time() - (days_back * 86400)) if days_back else None

    patch_raw = _prompt_text("Patch version prefix filter (e.g. 14.4 or Enter for all)", "")
    patch_prefix = patch_raw or None

    min_duration_sec = _prompt_int(
        "Minimum match duration in seconds (excludes remakes)",
        default=300,
        min_val=0,
    )
    min_dur = min_duration_sec if min_duration_sec is not None else 300

    max_duration_sec = _prompt_int(
        "Maximum match duration in seconds",
        default=None,
        min_val=min_dur,
        allow_none=True,
    )
    exclude_surrenders = _prompt_bool("Exclude matches that ended in surrender?", default=False)

    champ_raw = _prompt_text(
        "Filter matches by champion names (comma-separated, e.g. Ahri,LeeSin or Enter for all)",
        "",
    )
    champions = [c.strip() for c in champ_raw.split(",") if c.strip()] if champ_raw else []

    print("  Positions: [1] TOP  [2] JUNGLE  [3] MIDDLE  [4] BOTTOM  [5] UTILITY")
    while True:
        pos_raw = _prompt_text(
            "Filter participant roles (names or numbers comma-separated, Enter for all)",
            "",
        )
        if not pos_raw:
            positions = []
            break
        parsed_pos = _parse_indexed_or_named(pos_raw, VALID_POSITIONS)
        invalid_pos = [p for p in parsed_pos if p not in VALID_POSITIONS]
        if not invalid_pos:
            positions = parsed_pos
            break
        print(f"  Invalid position(s): {invalid_pos}.")

    while True:
        side_raw = _prompt_text("Filter map side (BLUE, RED, or Enter for both)", "").upper()
        if not side_raw:
            side = None
            break
        if side_raw in ("BLUE", "RED"):
            side = side_raw
            break
        print("  Invalid side. Enter BLUE, RED, or press Enter for both.")

    print("\nPlayer Discovery Mode:")
    print("  [1] Snowball Graph (Discover and crawl match participants for diversity)")
    print("  [2] Strict Seed Tiers Only (Query only players from selected ranked tiers)")
    disc_choice = _prompt_choice("Select discovery mode", {"1", "2"}, "1")
    discover_participants = disc_choice == "1"

    return {
        "start_time": start_time,
        "patch_prefix": patch_prefix,
        "min_duration_sec": min_dur,
        "max_duration_sec": max_duration_sec,
        "exclude_surrenders": exclude_surrenders,
        "champions": champions,
        "positions": positions,
        "side": side,
        "discover_participants": discover_participants,
    }


def _select_execution_and_output() -> dict:
    """Interactive prompt for duration, match count limits, and output settings."""
    print("\n--- Step 5: Execution Limits & Storage ---")
    max_hours = _prompt_float(
        "Maximum execution duration in hours (0 for unlimited)",
        default=8.0,
        min_val=0.0,
        allow_none=True,
    )
    target_matches = _prompt_int(
        "Target number of unique matches to collect",
        default=None,
        min_val=1,
        allow_none=True,
    )
    max_per_player = _prompt_int(
        "Max matches to query per player (1-100)",
        default=10,
        min_val=1,
        max_val=100,
    ) or 10

    while True:
        fmt = _prompt_text("Output format (both, parquet, csv)", "both").lower()
        if fmt in ("both", "parquet", "csv"):
            break
        print("  Invalid format. Choose 'both', 'parquet', or 'csv'.")

    while True:
        dataset_name = _prompt_text("Output dataset filename prefix", "ranked_matches")
        if dataset_name and "/" not in dataset_name and "\\" not in dataset_name and ".." not in dataset_name:
            break
        print("  Invalid filename. Avoid path separators.")

    reset_state = _prompt_bool("Reset previous checkpoint state and start fresh?", default=False)

    return {
        "max_duration_hours": max_hours,
        "target_matches": target_matches,
        "max_matches_per_player": max_per_player,
        "output_format": fmt,
        "dataset_name": dataset_name,
        "reset_state": reset_state,
    }


def display_pre_flight_summary(config: CollectionFilterConfig) -> None:
    """Print formatted summary of all configured filters before executing API requests."""
    queue_name = QUEUE_MAP.get(config.queue_id, str(config.queue_id)) if config.queue_id else "All Queues"
    duration_range = f"{config.min_duration_sec}s"
    if config.max_duration_sec is not None:
        duration_range += f" .. {config.max_duration_sec}s"
    else:
        duration_range += " .. unlimited"

    print("\n" + "=" * 68)
    print("PRE-FLIGHT COLLECTION CONFIGURATION SUMMARY")
    print("=" * 68)
    print(f"Platforms:            {', '.join(config.platforms)}")
    print(f"Ranked Tiers:         {', '.join(config.tiers)}")
    if config.has_standard_tiers:
        print(
            f"Divisions / Pages:    {', '.join(config.divisions)} "
            f"(max {config.max_pages_per_division} page(s)/division)"
        )
    print(f"Queue / Match Type:   {config.queue_id or 'All'} ({queue_name}) | {config.match_type or 'All'}")
    print(f"Match Duration Range: {duration_range}")
    print(f"Exclude Surrenders:   {'Yes' if config.exclude_surrenders else 'No'}")
    print(f"Patch Prefix:         {config.patch_prefix or 'All patches'}")
    print(f"Champions Filter:     {', '.join(config.champions) if config.champions else 'All champions'}")
    print(f"Positions Filter:     {', '.join(config.positions) if config.positions else 'All positions'}")
    print(f"Map Side Filter:      {config.side or 'Both (BLUE & RED)'}")
    print(
        f"Participant Mode:     "
        f"{'Snowball Graph Discovery' if config.discover_participants else 'Strict Seed Tiers Only'}"
    )
    print(
        f"Time / Match Limits:  "
        f"{f'{config.max_duration_hours}h' if config.max_duration_hours else 'Unlimited time'} | "
        f"{config.target_matches or 'Unlimited'} matches | "
        f"{config.max_matches_per_player} matches/player"
    )
    print(f"Storage Output:       data/{config.dataset_name}.* (Format: {config.output_format})")
    print(f"Reset Checkpoint:     {'Yes' if config.reset_state else 'No (Resume if exists)'}")
    print("-" * 68)
    print("Equivalent CLI Command:")
    print(f"  {config.to_cli_command()}")
    print("=" * 68)


def confirm_collection_start(config: CollectionFilterConfig) -> bool:
    """Display pre-flight summary and ask user confirmation before starting requests."""
    display_pre_flight_summary(config)
    try:
        return _prompt_bool("Start match collection now?", default=True)
    except (KeyboardInterrupt, EOFError):
        print("\nCollection cancelled.")
        return False


def prompt_collection_filters() -> Optional[CollectionFilterConfig]:
    """Run interactive wizard to build and confirm CollectionFilterConfig before API requests."""
    try:
        print("\n" + "=" * 68)
        print("LEAGUE OF LEGENDS MATCH COLLECTION - INTERACTIVE FILTER WIZARD")
        print("=" * 68)

        platforms = _select_platforms()
        tiers, divisions, max_pages = _select_tiers_and_divisions()
        queue_id, match_type = _select_queue_and_match_type()
        match_filters = _select_match_filters()
        exec_settings = _select_execution_and_output()

        config = CollectionFilterConfig(
            platforms=platforms,
            tiers=tiers,
            divisions=divisions,
            max_pages_per_division=max_pages,
            queue_id=queue_id,
            match_type=match_type,
            **match_filters,
            **exec_settings,
        )
    except (KeyboardInterrupt, EOFError):
        print("\nWizard cancelled by user. No API requests were made.")
        return None
    except ValidationError as err:
        print(f"\nConfiguration validation error: {err}")
        return None

    if not confirm_collection_start(config):
        print("Collection cancelled. No API requests were made.")
        return None

    return config


def prompt_dataset_filter(settings: Settings) -> Optional[DatasetFilterConfig]:
    """Interactive prompt for filtering and exporting an existing dataset on disk."""
    try:
        print("\n--- Filter & Export Existing Dataset ---")
        default_input = str(settings.data_dir / "ranked_matches.parquet")
        input_path = Path(_prompt_text("Source dataset path", default_input))
        if not input_path.exists():
            print(f"  File not found: {input_path}")
            return None

        champ_raw = _prompt_text("Champion names (comma-separated, Enter for all)", "")
        champions = [c.strip() for c in champ_raw.split(",") if c.strip()] if champ_raw else []

        pos_raw = _prompt_text("Positions (TOP,JUNGLE,MIDDLE,BOTTOM,UTILITY or Enter for all)", "")
        positions = [p.strip().upper() for p in pos_raw.split(",") if p.strip()] if pos_raw else []

        side_raw = _prompt_text("Map side (BLUE, RED, or Enter for both)", "").upper()
        side = side_raw if side_raw in ("BLUE", "RED") else None

        win = _prompt_int("Match outcome filter (1=Win, 0=Loss, Enter for all)", default=None, min_val=0, max_val=1)
        patch_raw = _prompt_text("Patch version prefix (e.g. 14.4 or Enter for all)", "")
        min_dur = _prompt_int("Min game duration in seconds (Enter for no min)", default=None, min_val=0)
        max_dur = _prompt_int("Max game duration in seconds (Enter for no max)", default=None, min_val=0)

        while True:
            fmt = _prompt_text("Export format (csv, parquet, both)", "csv").lower()
            if fmt in ("csv", "parquet", "both"):
                break
            print("  Invalid format.")

        default_out = str(settings.data_dir / f"filtered_matches.{ 'parquet' if fmt == 'parquet' else 'csv' }")
        output_path = Path(_prompt_text("Destination file path", default_out))

        return DatasetFilterConfig(
            input_path=input_path,
            output_path=output_path,
            output_format=fmt,  # type: ignore[arg-type]
            champions=champions,
            positions=positions,
            side=side,  # type: ignore[arg-type]
            win=win,
            patch_prefix=patch_raw or None,
            min_duration_sec=min_dur,
            max_duration_sec=max_dur,
        )
    except (KeyboardInterrupt, EOFError):
        print("\nFilter cancelled.")
        return None
    except ValidationError as err:
        print(f"\nInvalid filter parameters: {err}")
        return None


def print_dataset_status(settings: Settings, platform: Optional[str] = None) -> None:
    """Display crawler checkpoint state and dataset file statistics."""
    target_platform = (platform or settings.default_platform).lower()
    state_file = settings.data_dir / f"state_{target_platform}.json"
    parquet_file = settings.data_dir / "ranked_matches.parquet"
    csv_file = settings.data_dir / "ranked_matches.csv"

    print("\n" + "=" * 54)
    print("DATASET & CRAWLER STATUS SUMMARY")
    print("=" * 54)

    if state_file.exists():
        sm = StateManager(state_file)
        print(f"Platform:            {target_platform.upper()}")
        print(f"Visited Players:     {len(sm.visited_puuids):,}")
        print(f"Queued Players:      {len(sm.queued_puuids):,}")
        print(f"Processed Matches:   {len(sm.processed_match_ids):,}")
        print(f"Failed Matches:      {len(sm.failed_match_ids):,}")
    else:
        print(f"Platform:            {target_platform.upper()} (No state file yet)")

    print("-" * 54)
    if parquet_file.exists():
        size_mb = parquet_file.stat().st_size / (1024 * 1024)
        table = pq.read_table(parquet_file)
        print(f"Parquet Dataset:     {parquet_file} ({size_mb:.2f} MB)")
        print(f"Total Rows:          {table.num_rows:,} ({table.num_rows // 10:,} matches)")
    else:
        print("Parquet Dataset:     Not created yet")

    if csv_file.exists():
        size_mb = csv_file.stat().st_size / (1024 * 1024)
        print(f"CSV Dataset:         {csv_file} ({size_mb:.2f} MB)")
    print("=" * 54 + "\n")


def run_interactive_cli(settings: Optional[Settings] = None) -> None:
    """Launch the interactive CLI main menu loop."""
    app_settings = settings or get_settings()

    while True:
        print("\n" + "=" * 60)
        print("LEAGUE OF LEGENDS ML DATASET CLI")
        print("=" * 60)
        print("  [1] Configure & Start Match Collection (Interactive Filter Wizard)")
        print("  [2] Quick Start Collection (BR1 | Challenger, GM, Master | Solo/Duo | 8h)")
        print("  [3] View Dataset & Crawler Status")
        print("  [4] Filter & Export Existing Dataset")
        print("  [5] Reset Crawler Checkpoint State")
        print("  [0] Exit")
        print("=" * 60)

        try:
            choice = _prompt_choice("Select an option", {"0", "1", "2", "3", "4", "5"}, "1")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting CLI.")
            break

        if choice == "0":
            print("Goodbye.")
            break

        if choice == "1":
            config = prompt_collection_filters()
            if config is not None:
                run_multi_platform_collection(app_settings, config)

        elif choice == "2":
            quick_config = CollectionFilterConfig()
            if confirm_collection_start(quick_config):
                run_multi_platform_collection(app_settings, quick_config)

        elif choice == "3":
            try:
                plat = _prompt_text("Platform checkpoint to inspect", app_settings.default_platform)
            except (KeyboardInterrupt, EOFError):
                continue
            print_dataset_status(app_settings, plat)

        elif choice == "4":
            filter_cfg = prompt_dataset_filter(app_settings)
            if filter_cfg is not None:
                storage = BatchStorage(data_dir=app_settings.data_dir)
                rows, paths = storage.filter_and_export(
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
                print(f"\nExported {rows:,} filtered rows to: {', '.join(str(p) for p in paths)}")

        elif choice == "5":
            try:
                plat = _prompt_text("Platform state to reset", app_settings.default_platform).upper()
                state_path = app_settings.data_dir / f"state_{plat.lower()}.json"
                if not state_path.exists():
                    print(f"No state file found for {plat} ({state_path}).")
                    continue
                if _prompt_bool(f"Delete checkpoint file {state_path}?", default=False):
                    state_path.unlink()
                    print(f"Reset state file: {state_path}")
            except (KeyboardInterrupt, EOFError):
                continue
