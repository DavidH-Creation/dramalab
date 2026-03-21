# tests/test_workspace.py
"""Tests for scriptsmith.workspace."""

from __future__ import annotations

import json
from pathlib import Path

from scriptsmith.workspace import (
    atomic_write,
    load_criteria,
    load_manifest,
    load_sequence,
    validate_workspace,
)
from scriptsmith.models import SequenceInfo


class TestAtomicWrite:
    def test_writes_file(self, tmp_path: Path):
        target = tmp_path / "test.txt"
        atomic_write(target, "hello world")
        assert target.read_text(encoding="utf-8") == "hello world"

    def test_no_temp_file_remains(self, tmp_path: Path):
        target = tmp_path / "test.txt"
        atomic_write(target, "hello")
        temps = list(tmp_path.glob("*.tmp"))
        assert len(temps) == 0

    def test_overwrites_existing(self, tmp_path: Path):
        target = tmp_path / "test.txt"
        target.write_text("old", encoding="utf-8")
        atomic_write(target, "new")
        assert target.read_text(encoding="utf-8") == "new"

    def test_utf8_chinese(self, tmp_path: Path):
        target = tmp_path / "test.txt"
        content = "张陵醒来，发现自己在一个陌生的地方。"
        atomic_write(target, content)
        assert target.read_text(encoding="utf-8") == content


class TestLoadManifest:
    def test_loads_sequences(self, tmp_workspace: Path):
        sequences = load_manifest(tmp_workspace)
        assert len(sequences) == 2
        assert sequences[0].id == "seq_001"
        assert sequences[1].id == "seq_002"

    def test_missing_manifest_raises(self, tmp_path: Path):
        import pytest
        with pytest.raises(FileNotFoundError):
            load_manifest(tmp_path)


class TestLoadSequence:
    def test_loads_by_id(self, tmp_workspace: Path):
        text = load_sequence(tmp_workspace, "seq_001")
        assert "张陵醒来" in text

    def test_missing_sequence_raises(self, tmp_workspace: Path):
        import pytest
        with pytest.raises(FileNotFoundError):
            load_sequence(tmp_workspace, "seq_999")


class TestLoadCriteria:
    def test_loads_criteria_md(self, tmp_workspace: Path):
        text = load_criteria(tmp_workspace)
        assert "评分标准" in text


class TestValidateWorkspace:
    def test_valid_workspace(self, tmp_workspace: Path):
        errors = validate_workspace(tmp_workspace)
        assert len(errors) == 0

    def test_missing_sequences_dir(self, tmp_path: Path):
        (tmp_path / "criteria.md").write_text("x", encoding="utf-8")
        errors = validate_workspace(tmp_path)
        assert any("sequences" in e for e in errors)

    def test_missing_criteria(self, tmp_workspace: Path):
        (tmp_workspace / "criteria.md").unlink()
        errors = validate_workspace(tmp_workspace)
        assert any("criteria" in e for e in errors)
