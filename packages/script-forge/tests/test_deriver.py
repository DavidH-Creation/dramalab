# tests/test_deriver.py
"""Tests for script_forge.deriver."""

from __future__ import annotations

import json
from pathlib import Path

from script_forge.backends.mock import MockBackend
from script_forge.deriver import derive_all


class TestDeriveAll:
    def test_creates_derived_files(self, tmp_workspace: Path):
        # MockBackend: first 2 calls = per-sequence summaries, next 2 = synopsis + context
        responses = [
            json.dumps({"scenes": ["s1"], "characters": ["张陵"], "arc_position": "起",
                         "key_events": ["e1"], "transitions": {"from_previous": "", "to_next": "悬念"}}),
            json.dumps({"scenes": ["s2"], "characters": ["张陵"], "arc_position": "承",
                         "key_events": ["e2"], "transitions": {"from_previous": "接续", "to_next": ""}}),
            "这是全剧大纲摘要。",  # synopsis
            "## 角色表\n- 张陵：主角",  # context
        ]
        backend = MockBackend(responses=responses)
        derive_all(tmp_workspace, backend)

        synopsis_path = tmp_workspace / "derived" / "synopsis.md"
        context_path = tmp_workspace / "derived" / "context.md"
        assert synopsis_path.exists()
        assert context_path.exists()
        assert "大纲" in synopsis_path.read_text(encoding="utf-8")

    def test_caches_summaries(self, tmp_workspace: Path):
        responses = [
            json.dumps({"scenes": ["s1"], "characters": [], "arc_position": "起",
                         "key_events": [], "transitions": {"from_previous": "", "to_next": ""}}),
            json.dumps({"scenes": ["s2"], "characters": [], "arc_position": "承",
                         "key_events": [], "transitions": {"from_previous": "", "to_next": ""}}),
            "synopsis",
            "context",
        ]
        backend = MockBackend(responses=responses)

        # First call: generates summaries
        derive_all(tmp_workspace, backend)
        first_call_count = backend.call_count

        # Reset call count, re-derive (should use cache for summaries)
        backend.call_count = 0
        backend.prompts = []
        derive_all(tmp_workspace, backend)

        # Only synopsis + context calls should happen (2), not summary calls
        assert backend.call_count == 2

    def test_invalidates_cache_on_content_change(self, tmp_workspace: Path):
        responses = [
            json.dumps({"scenes": ["s1"], "characters": [], "arc_position": "起",
                         "key_events": [], "transitions": {"from_previous": "", "to_next": ""}}),
            json.dumps({"scenes": ["s2"], "characters": [], "arc_position": "承",
                         "key_events": [], "transitions": {"from_previous": "", "to_next": ""}}),
            "synopsis",
            "context",
        ] * 2  # Double for two derive_all calls
        backend = MockBackend(responses=responses)

        derive_all(tmp_workspace, backend)

        # Change a sequence file
        (tmp_workspace / "sequences" / "seq_001_ep01-03.md").write_text(
            "CHANGED CONTENT", encoding="utf-8"
        )

        backend.call_count = 0
        derive_all(tmp_workspace, backend)

        # Should regenerate summary for seq_001 (1) + skip seq_002 (0) + synopsis + context (2) = 3
        assert backend.call_count == 3
