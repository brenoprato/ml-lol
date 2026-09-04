"""Unit tests for StateManager and deduplication."""

from pathlib import Path
from src.pipeline.state_manager import StateManager


def test_state_manager_lifecycle(tmp_path: Path) -> None:
    state_file = tmp_path / "state_test.json"
    sm = StateManager(state_file)

    # Queue PUUIDs
    added = sm.add_queued_puuids(["puuid1", "puuid2", "puuid3"])
    assert added == 3
    assert len(sm.queued_puuids) == 3

    # Deduplication on queueing
    added_again = sm.add_queued_puuids(["puuid2", "puuid4"])
    assert added_again == 1

    # Pop PUUID
    next_p = sm.pop_next_puuid()
    assert next_p == "puuid1"
    sm.mark_puuid_visited(next_p)
    assert next_p in sm.visited_puuids

    # Process match
    assert not sm.is_match_processed("MATCH_1")
    sm.mark_match_processed("MATCH_1")
    assert sm.is_match_processed("MATCH_1")

    # Persist and reload
    sm.save_state()
    assert state_file.exists()

    sm2 = StateManager(state_file)
    assert "puuid1" in sm2.visited_puuids
    assert "puuid2" in sm2.queued_puuids
    assert sm2.is_match_processed("MATCH_1")
