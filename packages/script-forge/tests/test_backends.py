# tests/test_backends.py
"""Tests for script_forge.backends."""

from __future__ import annotations

import json

import pytest

from script_forge.backends import BackendError, extract_json


class TestExtractJson:
    def test_plain_json(self):
        raw = '{"score": 7, "comment": "good"}'
        assert extract_json(raw) == {"score": 7, "comment": "good"}

    def test_json_in_markdown_code_fence(self):
        raw = 'Here is the result:\n```json\n{"score": 7}\n```\nDone.'
        assert extract_json(raw) == {"score": 7}

    def test_json_in_plain_code_fence(self):
        raw = '```\n{"score": 7}\n```'
        assert extract_json(raw) == {"score": 7}

    def test_json_with_surrounding_text(self):
        raw = 'Based on my analysis:\n\n{"score": 7, "note": "text"}\n\nThat is all.'
        assert extract_json(raw) == {"score": 7, "note": "text"}

    def test_nested_json(self):
        raw = '{"scores": {"A": 7, "B": 5}, "total": 12}'
        assert extract_json(raw) == {"scores": {"A": 7, "B": 5}, "total": 12}

    def test_no_json_raises(self):
        with pytest.raises(BackendError, match="No valid JSON"):
            extract_json("This has no JSON at all")

    def test_empty_string_raises(self):
        with pytest.raises(BackendError, match="No valid JSON"):
            extract_json("")

    def test_chinese_values(self):
        raw = '{"情节设置": 7, "人物对白": 5}'
        result = extract_json(raw)
        assert result["情节设置"] == 7

    def test_json_with_rationale(self):
        """_rationale field should be preserved in extraction."""
        raw = '{"情节设置": 7, "_rationale": {"情节设置": "情节紧凑"}}'
        result = extract_json(raw)
        assert result["_rationale"]["情节设置"] == "情节紧凑"

    def test_json_array(self):
        """extract_json should handle JSON arrays too."""
        raw = '[{"type": "scene", "match": "场1", "offset": 0}]'
        result = extract_json(raw)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["type"] == "scene"

    def test_json_array_in_code_fence(self):
        raw = '```json\n[{"type": "scene"}]\n```'
        result = extract_json(raw)
        assert isinstance(result, list)

    def test_json_array_embedded(self):
        raw = 'Here are the markers:\n[{"type": "scene", "match": "INT."}]\nDone.'
        result = extract_json(raw)
        assert isinstance(result, list)


from script_forge.backends.mock import MockBackend


class TestMockBackend:
    def test_query_cycles_responses(self):
        backend = MockBackend(responses=["resp1", "resp2"])
        assert backend.query("prompt1") == "resp1"
        assert backend.query("prompt2") == "resp2"
        assert backend.query("prompt3") == "resp1"  # cycles

    def test_query_records_prompts(self):
        backend = MockBackend(responses=["ok"])
        backend.query("hello")
        backend.query("world")
        assert backend.prompts == ["hello", "world"]

    def test_query_json_parses(self):
        backend = MockBackend(responses=['{"score": 7}'])
        result = backend.query_json("prompt")
        assert result == {"score": 7}

    def test_query_json_invalid_raises(self):
        backend = MockBackend(responses=["not json"])
        with pytest.raises(BackendError):
            backend.query_json("prompt")

    def test_call_count(self):
        backend = MockBackend(responses=["a"])
        backend.query("x")
        backend.query("y")
        assert backend.call_count == 2


from unittest.mock import patch, MagicMock
from script_forge.backends.claude_cli import ClaudeCLIBackend


class TestClaudeCLIBackend:
    """Tests for ClaudeCLIBackend. All tests patch shutil.which + subprocess.run
    so they work on machines without Claude CLI installed (including CI)."""

    def _make_backend(self):
        """Create backend with mocked shutil.which."""
        with patch("script_forge.backends.claude_cli.shutil.which", return_value="/usr/bin/claude"):
            return ClaudeCLIBackend(model="sonnet", timeout=60)

    def test_query_calls_claude_cli(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Hello from Claude"
        mock_result.stderr = ""

        backend = self._make_backend()
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = backend.query("test prompt")

        assert result == "Hello from Claude"
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "-p" in cmd

    def test_query_raises_on_nonzero_exit(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: something went wrong"

        backend = self._make_backend()
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(BackendError, match="Claude CLI failed"):
                backend.query("test")

    def test_query_json_parses_response(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"score": 7}'
        mock_result.stderr = ""

        backend = self._make_backend()
        with patch("subprocess.run", return_value=mock_result):
            result = backend.query_json("test")
            assert result == {"score": 7}

    def test_query_json_retries_on_parse_failure(self):
        bad_result = MagicMock()
        bad_result.returncode = 0
        bad_result.stdout = "not json"
        bad_result.stderr = ""

        good_result = MagicMock()
        good_result.returncode = 0
        good_result.stdout = '{"score": 7}'
        good_result.stderr = ""

        backend = self._make_backend()
        with patch("subprocess.run", side_effect=[bad_result, good_result]) as mock_run:
            result = backend.query_json("test prompt", retries=1)
            assert result == {"score": 7}
            assert mock_run.call_count == 2

    def test_long_prompt_uses_stdin(self):
        """Prompts > 7000 bytes should be piped via stdin."""
        long_prompt = "x" * 8000
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""

        backend = self._make_backend()
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            backend.query(long_prompt)

        call_args = mock_run.call_args
        # Long prompts must be passed via input= kwarg, not as CLI argument
        assert call_args[1].get("input") == long_prompt

    def test_reasoning_effort_in_command(self):
        """reasoning_effort should appear as --reasoning-effort flag."""
        with patch("script_forge.backends.claude_cli.shutil.which", return_value="/usr/bin/claude"):
            backend = ClaudeCLIBackend(model="sonnet", timeout=60, reasoning_effort="high")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="hello", stderr="")
            backend.query("test prompt")

        cmd = mock_run.call_args[0][0]
        assert "--reasoning-effort" in cmd
        idx = cmd.index("--reasoning-effort")
        assert cmd[idx + 1] == "high"

    def test_reasoning_effort_default_medium(self):
        """Default reasoning_effort should be medium."""
        with patch("script_forge.backends.claude_cli.shutil.which", return_value="/usr/bin/claude"):
            backend = ClaudeCLIBackend(model="sonnet", timeout=60)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="hello", stderr="")
            backend.query("test prompt")

        cmd = mock_run.call_args[0][0]
        assert "--reasoning-effort" in cmd
        idx = cmd.index("--reasoning-effort")
        assert cmd[idx + 1] == "medium"
