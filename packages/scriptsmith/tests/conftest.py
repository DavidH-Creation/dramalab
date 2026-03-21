# tests/conftest.py
"""Shared fixtures for scriptsmith tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Create a minimal workspace structure for testing."""
    (tmp_path / "input").mkdir()
    (tmp_path / "sequences").mkdir()
    (tmp_path / "derived").mkdir()
    (tmp_path / "experiments").mkdir()
    (tmp_path / "exports").mkdir()
    (tmp_path / ".scriptsmith").mkdir()

    manifest = {
        "version": 1,
        "sequences": [
            {
                "id": "seq_001",
                "filename": "seq_001_ep01-03.md",
                "title": "Test Sequence 1",
                "episodes": "1-3",
                "char_count": 5000,
                "scene_count": 6,
                "markers": ["场1-1", "场1-2", "场2-1", "场2-2", "场3-1", "场3-2"],
            },
            {
                "id": "seq_002",
                "filename": "seq_002_ep04-06.md",
                "title": "Test Sequence 2",
                "episodes": "4-6",
                "char_count": 4500,
                "scene_count": 5,
                "markers": ["场4-1", "场5-1", "场5-2", "场6-1", "场6-2"],
            },
        ],
    }
    (tmp_path / "sequences" / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (tmp_path / "sequences" / "seq_001_ep01-03.md").write_text(
        "场1-1\n张陵醒来，发现自己在一个陌生的地方。\n\n场1-2\n他遇到了一个神秘的老人。\n",
        encoding="utf-8",
    )
    (tmp_path / "sequences" / "seq_002_ep04-06.md").write_text(
        "场4-1\n张陵开始了新的冒险。\n\n场5-1\n危机来临。\n",
        encoding="utf-8",
    )
    (tmp_path / "criteria.md").write_text(
        "# 评分标准\n\n## 情节设置 (10分)\n...\n## 人物对白 (10分)\n...\n## 节奏感 (10分)\n...\n",
        encoding="utf-8",
    )
    return tmp_path
