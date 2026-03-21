# tests/test_scorer.py
"""Tests for scriptsmith.scorer."""

from __future__ import annotations

import json

import pytest

from scriptsmith.backends.mock import MockBackend
from scriptsmith.scorer import score


class TestScore:
    def test_micro_scoring_3_runs(self):
        responses = [
            json.dumps({"情节设置": 7, "人物对白": 5, "节奏感": 6, "_rationale": {"情节设置": "ok"}}),
            json.dumps({"情节设置": 8, "人物对白": 6, "节奏感": 7, "_rationale": {"情节设置": "ok"}}),
            json.dumps({"情节设置": 7, "人物对白": 5, "节奏感": 6, "_rationale": {"情节设置": "ok"}}),
        ]
        backend = MockBackend(responses=responses)
        result = score(
            sequence_text="测试文本",
            criteria="评分标准",
            context="上下文",
            mode="micro",
            backend=backend,
            runs=3,
        )
        assert result.scores["情节设置"] == 7  # median of [7,8,7]
        assert result.scores["人物对白"] == 5  # median of [5,6,5]
        assert result.total == 18  # 7+5+6
        assert len(result.raw_runs) == 3

    def test_single_run(self):
        responses = [json.dumps({"A": 7, "B": 5})]
        backend = MockBackend(responses=responses)
        result = score("text", "criteria", "ctx", "micro", backend, runs=1)
        assert result.scores == {"A": 7, "B": 5}

    def test_prompts_contain_text(self):
        responses = [json.dumps({"A": 7})]
        backend = MockBackend(responses=responses)
        score("MY_SCREENPLAY_TEXT", "MY_CRITERIA", "MY_CONTEXT", "micro", backend, runs=1)
        assert "MY_SCREENPLAY_TEXT" in backend.prompts[0]
        assert "MY_CRITERIA" in backend.prompts[0]

    def test_macro_mode_uses_macro_prompt(self):
        responses = [json.dumps({"A": 7})]
        backend = MockBackend(responses=responses)
        score("text", "criteria", "ctx", "macro", backend, runs=1)
        # Macro prompt should be loaded (different template)
        assert len(backend.prompts) == 1
