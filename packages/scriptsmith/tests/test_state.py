# tests/test_state.py
"""Tests for scriptsmith.state."""

from __future__ import annotations

import json
from pathlib import Path

from scriptsmith.models import ProjectState, ExperimentRecord, ScoreResult
from scriptsmith.state import (
    save_state,
    load_state,
    append_history,
    load_history,
    update_results_tsv,
    acquire_lock,
    release_lock,
)


def _make_score() -> ScoreResult:
    return ScoreResult(
        scores={"A": 7}, total=7, max_total=10,
        breakdown="7", raw_runs=[{"A": 7}],
    )


def _make_record(id: int = 1, status: str = "keep") -> ExperimentRecord:
    score = _make_score()
    return ExperimentRecord(
        id=id, commit="", sequence="seq_001", mode="micro",
        target_dimension="A", hypothesis="test",
        scope="场1-1", score_before=score, score_after=score,
        delta=0, status=status, description="test",
    )


class TestSaveLoadState:
    def test_roundtrip(self, tmp_workspace: Path):
        state = ProjectState.default(mode="micro")
        state.round_number = 5
        save_state(tmp_workspace, state)
        restored = load_state(tmp_workspace)
        assert restored is not None
        assert restored.round_number == 5
        assert restored.current_mode == "micro"

    def test_load_missing_returns_none(self, tmp_workspace: Path):
        assert load_state(tmp_workspace) is None

    def test_atomic_no_temp_remains(self, tmp_workspace: Path):
        save_state(tmp_workspace, ProjectState.default(mode="micro"))
        temps = list((tmp_workspace / ".scriptsmith").glob("*.tmp"))
        assert len(temps) == 0


class TestHistory:
    def test_append_and_load(self, tmp_workspace: Path):
        r1 = _make_record(id=1)
        r2 = _make_record(id=2, status="discard")
        append_history(tmp_workspace, r1)
        append_history(tmp_workspace, r2)
        records = load_history(tmp_workspace)
        assert len(records) == 2
        assert records[0].id == 1
        assert records[1].status == "discard"

    def test_load_empty(self, tmp_workspace: Path):
        assert load_history(tmp_workspace) == []


class TestResultsTsv:
    def test_creates_file(self, tmp_workspace: Path):
        record = _make_record()
        update_results_tsv(tmp_workspace, record)
        path = tmp_workspace / "results.tsv"
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "seq_001" in content

    def test_appends_rows(self, tmp_workspace: Path):
        update_results_tsv(tmp_workspace, _make_record(id=1))
        update_results_tsv(tmp_workspace, _make_record(id=2))
        lines = (tmp_workspace / "results.tsv").read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3  # header + 2 rows


class TestLock:
    def test_acquire_and_release(self, tmp_workspace: Path):
        acquire_lock(tmp_workspace)
        lock_path = tmp_workspace / ".scriptsmith" / ".lock"
        assert lock_path.exists()
        release_lock(tmp_workspace)
        assert not lock_path.exists()

    def test_double_acquire_raises(self, tmp_workspace: Path):
        import pytest
        acquire_lock(tmp_workspace)
        with pytest.raises(RuntimeError, match="already running"):
            acquire_lock(tmp_workspace)
        release_lock(tmp_workspace)
