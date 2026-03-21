# tests/test_modifier.py
"""Tests for script_forge.modifier."""

from __future__ import annotations

import json

import pytest

from script_forge.backends.mock import MockBackend
from script_forge.models import ExperimentRecord, ScoreResult
from script_forge.modifier import modify


def _make_score(scores: dict[str, int]) -> ScoreResult:
    return ScoreResult(
        scores=scores,
        total=sum(scores.values()),
        max_total=len(scores) * 10,
        breakdown=",".join(str(v) for v in scores.values()),
        raw_runs=[scores],
    )


class TestModify:
    def test_returns_modified_text_and_meta(self):
        response = json.dumps({
            "modified_text": "改写后的文本",
            "target_dimension": "人物对白",
            "hypothesis": "改善对白",
            "scope": "场1-1",
            "description": "优化了对白",
        })
        backend = MockBackend(responses=[response])
        current_score = _make_score({"情节设置": 7, "人物对白": 4, "节奏感": 6})

        new_text, meta = modify(
            sequence_text="原始文本",
            criteria="评分标准",
            context="上下文",
            current_score=current_score,
            history=[],
            mode="micro",
            backend=backend,
        )

        assert new_text == "改写后的文本"
        assert meta["target_dimension"] == "人物对白"
        assert meta["hypothesis"] == "改善对白"

    def test_targets_weakest_dimension(self):
        response = json.dumps({
            "modified_text": "text",
            "target_dimension": "节奏感",
            "hypothesis": "h",
            "scope": "s",
            "description": "d",
        })
        backend = MockBackend(responses=[response])
        current_score = _make_score({"情节设置": 8, "人物对白": 7, "节奏感": 3})

        modify("text", "criteria", "ctx", current_score, [], "micro", backend)

        # Prompt should mention the weakest dimension
        assert "节奏感" in backend.prompts[0]

    def test_includes_failed_experiments_in_prompt(self):
        response = json.dumps({
            "modified_text": "text",
            "target_dimension": "A",
            "hypothesis": "h",
            "scope": "s",
            "description": "d",
        })
        backend = MockBackend(responses=[response])
        score = _make_score({"A": 5})

        failed = ExperimentRecord(
            id=1, commit="", sequence="seq_001", mode="micro",
            target_dimension="A", hypothesis="failed attempt",
            scope="场1-1", score_before=score, score_after=score,
            delta=-1, status="discard", description="this didn't work",
        )

        modify("text", "criteria", "ctx", score, [failed], "micro", backend)

        assert "failed attempt" in backend.prompts[0]
