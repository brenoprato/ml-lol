"""State management for checkpointing, pause/resume, and match/player deduplication."""

from collections import deque
import json
from pathlib import Path
from typing import Optional
from loguru import logger

from src.core.exceptions import StatePersistenceException


class StateManager:
    """Manages crawler state including visited PUUIDs, queue, and processed match IDs."""

    def __init__(self, state_file: Path) -> None:
        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        self.visited_puuids: set[str] = set()
        self.queued_puuids: deque[str] = deque()
        self._queued_set: set[str] = set()
        self.processed_match_ids: set[str] = set()
        self.failed_match_ids: set[str] = set()

        self.load_state()

    def add_queued_puuids(self, puuids: list[str]) -> int:
        """Enqueue new player PUUIDs if they haven't been visited or queued yet."""
        added = 0
        for puuid in puuids:
            if puuid not in self.visited_puuids and puuid not in self._queued_set:
                self.queued_puuids.append(puuid)
                self._queued_set.add(puuid)
                added += 1
        return added

    def pop_next_puuid(self) -> Optional[str]:
        """Pop the next player PUUID from the crawler queue."""
        if not self.queued_puuids:
            return None
        puuid = self.queued_puuids.popleft()
        self._queued_set.discard(puuid)
        return puuid

    def mark_puuid_visited(self, puuid: str) -> None:
        """Mark a PUUID as completely visited/harvested."""
        self.visited_puuids.add(puuid)
        self._queued_set.discard(puuid)

    def is_match_processed(self, match_id: str) -> bool:
        """Check if a match ID has already been collected."""
        return match_id in self.processed_match_ids

    def mark_match_processed(self, match_id: str) -> None:
        """Mark a match ID as successfully processed and stored."""
        self.processed_match_ids.add(match_id)

    def mark_match_failed(self, match_id: str) -> None:
        """Mark a match ID as permanently failed or skipped."""
        self.failed_match_ids.add(match_id)

    def load_state(self) -> None:
        """Load state from disk if exists."""
        if not self.state_file.exists():
            logger.info("No prior state file found. Starting with fresh state.")
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.visited_puuids = set(data.get("visited_puuids", []))
            queued_list = data.get("queued_puuids", [])
            self.queued_puuids = deque(queued_list)
            self._queued_set = set(queued_list)
            self.processed_match_ids = set(data.get("processed_match_ids", []))
            self.failed_match_ids = set(data.get("failed_match_ids", []))

            logger.info(
                f"Loaded state: {len(self.visited_puuids)} visited PUUIDs, "
                f"{len(self.queued_puuids)} queued PUUIDs, "
                f"{len(self.processed_match_ids)} processed matches."
            )
        except Exception as err:
            logger.error(f"Failed to load state file: {err}")
            raise StatePersistenceException(f"Error loading state from {self.state_file}: {err}") from err

    def save_state(self) -> None:
        """Atomically persist state to disk."""
        data = {
            "visited_puuids": list(self.visited_puuids),
            "queued_puuids": list(self.queued_puuids),
            "processed_match_ids": list(self.processed_match_ids),
            "failed_match_ids": list(self.failed_match_ids),
        }
        temp_file = self.state_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            temp_file.replace(self.state_file)
        except Exception as err:
            logger.error(f"Failed to save state: {err}")
            if temp_file.exists():
                temp_file.unlink()
            raise StatePersistenceException(f"Error saving state to {self.state_file}: {err}") from err

    def reset(self) -> None:
        """Clear memory state and delete state file."""
        self.visited_puuids.clear()
        self.queued_puuids.clear()
        self._queued_set.clear()
        self.processed_match_ids.clear()
        self.failed_match_ids.clear()
        if self.state_file.exists():
            self.state_file.unlink()
        logger.info("State has been completely reset.")
