# tests/test_loop.py
"""Tests for script_forge.loop."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from script_forge.backends.mock import MockBackend
from script_forge.loop import run_loop, should_stop
from script_forge.models import ProjectState
from script_forge.state import load_state, save_state


def _make_mock_backend_for_loop() -> MockBackend:
    """Create a mock backend that returns valid score + modify responses."""
    score_resp = json.dumps({
        "情节设置": 7, "人物对白": 5, "节奏感": 6,
        "_rationale": {"情节设置": "ok", "人物对白": "ok", "节奏感": "ok"},
    })
    modify_resp = json.dumps({
        "modified_text": "改写后的文本内容",
        "target_dimension": "人物对白",
        "hypothesis": "改善对白",
        "scope": "场1-1",
        "description": "优化了对白",
    })
    # Loop needs: 3x score (baseline) + 1x modify + 3x score (candidate)
    # For a discard scenario, make after-scores lower
    score_resp_worse = json.dumps({
        "情节设置": 6, "人物对白": 4, "节奏感": 5,
        "_rationale": {"情节设置": "worse", "人物对白": "worse", "节奏感": "worse"},
    })
    return MockBackend(responses=[
        score_resp, score_resp, score_resp,  # baseline
        modify_resp,                          # modify
        score_resp, score_resp, score_resp,   # re-score (same = no improvement = discard)
    ])


def _init_workspace_with_git(workspace: Path) -> None:
    """Initialize git for the workspace."""
    import subprocess
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=workspace, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=workspace, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=workspace, capture_output=True)


class TestShouldStop:
    def test_stops_at_round_limit(self):
        state = ProjectState.default(mode="micro")
        state.round_number = 5
        assert should_stop(state, max_rounds=5, stall_limit=10)

    def test_does_not_stop_before_limit(self):
        state = ProjectState.default(mode="micro")
        state.round_number = 3
        assert not should_stop(state, max_rounds=5, stall_limit=10)

    def test_stops_on_auto_done(self):
        state = ProjectState.default(mode="auto")
        state.auto_phase = "done"
        assert should_stop(state, max_rounds=None, stall_limit=5)

    def test_none_rounds_does_not_stop_on_count(self):
        state = ProjectState.default(mode="micro")
        state.round_number = 100
        state.stall_count = 0
        assert not should_stop(state, max_rounds=None, stall_limit=5)

    def test_stops_on_stall(self):
        state = ProjectState.default(mode="micro")
        state.stall_count = 5
        assert should_stop(state, max_rounds=None, stall_limit=5)


class TestRunLoop:
    def test_micro_one_round(self, tmp_workspace: Path):
        _init_workspace_with_git(tmp_workspace)
        backend = _make_mock_backend_for_loop()

        run_loop(tmp_workspace, mode="micro", rounds=1, backend=backend)

        # Should have run at least the scoring calls
        assert backend.call_count >= 4  # 3 score + 1 modify minimum

    def test_micro_respects_rounds(self, tmp_workspace: Path):
        _init_workspace_with_git(tmp_workspace)
        # Need enough responses for 2 rounds
        score_resp = json.dumps({"情节设置": 7, "人物对白": 5, "节奏感": 6,
                                  "_rationale": {"情节设置": "ok", "人物对白": "ok", "节奏感": "ok"}})
        modify_resp = json.dumps({"modified_text": "text", "target_dimension": "人物对白",
                                   "hypothesis": "h", "scope": "s", "description": "d"})
        backend = MockBackend(responses=[score_resp, score_resp, score_resp, modify_resp] * 5)

        run_loop(tmp_workspace, mode="micro", rounds=2, backend=backend)

        state_path = tmp_workspace / ".script-forge" / "state.json"
        assert state_path.exists()

    def test_keep_threshold_respected(self, tmp_workspace: Path):
        """Candidate with delta=1 should be discarded when keep_threshold=2."""
        _init_workspace_with_git(tmp_workspace)
        backend = _make_mock_backend_for_loop()
        run_loop(tmp_workspace, mode="micro", rounds=1, backend=backend, keep_threshold=2)
        state = load_state(tmp_workspace)
        assert state.total_discards == 1
        assert state.total_keeps == 0

    def test_on_round_callback_called(self, tmp_workspace: Path):
        """on_round callback should be called with ExperimentRecord after each round."""
        _init_workspace_with_git(tmp_workspace)
        backend = _make_mock_backend_for_loop()
        records = []
        run_loop(tmp_workspace, mode="micro", rounds=1, backend=backend, on_round=records.append)
        assert len(records) == 1
        assert hasattr(records[0], 'delta')

    def test_stop_event_stops_loop(self, tmp_workspace: Path):
        """Setting stop_event should stop the loop after current round."""
        _init_workspace_with_git(tmp_workspace)
        backend = _make_mock_backend_for_loop()
        stop = threading.Event()
        stop.set()  # Pre-set: loop should exit immediately
        run_loop(tmp_workspace, mode="micro", rounds=10, backend=backend, stop_event=stop)
        state = load_state(tmp_workspace)
        assert state.round_number == 0  # Never ran a round
