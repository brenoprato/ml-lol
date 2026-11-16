"""Pydantic models and constants for collection and dataset filtering."""

from pathlib import Path
import shlex
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

APEX_TIERS: tuple[str, ...] = ("CHALLENGER", "GRANDMASTER", "MASTER")
STANDARD_TIERS: tuple[str, ...] = (
    "DIAMOND",
    "EMERALD",
    "PLATINUM",
    "GOLD",
    "SILVER",
    "BRONZE",
    "IRON",
)
ALL_TIERS: tuple[str, ...] = APEX_TIERS + STANDARD_TIERS
ALL_DIVISIONS: tuple[str, ...] = ("I", "II", "III", "IV")
VALID_POSITIONS: tuple[str, ...] = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")
VALID_MATCH_TYPES: tuple[str, ...] = ("ranked", "normal", "tourney", "tutorial")
QUEUE_MAP: dict[int, str] = {
    420: "RANKED_SOLO_5x5",
    440: "RANKED_FLEX_SR",
    400: "NORMAL_DRAFT",
    450: "ARAM",
}


def _deduplicate_preserve_order(items: list[str]) -> list[str]:
    """Deduplicate string list while preserving first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


class CollectionFilterConfig(BaseModel):
    """Configuration defining all pre-request and post-fetch collection filters."""

    platforms: list[str] = Field(default_factory=lambda: ["BR1"])
    tiers: list[str] = Field(default_factory=lambda: ["CHALLENGER", "GRANDMASTER", "MASTER"])
    divisions: list[str] = Field(default_factory=lambda: ["I"])
    max_pages_per_division: int = Field(default=1, ge=1, le=20)
    queue_id: Optional[int] = 420
    match_type: Optional[str] = "ranked"
    start_time: Optional[int] = Field(default=None, ge=0)
    end_time: Optional[int] = Field(default=None, ge=0)
    min_duration_sec: int = Field(default=300, ge=0)
    max_duration_sec: Optional[int] = Field(default=None, ge=0)
    exclude_surrenders: bool = False
    patch_prefix: Optional[str] = None
    champions: list[str] = Field(default_factory=list)
    positions: list[str] = Field(default_factory=list)
    side: Optional[Literal["BLUE", "RED"]] = None
    discover_participants: bool = True
    target_matches: Optional[int] = Field(default=None, ge=1)
    max_duration_hours: Optional[float] = Field(default=8.0, gt=0)
    max_matches_per_player: int = Field(default=10, ge=1, le=100)
    output_format: Literal["parquet", "csv", "both"] = "both"
    dataset_name: str = "ranked_matches"
    reset_state: bool = False

    @field_validator("platforms")
    @classmethod
    def validate_platforms(cls, value: list[str]) -> list[str]:
        from src.riot.routing import PLATFORM_TO_REGION_MAP

        normalized = _deduplicate_preserve_order(
            [p.strip().upper() for p in value if p.strip()]
        )
        if not normalized:
            raise ValueError("At least one platform must be specified.")
        invalid = [p for p in normalized if p not in PLATFORM_TO_REGION_MAP]
        if invalid:
            raise ValueError(
                f"Unsupported platform(s): {invalid}. "
                f"Supported: {list(PLATFORM_TO_REGION_MAP.keys())}"
            )
        return normalized

    @field_validator("tiers")
    @classmethod
    def validate_tiers(cls, value: list[str]) -> list[str]:
        normalized = _deduplicate_preserve_order(
            [t.strip().upper() for t in value if t.strip()]
        )
        if not normalized:
            raise ValueError("At least one ranked tier must be specified.")
        invalid = [t for t in normalized if t not in ALL_TIERS]
        if invalid:
            raise ValueError(f"Unsupported tier(s): {invalid}. Valid tiers: {list(ALL_TIERS)}")
        return normalized

    @field_validator("divisions")
    @classmethod
    def validate_divisions(cls, value: list[str]) -> list[str]:
        normalized = _deduplicate_preserve_order(
            [d.strip().upper() for d in value if d.strip()]
        )
        if not normalized:
            raise ValueError("At least one division must be specified.")
        invalid = [d for d in normalized if d not in ALL_DIVISIONS]
        if invalid:
            raise ValueError(
                f"Unsupported division(s): {invalid}. Valid divisions: {list(ALL_DIVISIONS)}"
            )
        return normalized

    @field_validator("positions")
    @classmethod
    def validate_positions(cls, value: list[str]) -> list[str]:
        normalized = _deduplicate_preserve_order(
            [pos.strip().upper() for pos in value if pos.strip()]
        )
        invalid = [pos for pos in normalized if pos not in VALID_POSITIONS]
        if invalid:
            raise ValueError(
                f"Unsupported position(s): {invalid}. Valid positions: {list(VALID_POSITIONS)}"
            )
        return normalized

    @field_validator("champions")
    @classmethod
    def validate_champions(cls, value: list[str]) -> list[str]:
        return _deduplicate_preserve_order([c.strip() for c in value if c.strip()])

    @field_validator("side", mode="before")
    @classmethod
    def normalize_side(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        norm = value.strip().upper()
        return norm or None

    @field_validator("match_type", mode="before")
    @classmethod
    def validate_match_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        norm = value.strip().lower()
        if not norm:
            return None
        if norm not in VALID_MATCH_TYPES:
            raise ValueError(
                f"Unsupported match_type '{value}'. Valid types: {list(VALID_MATCH_TYPES)}"
            )
        return norm

    @field_validator("patch_prefix", mode="before")
    @classmethod
    def normalize_patch_prefix(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        norm = value.strip()
        return norm or None

    @field_validator("dataset_name")
    @classmethod
    def validate_dataset_name(cls, value: str) -> str:
        norm = value.strip()
        if not norm:
            raise ValueError("dataset_name must not be empty.")
        if "/" in norm or "\\" in norm or ".." in norm:
            raise ValueError("dataset_name must be a valid filename without path separators.")
        return norm

    @model_validator(mode="after")
    def validate_ranges(self) -> "CollectionFilterConfig":
        if self.max_duration_sec is not None and self.max_duration_sec < self.min_duration_sec:
            raise ValueError("max_duration_sec must be greater than or equal to min_duration_sec.")
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time < self.start_time
        ):
            raise ValueError("end_time must be greater than or equal to start_time.")
        return self

    @property
    def has_standard_tiers(self) -> bool:
        """Return True if any standard tier (Diamond through Iron) is selected."""
        return any(tier in STANDARD_TIERS for tier in self.tiers)

    @property
    def league_queue_name(self) -> str:
        """Resolve Riot League-v4 queue string for seed harvesting."""
        if self.queue_id == 440:
            return "RANKED_FLEX_SR"
        return "RANKED_SOLO_5x5"

    def to_cli_command(self) -> str:
        """Reconstruct the equivalent CLI command string for reproducibility."""
        parts = [
            "python3 src/main.py collect",
            f"-p {shlex.quote(','.join(self.platforms))}",
            f"--tiers {shlex.quote(','.join(self.tiers))}",
        ]
        if self.has_standard_tiers:
            parts.append(f"--divisions {shlex.quote(','.join(self.divisions))}")
            if self.max_pages_per_division != 1:
                parts.append(f"--max-pages {self.max_pages_per_division}")
        if self.queue_id is not None:
            parts.append(f"-q {self.queue_id}")
        if self.match_type != "ranked":
            parts.append(f"--match-type {shlex.quote(self.match_type or 'all')}")
        if self.start_time is not None:
            parts.append(f"--start-time {self.start_time}")
        if self.end_time is not None:
            parts.append(f"--end-time {self.end_time}")
        if self.min_duration_sec != 300:
            parts.append(f"--min-duration {self.min_duration_sec}")
        if self.max_duration_sec is not None:
            parts.append(f"--max-duration {self.max_duration_sec}")
        if self.exclude_surrenders:
            parts.append("--exclude-surrenders")
        if self.patch_prefix:
            parts.append(f"--patch {shlex.quote(self.patch_prefix)}")
        if self.champions:
            parts.append(f"--champions {shlex.quote(','.join(self.champions))}")
        if self.positions:
            parts.append(f"--positions {shlex.quote(','.join(self.positions))}")
        if self.side:
            parts.append(f"--side {self.side}")
        if not self.discover_participants:
            parts.append("--no-discover")
        if self.max_duration_hours is not None:
            parts.append(f"--hours {self.max_duration_hours}")
        if self.target_matches is not None:
            parts.append(f"-n {self.target_matches}")
        if self.max_matches_per_player != 10:
            parts.append(f"--max-per-player {self.max_matches_per_player}")
        if self.output_format != "both":
            parts.append(f"--format {self.output_format}")
        if self.dataset_name != "ranked_matches":
            parts.append(f"--dataset-name {shlex.quote(self.dataset_name)}")
        if self.reset_state:
            parts.append("--reset-state")
        parts.append("-y")
        return " ".join(parts)


class DatasetFilterConfig(BaseModel):
    """Configuration for filtering and exporting an existing dataset on disk."""

    input_path: Path = Field(default=Path("data/ranked_matches.parquet"))
    output_path: Path = Field(default=Path("data/filtered_matches.csv"))
    output_format: Literal["parquet", "csv", "both"] = "csv"
    champions: list[str] = Field(default_factory=list)
    positions: list[str] = Field(default_factory=list)
    side: Optional[Literal["BLUE", "RED"]] = None
    win: Optional[int] = Field(default=None, ge=0, le=1)
    patch_prefix: Optional[str] = None
    min_duration_sec: Optional[int] = Field(default=None, ge=0)
    max_duration_sec: Optional[int] = Field(default=None, ge=0)

    @field_validator("positions")
    @classmethod
    def validate_positions(cls, value: list[str]) -> list[str]:
        normalized = _deduplicate_preserve_order(
            [pos.strip().upper() for pos in value if pos.strip()]
        )
        invalid = [pos for pos in normalized if pos not in VALID_POSITIONS]
        if invalid:
            raise ValueError(
                f"Unsupported position(s): {invalid}. Valid positions: {list(VALID_POSITIONS)}"
            )
        return normalized

    @field_validator("champions")
    @classmethod
    def validate_champions(cls, value: list[str]) -> list[str]:
        return _deduplicate_preserve_order([c.strip() for c in value if c.strip()])

    @field_validator("side", mode="before")
    @classmethod
    def normalize_side(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        norm = value.strip().upper()
        return norm or None

    @field_validator("patch_prefix", mode="before")
    @classmethod
    def normalize_patch_prefix(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        norm = value.strip()
        return norm or None

    @model_validator(mode="after")
    def validate_duration_range(self) -> "DatasetFilterConfig":
        if (
            self.min_duration_sec is not None
            and self.max_duration_sec is not None
            and self.max_duration_sec < self.min_duration_sec
        ):
            raise ValueError("max_duration_sec must be greater than or equal to min_duration_sec.")
        return self
