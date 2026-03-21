# tests/test_prompts.py
"""Tests for script_forge.prompts."""

from __future__ import annotations

from script_forge.prompts import load_prompt


class TestLoadPrompt:
    def test_loads_score_micro(self):
        result = load_prompt("score_micro", text="测试文本", criteria="评分标准", context="上下文")
        assert "测试文本" in result
        assert "评分标准" in result

    def test_loads_modify_micro(self):
        result = load_prompt(
            "modify_micro",
            text="测试文本",
            criteria="评分标准",
            context="上下文",
            breakdown="7,5,6",
            weakest_dimension="人物对白",
            weakest_score="5",
            dimension_criteria="对白要自然",
            failed_experiments="无",
        )
        assert "人物对白" in result
        assert "测试文本" in result

    def test_unknown_template_raises(self):
        import pytest
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent_template")

    def test_derive_seq_summary(self):
        result = load_prompt("derive_seq_summary", text="测试文本", seq_id="seq_001")
        assert "seq_001" in result

    def test_derive_synopsis(self):
        result = load_prompt("derive_synopsis", summaries="[{...}]")
        assert "[{...}]" in result

    def test_derive_context(self):
        result = load_prompt("derive_context", summaries="[{...}]")
        assert "角色" in result or "[{...}]" in result
