# tests/test_git_ops.py
"""Tests for script_forge.git_ops."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from script_forge.git_ops import (
    apply_candidate,
    commit_keep,
    discard_candidate,
    git_init,
    reconcile_workspace,
)


def _git_init_workspace(workspace: Path) -> None:
    """Initialize git in workspace and commit initial state."""
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=workspace, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=workspace, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=workspace, capture_output=True,
    )


class TestApplyCandidate:
    def test_writes_new_text_and_creates_backup(self, tmp_workspace: Path):
        _git_init_workspace(tmp_workspace)
        original = (tmp_workspace / "sequences" / "seq_001_ep01-03.md").read_text(encoding="utf-8")

        apply_candidate(tmp_workspace, "seq_001", "NEW CONTENT HERE")

        current = (tmp_workspace / "sequences" / "seq_001_ep01-03.md").read_text(encoding="utf-8")
        assert current == "NEW CONTENT HERE"

        backup = tmp_workspace / ".script-forge" / "backup_seq_001.md"
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == original

    def test_unknown_sequence_raises(self, tmp_workspace: Path):
        with pytest.raises(FileNotFoundError):
            apply_candidate(tmp_workspace, "seq_999", "text")


class TestCommitKeep:
    def test_commits_and_removes_backup(self, tmp_workspace: Path):
        _git_init_workspace(tmp_workspace)
        apply_candidate(tmp_workspace, "seq_001", "IMPROVED TEXT")

        short_hash = commit_keep(tmp_workspace, "seq_001", "keep: improved seq_001")

        assert len(short_hash) >= 7
        backup = tmp_workspace / ".script-forge" / "backup_seq_001.md"
        assert not backup.exists()

        # Verify git log has the commit
        log = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True, text=True, cwd=tmp_workspace,
        )
        assert "keep" in log.stdout

    def test_other_files_untouched(self, tmp_workspace: Path):
        _git_init_workspace(tmp_workspace)
        seq2_before = (tmp_workspace / "sequences" / "seq_002_ep04-06.md").read_text(encoding="utf-8")

        apply_candidate(tmp_workspace, "seq_001", "CHANGED")
        commit_keep(tmp_workspace, "seq_001", "keep")

        seq2_after = (tmp_workspace / "sequences" / "seq_002_ep04-06.md").read_text(encoding="utf-8")
        assert seq2_after == seq2_before


class TestDiscardCandidate:
    def test_restores_original(self, tmp_workspace: Path):
        _git_init_workspace(tmp_workspace)
        original = (tmp_workspace / "sequences" / "seq_001_ep01-03.md").read_text(encoding="utf-8")

        apply_candidate(tmp_workspace, "seq_001", "BAD CHANGE")
        discard_candidate(tmp_workspace, "seq_001")

        restored = (tmp_workspace / "sequences" / "seq_001_ep01-03.md").read_text(encoding="utf-8")
        assert restored == original

        backup = tmp_workspace / ".script-forge" / "backup_seq_001.md"
        assert not backup.exists()


class TestReconcileWorkspace:
    def test_recovers_orphan_backup(self, tmp_workspace: Path):
        """Simulate crash: backup exists but candidate was written."""
        _git_init_workspace(tmp_workspace)
        original = (tmp_workspace / "sequences" / "seq_001_ep01-03.md").read_text(encoding="utf-8")

        # Simulate crash mid-experiment: backup exists, file is changed
        backup = tmp_workspace / ".script-forge" / "backup_seq_001.md"
        backup.write_text(original, encoding="utf-8")
        (tmp_workspace / "sequences" / "seq_001_ep01-03.md").write_text(
            "CRASHED MID-WRITE", encoding="utf-8"
        )

        reconcile_workspace(tmp_workspace)

        # File should be restored
        current = (tmp_workspace / "sequences" / "seq_001_ep01-03.md").read_text(encoding="utf-8")
        assert current == original
        assert not backup.exists()

    def test_no_orphans_is_noop(self, tmp_workspace: Path):
        _git_init_workspace(tmp_workspace)
        reconcile_workspace(tmp_workspace)  # Should not raise
