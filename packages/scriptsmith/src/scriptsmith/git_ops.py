# src/scriptsmith/git_ops.py
"""Git operations with candidate-based safety. No git reset --hard."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path

from scriptsmith.workspace import load_manifest

logger = logging.getLogger(__name__)


def git_init(workspace: Path) -> None:
    """Initialize git in workspace and create initial commit."""
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True, check=True)
    # Set local user config so commit works even without global git config
    subprocess.run(
        ["git", "config", "user.email", "scriptsmith@local"],
        cwd=workspace, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "ScriptSmith"],
        cwd=workspace, capture_output=True, check=True,
    )
    subprocess.run(["git", "add", "."], cwd=workspace, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init: scriptsmith workspace"],
        cwd=workspace, capture_output=True, check=True,
    )


def _resolve_sequence_path(workspace: Path, sequence_id: str) -> tuple[str, Path]:
    """Look up filename from manifest and return (filename, full_path)."""
    sequences = load_manifest(workspace)
    for seq in sequences:
        if seq.id == sequence_id:
            path = workspace / "sequences" / seq.filename
            return seq.filename, path
    raise FileNotFoundError(f"Sequence ID not in manifest: {sequence_id}")


def apply_candidate(workspace: Path, sequence_id: str, new_text: str) -> Path:
    """Write candidate text. Backup original first."""
    filename, path = _resolve_sequence_path(workspace, sequence_id)
    backup = workspace / ".scriptsmith" / f"backup_{sequence_id}.md"
    shutil.copy2(path, backup)
    path.write_text(new_text, encoding="utf-8")
    return path


def commit_keep(workspace: Path, sequence_id: str, message: str) -> str:
    """Commit the candidate change. Remove backup. Return short hash."""
    filename, path = _resolve_sequence_path(workspace, sequence_id)
    backup = workspace / ".scriptsmith" / f"backup_{sequence_id}.md"

    subprocess.run(
        ["git", "add", f"sequences/{filename}"],
        cwd=workspace, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=workspace, capture_output=True, check=True,
    )
    backup.unlink(missing_ok=True)
    return _get_short_hash(workspace)


def discard_candidate(workspace: Path, sequence_id: str) -> None:
    """Restore from backup. No destructive git commands."""
    filename, path = _resolve_sequence_path(workspace, sequence_id)
    backup = workspace / ".scriptsmith" / f"backup_{sequence_id}.md"

    if not backup.exists():
        logger.warning("No backup found for %s, nothing to discard", sequence_id)
        return

    shutil.copy2(backup, path)

    # Belt-and-suspenders: verify restoration
    result = subprocess.run(
        ["git", "diff", "--stat", f"sequences/{filename}"],
        capture_output=True, text=True, cwd=workspace,
    )
    if result.stdout.strip():
        logger.warning("File %s still differs from HEAD after restore", filename)

    backup.unlink(missing_ok=True)


def reconcile_workspace(workspace: Path) -> None:
    """Recover from crash: restore orphan backups, mark crashed experiments."""
    sf_dir = workspace / ".scriptsmith"
    if not sf_dir.exists():
        return

    orphans = list(sf_dir.glob("backup_*.md"))
    if not orphans:
        return

    for backup in orphans:
        # Extract sequence_id from backup_seq_001.md → seq_001
        match = re.match(r"backup_(.+)\.md$", backup.name)
        if not match:
            continue
        sequence_id = match.group(1)

        try:
            filename, path = _resolve_sequence_path(workspace, sequence_id)
            shutil.copy2(backup, path)
            logger.warning("Recovered %s from interrupted experiment", sequence_id)
        except FileNotFoundError:
            logger.warning("Orphan backup for unknown sequence: %s", sequence_id)

        backup.unlink(missing_ok=True)

    # Mark last experiment in history as crashed if it wasn't finalized
    _mark_last_experiment_crashed(workspace)


def _mark_last_experiment_crashed(workspace: Path) -> None:
    """If the last history entry is not keep/discard, mark it as crashed."""
    import json

    history_path = workspace / ".scriptsmith" / "history.jsonl"
    if not history_path.exists():
        return

    lines = history_path.read_text(encoding="utf-8").strip().split("\n")
    if not lines or not lines[-1].strip():
        return

    try:
        last = json.loads(lines[-1])
    except json.JSONDecodeError:
        return

    if last.get("status") not in ("keep", "discard", "crashed"):
        last["status"] = "crashed"
        lines[-1] = json.dumps(last, ensure_ascii=False)
        history_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.warning("Marked experiment %s as crashed", last.get("id"))


def _get_short_hash(workspace: Path) -> str:
    """Return short hash of HEAD."""
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, cwd=workspace,
    )
    return result.stdout.strip()
