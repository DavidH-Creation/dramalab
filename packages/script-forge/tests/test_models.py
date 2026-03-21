# tests/test_models.py
"""Tests for script_forge.models."""

from __future__ import annotations

from script_forge.models import ScoreResult, ExperimentRecord, ProjectState, SequenceInfo


class TestScoreResult:
    def test_from_raw_runs_median(self):
        """Median of 3 runs: [6,7,8] → 7, [5,5,6] → 5."""
        runs = [
            {"情节设置": 6, "人物对白": 5},
            {"情节设置": 8, "人物对白": 6},
            {"情节设置": 7, "人物对白": 5},
        ]
        result = ScoreResult.from_raw_runs(runs, max_total=20)
        assert result.scores == {"情节设置": 7, "人物对白": 5}
        assert result.total == 12
        assert result.max_total == 20

    def test_from_raw_runs_single(self):
        """Single run: scores are taken as-is."""
        runs = [{"情节设置": 8, "人物对白": 7}]
        result = ScoreResult.from_raw_runs(runs, max_total=20)
        assert result.scores == {"情节设置": 8, "人物对白": 7}
        assert result.total == 15

    def test_to_dict_and_from_dict_roundtrip(self):
        runs = [{"情节设置": 7, "人物对白": 5}]
        original = ScoreResult.from_raw_runs(runs, max_total=20)
        restored = ScoreResult.from_dict(original.to_dict())
        assert restored.scores == original.scores
        assert restored.total == original.total
        assert restored.max_total == original.max_total

    def test_breakdown_string(self):
        runs = [{"A": 7, "B": 5}]
        result = ScoreResult.from_raw_runs(runs, max_total=20)
        assert result.breakdown == "7,5"

    def test_weakest_dimension(self):
        runs = [{"情节设置": 8, "人物对白": 5, "节奏感": 7}]
        result = ScoreResult.from_raw_runs(runs, max_total=30)
        assert result.weakest_dimension == "人物对白"


class TestExperimentRecord:
    def test_to_dict_roundtrip(self):
        score = ScoreResult(
            scores={"A": 7}, total=7, max_total=10,
            breakdown="7", raw_runs=[{"A": 7}],
        )
        record = ExperimentRecord(
            id=1, commit="abc1234", sequence="seq_001", mode="micro",
            target_dimension="A", hypothesis="test",
            scope="场1-1", score_before=score, score_after=score,
            delta=0, status="keep", description="test desc",
        )
        d = record.to_dict()
        restored = ExperimentRecord.from_dict(d)
        assert restored.id == record.id
        assert restored.commit == "abc1234"
        assert restored.status == record.status
        assert restored.score_before.total == record.score_before.total


class TestSequenceInfo:
    def test_from_dict(self):
        d = {
            "id": "seq_001",
            "filename": "seq_001_ep01-03.md",
            "title": "Test",
            "episodes": "1-3",
            "char_count": 5000,
            "scene_count": 6,
            "markers": ["场1-1", "场1-2"],
        }
        info = SequenceInfo.from_dict(d)
        assert info.id == "seq_001"
        assert info.markers == ["场1-1", "场1-2"]


class TestProjectState:
    def test_default_state(self):
        state = ProjectState.default(mode="micro")
        assert state.current_mode == "micro"
        assert state.round_number == 0
        assert state.stall_count == 0
        assert state.auto_phase is None

    def test_auto_mode_sets_phase(self):
        state = ProjectState.default(mode="auto")
        assert state.auto_phase == "macro_initial"
        assert state.current_mode == "macro"

    def test_roundtrip(self):
        state = ProjectState.default(mode="micro")
        restored = ProjectState.from_dict(state.to_dict())
        assert restored.current_mode == state.current_mode
        assert restored.round_number == state.round_number
