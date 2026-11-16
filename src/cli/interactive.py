"""Rich and checkbox-driven interactive CLI wizard for configuring filters before API calls."""

from pathlib import Path
import time
from typing import Any, Optional

from pydantic import ValidationError
import pyarrow.parquet as pq
import questionary
from questionary import Choice, Style
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config.settings import Settings, get_settings
from src.models.filter_models import (
    ALL_DIVISIONS,
    ALL_TIERS,
    APEX_TIERS,
    CollectionFilterConfig,
    DatasetFilterConfig,
    QUEUE_MAP,
    STANDARD_TIERS,
    VALID_POSITIONS,
)
from src.pipeline.orchestrator import run_multi_platform_collection
from src.pipeline.state_manager import StateManager
from src.pipeline.storage import BatchStorage
from src.riot.routing import PLATFORM_TO_REGION_MAP

console = Console()

CLI_STYLE = Style(
    [
        ("qmark", "fg:#00d7ff bold"),
        ("question", "bold"),
        ("answer", "fg:#00ff87 bold"),
        ("pointer", "fg:#00d7ff bold"),
        ("highlighted", "fg:#00d7ff bold"),
        ("selected", "fg:#00ff87"),
        ("separator", "fg:#6c6c6c"),
        ("instruction", "fg:#8a8a8a"),
        ("text", ""),
    ]
)

CHECKBOX_HINT = "(Space: toggle, a: all, i: invert, Enter: confirm)"

PLATFORM_LABELS: dict[str, str] = {
    "BR1": "BR1  - Brazil (americas)",
    "KR": "KR   - Korea (asia)",
    "NA1": "NA1  - North America (americas)",
    "EUW1": "EUW1 - Europe West (europe)",
    "EUN1": "EUN1 - Europe Nordic & East (europe)",
    "LA1": "LA1  - Latin America North (americas)",
    "LA2": "LA2  - Latin America South (americas)",
    "OC1": "OC1  - Oceania (americas)",
    "JP1": "JP1  - Japan (asia)",
    "TR1": "TR1  - Turkey (europe)",
    "RU": "RU   - Russia (europe)",
    "ME1": "ME1  - Middle East (europe)",
    "SG2": "SG2  - Singapore (sea)",
    "TW2": "TW2  - Taiwan (sea)",
    "VN2": "VN2  - Vietnam (sea)",
    "PH2": "PH2  - Philippines (sea)",
    "TH2": "TH2  - Thailand (sea)",
}

POSITION_LABELS: dict[str, str] = {
    "TOP": "TOP     - Top Lane",
    "JUNGLE": "JUNGLE  - Jungle",
    "MIDDLE": "MIDDLE  - Mid Lane",
    "BOTTOM": "BOTTOM  - Bot Lane (ADC)",
    "UTILITY": "UTILITY - Support",
}

EXTRA_FILTER_CHOICES: list[tuple[str, str]] = [
    ("exclude_surrenders", "Exclude matches that ended in surrender"),
    ("strict_seeds", "Strict Seed Tiers Only (disable snowball participant discovery)"),
    ("time_window", "Time window filter (collect matches from last N days)"),
    ("patch_filter", "Patch version prefix filter (e.g. 14.4)"),
    ("champion_filter", "Champion filter (specific champion names)"),
    ("duration_bounds", "Custom match duration bounds (min/max seconds)"),
]


def _require_non_empty(selected: list[Any]) -> bool | str:
    """Validate that at least one checkbox option is selected."""
    return True if selected else "Select at least one option (use Space to toggle)."


def _validate_positive_float_or_unlimited(raw: str) -> bool | str:
    """Validate positive float or unlimited/zero input."""
    cleaned = raw.strip().lower()
    if not cleaned or cleaned in ("0", "none", "unlimited", "all"):
        return True
    try:
        val = float(cleaned)
    except ValueError:
        return "Enter a valid number (e.g. 8.0) or 0 for unlimited."
    return True if val > 0 else "Value must be greater than 0 (or 0 for unlimited)."


def _validate_optional_int(raw: str, min_val: int = 0, allow_unlimited: bool = True) -> bool | str:
    """Validate integer within lower bound or optional unlimited keyword."""
    cleaned = raw.strip().lower()
    if allow_unlimited and (not cleaned or cleaned in ("none", "unlimited", "all", "0")):
        return True
    try:
        val = int(cleaned)
    except ValueError:
        return "Enter a valid integer."
    return True if val >= min_val else f"Value must be >= {min_val}."


def _validate_int_range(raw: str, min_val: int, max_val: int) -> bool | str:
    """Validate integer strictly inside [min_val, max_val]."""
    try:
        val = int(raw.strip())
    except ValueError:
        return "Enter a valid integer."
    if min_val <= val <= max_val:
        return True
    return f"Enter an integer between {min_val} and {max_val}."


def _validate_dataset_name(raw: str) -> bool | str:
    """Validate output dataset filename without path traversal characters."""
    cleaned = raw.strip()
    if not cleaned:
        return "Filename prefix cannot be empty."
    if "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return "Filename must not contain path separators or '..'."
    return True


def render_banner() -> None:
    """Render styled terminal header and keyboard navigation hints."""
    banner_text = (
        "[bold cyan]League of Legends Dataset Collector & Filter CLI[/bold cyan]\n"
        r"[dim]Navigation: \[Up/Down] Move   \[Space] Toggle Checkbox   "
        r"\[a] Select All   \[i] Invert   \[Enter] Confirm[/dim]"
    )
    console.print(Panel(banner_text, box=box.ROUNDED, border_style="cyan", padding=(0, 2)))


def _ordered_platforms() -> list[str]:
    """Return platforms with most common servers listed first, followed by remaining servers."""
    priority = ["BR1", "KR", "NA1", "EUW1"]
    rest = [p for p in PLATFORM_TO_REGION_MAP if p not in priority]
    return priority + rest


def _select_platforms() -> Optional[list[str]]:
    """Multi-select checkbox prompt for server platforms."""
    choices = [
        Choice(
            title=PLATFORM_LABELS.get(plat, f"{plat} ({PLATFORM_TO_REGION_MAP[plat]})"),
            value=plat,
            checked=(plat == "BR1"),
        )
        for plat in _ordered_platforms()
    ]
    return questionary.checkbox(
        "1. Select Server Regions / Platforms:",
        choices=choices,
        validate=_require_non_empty,
        instruction=CHECKBOX_HINT,
        style=CLI_STYLE,
    ).ask()


def _select_tiers_and_divisions() -> Optional[tuple[list[str], list[str], int]]:
    """Multi-select checkbox prompt for ranked tiers and optional divisions/pages."""
    tier_choices = [
        Choice(
            title=f"{tier:<12} ({'Apex' if tier in APEX_TIERS else 'Standard'})",
            value=tier,
            checked=(tier in APEX_TIERS),
        )
        for tier in ALL_TIERS
    ]
    tiers = questionary.checkbox(
        "2. Select Ranked Tiers (Elos):",
        choices=tier_choices,
        validate=_require_non_empty,
        instruction=CHECKBOX_HINT,
        style=CLI_STYLE,
    ).ask()
    if tiers is None:
        return None

    divisions = ["I"]
    max_pages = 1
    if any(t in STANDARD_TIERS for t in tiers):
        div_choices = [
            Choice(title=f"Division {div}", value=div, checked=(div == "I"))
            for div in ALL_DIVISIONS
        ]
        selected_divs = questionary.checkbox(
            "   Select Divisions for Standard Tiers (Diamond - Iron):",
            choices=div_choices,
            validate=_require_non_empty,
            instruction=CHECKBOX_HINT,
            style=CLI_STYLE,
        ).ask()
        if selected_divs is None:
            return None
        divisions = selected_divs

        pages_raw = questionary.text(
            "   Max API pages per division (205 players/page, 1-20):",
            default="1",
            validate=lambda r: _validate_int_range(r, 1, 20),
            style=CLI_STYLE,
        ).ask()
        if pages_raw is None:
            return None
        max_pages = int(pages_raw.strip())

    return tiers, divisions, max_pages


def _select_queue_and_match_type() -> Optional[tuple[Optional[int], Optional[str]]]:
    """Single-select prompt for Riot queue and match type."""
    queue_choices = [
        Choice(title="Ranked Solo/Duo (Queue 420 | type: ranked)", value="420"),
        Choice(title="Ranked Flex     (Queue 440 | type: ranked)", value="440"),
        Choice(title="Normal Draft    (Queue 400 | type: normal)", value="400"),
        Choice(title="ARAM            (Queue 450 | type: normal)", value="450"),
        Choice(title="All Queues      (No queue filter)", value="ALL"),
    ]
    selected = questionary.select(
        "3. Select Queue & Match Type:",
        choices=queue_choices,
        default="420",
        style=CLI_STYLE,
    ).ask()
    if selected is None:
        return None

    mapping: dict[str, tuple[Optional[int], Optional[str]]] = {
        "420": (420, "ranked"),
        "440": (440, "ranked"),
        "400": (400, "normal"),
        "450": (450, "normal"),
        "ALL": (None, None),
    }
    return mapping[selected]


def _select_positions_and_side() -> Optional[tuple[list[str], Optional[str]]]:
    """Multi-select checkboxes for participant roles and map sides."""
    pos_choices = [
        Choice(title=POSITION_LABELS[pos], value=pos, checked=True)
        for pos in VALID_POSITIONS
    ]
    selected_pos = questionary.checkbox(
        "4. Select Participant Roles / Positions to Keep:",
        choices=pos_choices,
        validate=_require_non_empty,
        instruction=CHECKBOX_HINT,
        style=CLI_STYLE,
    ).ask()
    if selected_pos is None:
        return None
    positions = [] if len(selected_pos) == len(VALID_POSITIONS) else selected_pos

    side_choices = [
        Choice(title="BLUE Side (Team 100)", value="BLUE", checked=True),
        Choice(title="RED  Side (Team 200)", value="RED", checked=True),
    ]
    selected_sides = questionary.checkbox(
        "5. Select Map Sides to Keep:",
        choices=side_choices,
        validate=_require_non_empty,
        instruction=CHECKBOX_HINT,
        style=CLI_STYLE,
    ).ask()
    if selected_sides is None:
        return None
    side = None if len(selected_sides) == 2 else selected_sides[0]

    return positions, side


def _select_extra_filters() -> Optional[dict[str, Any]]:
    """Multi-select checkbox menu for optional match and gameplay filters."""
    extra_choices = [
        Choice(title=label, value=key, checked=False)
        for key, label in EXTRA_FILTER_CHOICES
    ]
    enabled = questionary.checkbox(
        "6. Toggle Additional Match & Gameplay Filters (Optional):",
        choices=extra_choices,
        instruction=CHECKBOX_HINT,
        style=CLI_STYLE,
    ).ask()
    if enabled is None:
        return None

    enabled_set = set(enabled)
    start_time: Optional[int] = None
    patch_prefix: Optional[str] = None
    champions: list[str] = []
    min_duration_sec = 300
    max_duration_sec: Optional[int] = None

    if "time_window" in enabled_set:
        days_raw = questionary.text(
            "   Collect matches from the last N days:",
            default="7",
            validate=_validate_positive_float_or_unlimited,
            style=CLI_STYLE,
        ).ask()
        if days_raw is None:
            return None
        cleaned = days_raw.strip().lower()
        if cleaned and cleaned not in ("0", "none", "unlimited", "all"):
            start_time = int(time.time() - (float(cleaned) * 86400))

    if "patch_filter" in enabled_set:
        patch_raw = questionary.text(
            "   Patch version prefix (e.g. 14.4):",
            default="",
            style=CLI_STYLE,
        ).ask()
        if patch_raw is None:
            return None
        patch_prefix = patch_raw.strip() or None

    if "champion_filter" in enabled_set:
        champ_raw = questionary.text(
            "   Champion names (comma-separated, e.g. Ahri, LeeSin):",
            default="",
            style=CLI_STYLE,
        ).ask()
        if champ_raw is None:
            return None
        champions = [c.strip() for c in champ_raw.split(",") if c.strip()]

    if "duration_bounds" in enabled_set:
        min_raw = questionary.text(
            "   Minimum match duration in seconds (excludes remakes):",
            default="300",
            validate=lambda r: _validate_optional_int(r, min_val=0, allow_unlimited=False),
            style=CLI_STYLE,
        ).ask()
        if min_raw is None:
            return None
        min_duration_sec = int(min_raw.strip())

        max_raw = questionary.text(
            "   Maximum match duration in seconds (0 or Enter for unlimited):",
            default="Unlimited",
            validate=lambda r: _validate_optional_int(r, min_val=min_duration_sec, allow_unlimited=True),
            style=CLI_STYLE,
        ).ask()
        if max_raw is None:
            return None
        cleaned_max = max_raw.strip().lower()
        if cleaned_max not in ("", "0", "none", "unlimited", "all"):
            max_duration_sec = int(cleaned_max)

    return {
        "exclude_surrenders": "exclude_surrenders" in enabled_set,
        "discover_participants": "strict_seeds" not in enabled_set,
        "start_time": start_time,
        "patch_prefix": patch_prefix,
        "champions": champions,
        "min_duration_sec": min_duration_sec,
        "max_duration_sec": max_duration_sec,
    }


def _select_execution_and_output() -> Optional[dict[str, Any]]:
    """Configure storage formats (checkboxes), execution time/match limits, and checkpoint options."""
    format_choices = [
        Choice(title="Parquet (.parquet - Snappy compressed, typed for ML)", value="parquet", checked=True),
        Choice(title="CSV     (.csv     - Spreadsheet-compatible UTF-8)", value="csv", checked=True),
    ]
    selected_formats = questionary.checkbox(
        "7. Select Output Storage Format(s):",
        choices=format_choices,
        validate=_require_non_empty,
        instruction=CHECKBOX_HINT,
        style=CLI_STYLE,
    ).ask()
    if selected_formats is None:
        return None
    if set(selected_formats) == {"parquet", "csv"}:
        output_format = "both"
    else:
        output_format = selected_formats[0]

    hours_raw = questionary.text(
        "8. Maximum execution duration in hours (0 for unlimited):",
        default="8.0",
        validate=_validate_positive_float_or_unlimited,
        style=CLI_STYLE,
    ).ask()
    if hours_raw is None:
        return None
    cleaned_hours = hours_raw.strip().lower()
    max_hours = None if cleaned_hours in ("", "0", "none", "unlimited", "all") else float(cleaned_hours)

    target_raw = questionary.text(
        "   Target number of unique matches (Enter or Unlimited for time-based):",
        default="Unlimited",
        validate=lambda r: _validate_optional_int(r, min_val=1, allow_unlimited=True),
        style=CLI_STYLE,
    ).ask()
    if target_raw is None:
        return None
    cleaned_target = target_raw.strip().lower()
    target_matches = (
        None if cleaned_target in ("", "0", "none", "unlimited", "all") else int(cleaned_target)
    )

    per_player_raw = questionary.text(
        "   Max matches to query per player (1-100):",
        default="10",
        validate=lambda r: _validate_int_range(r, 1, 100),
        style=CLI_STYLE,
    ).ask()
    if per_player_raw is None:
        return None
    max_per_player = int(per_player_raw.strip())

    dataset_name = questionary.text(
        "   Output dataset filename prefix (inside data/):",
        default="ranked_matches",
        validate=_validate_dataset_name,
        style=CLI_STYLE,
    ).ask()
    if dataset_name is None:
        return None

    reset_state = questionary.confirm(
        "   Reset previous checkpoint state and start fresh?",
        default=False,
        style=CLI_STYLE,
    ).ask()
    if reset_state is None:
        return None

    return {
        "output_format": output_format,
        "max_duration_hours": max_hours,
        "target_matches": target_matches,
        "max_matches_per_player": max_per_player,
        "dataset_name": dataset_name.strip(),
        "reset_state": reset_state,
    }


def display_pre_flight_summary(config: CollectionFilterConfig) -> None:
    """Render a styled Rich summary table of all selected filters before sending API requests."""
    queue_name = QUEUE_MAP.get(config.queue_id, str(config.queue_id)) if config.queue_id else "All Queues"
    duration_range = f"{config.min_duration_sec}s .. " + (
        f"{config.max_duration_sec}s" if config.max_duration_sec is not None else "unlimited"
    )
    time_window = (
        f"Since epoch {config.start_time}" if config.start_time is not None else "All available"
    )

    table = Table(
        title="Pre-Flight Collection Configuration",
        box=box.ROUNDED,
        border_style="cyan",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Filter / Parameter", style="bold white", no_wrap=True)
    table.add_column("Selected Value", style="green")

    table.add_row("Platforms", ", ".join(config.platforms))
    table.add_row("Ranked Tiers (Elos)", ", ".join(config.tiers))
    if config.has_standard_tiers:
        table.add_row(
            "Divisions / Pages",
            f"{', '.join(config.divisions)} (max {config.max_pages_per_division} page(s)/division)",
        )
    table.add_row("Queue / Match Type", f"{config.queue_id or 'All'} ({queue_name}) | {config.match_type or 'All'}")
    table.add_row("Roles / Positions", ", ".join(config.positions) if config.positions else "All (TOP..UTILITY)")
    table.add_row("Map Side", config.side or "Both (BLUE & RED)")
    table.add_row("Time Window", time_window)
    table.add_row("Match Duration", duration_range)
    table.add_row("Exclude Surrenders", "Yes" if config.exclude_surrenders else "No")
    table.add_row("Patch Prefix", config.patch_prefix or "All patches")
    table.add_row("Champions", ", ".join(config.champions) if config.champions else "All champions")
    table.add_row(
        "Discovery Mode",
        "Snowball Graph Discovery" if config.discover_participants else "Strict Seed Tiers Only",
    )
    table.add_row(
        "Execution Limits",
        f"{f'{config.max_duration_hours}h' if config.max_duration_hours else 'Unlimited time'} | "
        f"{config.target_matches or 'Unlimited'} matches | "
        f"{config.max_matches_per_player} matches/player",
    )
    table.add_row("Storage Output", f"data/{config.dataset_name}.* (Format: {config.output_format})")
    table.add_row("Reset Checkpoint", "Yes" if config.reset_state else "No (Resume if exists)")

    console.print()
    console.print(table)
    console.print(
        Panel(
            config.to_cli_command(),
            title="Equivalent Reproducible CLI Command",
            box=box.ROUNDED,
            border_style="dim",
        )
    )


def confirm_collection_start(config: CollectionFilterConfig) -> bool:
    """Display pre-flight summary and confirm before initiating Riot API requests."""
    display_pre_flight_summary(config)
    confirmed = questionary.confirm(
        "Start match collection now?",
        default=True,
        style=CLI_STYLE,
    ).ask()
    return bool(confirmed)


def prompt_collection_filters() -> Optional[CollectionFilterConfig]:
    """Run checkbox-driven interactive wizard to configure all filters before API calls."""
    render_banner()

    platforms = _select_platforms()
    if platforms is None:
        console.print("[yellow]Collection cancelled. No API requests were made.[/yellow]")
        return None

    tiers_result = _select_tiers_and_divisions()
    if tiers_result is None:
        console.print("[yellow]Collection cancelled. No API requests were made.[/yellow]")
        return None
    tiers, divisions, max_pages = tiers_result

    queue_result = _select_queue_and_match_type()
    if queue_result is None:
        console.print("[yellow]Collection cancelled. No API requests were made.[/yellow]")
        return None
    queue_id, match_type = queue_result

    pos_side_result = _select_positions_and_side()
    if pos_side_result is None:
        console.print("[yellow]Collection cancelled. No API requests were made.[/yellow]")
        return None
    positions, side = pos_side_result

    extra_filters = _select_extra_filters()
    if extra_filters is None:
        console.print("[yellow]Collection cancelled. No API requests were made.[/yellow]")
        return None

    exec_settings = _select_execution_and_output()
    if exec_settings is None:
        console.print("[yellow]Collection cancelled. No API requests were made.[/yellow]")
        return None

    try:
        config = CollectionFilterConfig(
            platforms=platforms,
            tiers=tiers,
            divisions=divisions,
            max_pages_per_division=max_pages,
            queue_id=queue_id,
            match_type=match_type,
            positions=positions,
            side=side,
            **extra_filters,
            **exec_settings,
        )
    except ValidationError as err:
        console.print(f"[red]Configuration validation error:[/red] {err}")
        return None

    if not confirm_collection_start(config):
        console.print("[yellow]Collection cancelled. No API requests were made.[/yellow]")
        return None

    return config


def prompt_dataset_filter(settings: Settings) -> Optional[DatasetFilterConfig]:
    """Checkbox-driven offline dataset filtering wizard."""
    console.print(
        Panel(
            "[bold cyan]Offline Dataset Filter & Export Wizard[/bold cyan]\n"
            f"[dim]{CHECKBOX_HINT}[/dim]",
            box=box.ROUNDED,
            border_style="cyan",
        )
    )

    default_input = str(settings.data_dir / "ranked_matches.parquet")
    input_raw = questionary.text(
        "Source dataset path:",
        default=default_input,
        style=CLI_STYLE,
    ).ask()
    if input_raw is None:
        return None
    input_path = Path(input_raw.strip())
    if not input_path.exists():
        console.print(f"[red]File not found:[/red] {input_path}")
        return None

    selected_pos = questionary.checkbox(
        "Select Positions to Keep:",
        choices=[Choice(title=POSITION_LABELS[p], value=p, checked=True) for p in VALID_POSITIONS],
        validate=_require_non_empty,
        instruction=CHECKBOX_HINT,
        style=CLI_STYLE,
    ).ask()
    if selected_pos is None:
        return None
    positions = [] if len(selected_pos) == len(VALID_POSITIONS) else selected_pos

    selected_sides = questionary.checkbox(
        "Select Map Sides to Keep:",
        choices=[
            Choice(title="BLUE Side", value="BLUE", checked=True),
            Choice(title="RED  Side", value="RED", checked=True),
        ],
        validate=_require_non_empty,
        instruction=CHECKBOX_HINT,
        style=CLI_STYLE,
    ).ask()
    if selected_sides is None:
        return None
    side = None if len(selected_sides) == 2 else selected_sides[0]

    selected_outcomes = questionary.checkbox(
        "Select Match Outcomes to Keep:",
        choices=[
            Choice(title="Win  (1)", value=1, checked=True),
            Choice(title="Loss (0)", value=0, checked=True),
        ],
        validate=_require_non_empty,
        instruction=CHECKBOX_HINT,
        style=CLI_STYLE,
    ).ask()
    if selected_outcomes is None:
        return None
    win = None if len(selected_outcomes) == 2 else int(selected_outcomes[0])

    champ_raw = questionary.text(
        "Champion names filter (comma-separated, leave blank for all):",
        default="",
        style=CLI_STYLE,
    ).ask()
    if champ_raw is None:
        return None
    champions = [c.strip() for c in champ_raw.split(",") if c.strip()]

    patch_raw = questionary.text(
        "Patch prefix filter (e.g. 14.4, leave blank for all):",
        default="",
        style=CLI_STYLE,
    ).ask()
    if patch_raw is None:
        return None

    min_raw = questionary.text(
        "Minimum match duration in seconds (leave blank for no minimum):",
        default="",
        validate=lambda r: _validate_optional_int(r, min_val=0, allow_unlimited=True) if r.strip() else True,
        style=CLI_STYLE,
    ).ask()
    if min_raw is None:
        return None
    min_dur = int(min_raw.strip()) if min_raw.strip() else None

    max_raw = questionary.text(
        "Maximum match duration in seconds (leave blank for no maximum):",
        default="",
        validate=lambda r: _validate_optional_int(r, min_val=0, allow_unlimited=True) if r.strip() else True,
        style=CLI_STYLE,
    ).ask()
    if max_raw is None:
        return None
    max_dur = int(max_raw.strip()) if max_raw.strip() else None

    selected_formats = questionary.checkbox(
        "Select Export Format(s):",
        choices=[
            Choice(title="CSV     (.csv)", value="csv", checked=True),
            Choice(title="Parquet (.parquet)", value="parquet", checked=False),
        ],
        validate=_require_non_empty,
        instruction=CHECKBOX_HINT,
        style=CLI_STYLE,
    ).ask()
    if selected_formats is None:
        return None
    fmt = "both" if set(selected_formats) == {"csv", "parquet"} else selected_formats[0]

    default_out = str(
        settings.data_dir / f"filtered_matches.{'parquet' if fmt == 'parquet' else 'csv'}"
    )
    out_raw = questionary.text(
        "Destination file path:",
        default=default_out,
        style=CLI_STYLE,
    ).ask()
    if out_raw is None:
        return None

    try:
        return DatasetFilterConfig(
            input_path=input_path,
            output_path=Path(out_raw.strip()),
            output_format=fmt,  # type: ignore[arg-type]
            champions=champions,
            positions=positions,
            side=side,  # type: ignore[arg-type]
            win=win,
            patch_prefix=patch_raw.strip() or None,
            min_duration_sec=min_dur,
            max_duration_sec=max_dur,
        )
    except ValidationError as err:
        console.print(f"[red]Invalid filter parameters:[/red] {err}")
        return None


def print_dataset_status(settings: Settings, platform: Optional[str] = None) -> None:
    """Display crawler checkpoint state and dataset file statistics in a Rich table."""
    target_platform = (platform or settings.default_platform).lower()
    state_file = settings.data_dir / f"state_{target_platform}.json"
    parquet_file = settings.data_dir / "ranked_matches.parquet"
    csv_file = settings.data_dir / "ranked_matches.csv"

    table = Table(
        title="Dataset & Crawler Status Summary",
        box=box.ROUNDED,
        border_style="cyan",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Metric", style="bold white")
    table.add_column("Value", style="green")

    if state_file.exists():
        sm = StateManager(state_file)
        table.add_row("Platform Checkpoint", target_platform.upper())
        table.add_row("Visited Players", f"{len(sm.visited_puuids):,}")
        table.add_row("Queued Players", f"{len(sm.queued_puuids):,}")
        table.add_row("Processed Matches", f"{len(sm.processed_match_ids):,}")
        table.add_row("Failed / Skipped Matches", f"{len(sm.failed_match_ids):,}")
    else:
        table.add_row("Platform Checkpoint", f"{target_platform.upper()} (No state file yet)")

    if parquet_file.exists():
        size_mb = parquet_file.stat().st_size / (1024 * 1024)
        pq_table = pq.read_table(parquet_file)
        table.add_row("Parquet Dataset", f"{parquet_file} ({size_mb:.2f} MB)")
        table.add_row(
            "Total Records",
            f"{pq_table.num_rows:,} rows ({pq_table.num_rows // 10:,} matches)",
        )
    else:
        table.add_row("Parquet Dataset", "Not created yet")

    if csv_file.exists():
        size_mb = csv_file.stat().st_size / (1024 * 1024)
        table.add_row("CSV Dataset", f"{csv_file} ({size_mb:.2f} MB)")

    console.print()
    console.print(table)
    console.print()


def run_interactive_cli(settings: Optional[Settings] = None) -> None:
    """Launch the interactive Rich + Questionary main menu loop."""
    app_settings = settings or get_settings()
    render_banner()

    menu_choices = [
        Choice(
            title="Configure & Start Match Collection (Checkbox Filter Wizard)",
            value="wizard",
        ),
        Choice(
            title="Quick Start Collection (BR1 | Challenger, GM, Master | Solo/Duo | 8h)",
            value="quick",
        ),
        Choice(
            title="View Dataset & Crawler Status",
            value="status",
        ),
        Choice(
            title="Filter & Export Existing Dataset",
            value="filter",
        ),
        Choice(
            title="Reset Crawler Checkpoint State",
            value="reset",
        ),
        Choice(
            title="Exit",
            value="exit",
        ),
    ]

    while True:
        choice = questionary.select(
            "Main Menu - Select an action:",
            choices=menu_choices,
            style=CLI_STYLE,
        ).ask()

        if choice is None or choice == "exit":
            console.print("[cyan]Exiting CLI.[/cyan]")
            break

        if choice == "wizard":
            config = prompt_collection_filters()
            if config is not None:
                run_multi_platform_collection(app_settings, config)

        elif choice == "quick":
            quick_config = CollectionFilterConfig()
            if confirm_collection_start(quick_config):
                run_multi_platform_collection(app_settings, quick_config)

        elif choice == "status":
            plat = questionary.text(
                "Platform checkpoint to inspect:",
                default=app_settings.default_platform,
                style=CLI_STYLE,
            ).ask()
            if plat is not None:
                print_dataset_status(app_settings, plat)

        elif choice == "filter":
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
                console.print(
                    f"\n[green]Exported {rows:,} filtered rows to:[/green] "
                    f"{', '.join(str(p) for p in paths)}\n"
                )

        elif choice == "reset":
            plat_raw = questionary.text(
                "Platform state to reset:",
                default=app_settings.default_platform,
                style=CLI_STYLE,
            ).ask()
            if plat_raw is None:
                continue
            plat = plat_raw.strip().upper()
            state_path = app_settings.data_dir / f"state_{plat.lower()}.json"
            if not state_path.exists():
                console.print(f"[yellow]No state file found for {plat} ({state_path}).[/yellow]")
                continue
            confirmed = questionary.confirm(
                f"Delete checkpoint file {state_path}?",
                default=False,
                style=CLI_STYLE,
            ).ask()
            if confirmed:
                state_path.unlink()
                console.print(f"[green]Reset state file:[/green] {state_path}")
