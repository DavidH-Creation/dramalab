# src/scriptsmith/workspace.py
"""Workspace creation, validation, and file utilities."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from scriptsmith.models import SequenceInfo


def atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically via temp file + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=path.parent, suffix=".tmp", prefix=f".{path.name}."
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_manifest(workspace: Path) -> list[SequenceInfo]:
    """Load sequence manifest from workspace."""
    manifest_path = workspace / "sequences" / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return [SequenceInfo.from_dict(s) for s in data["sequences"]]


def save_manifest(workspace: Path, sequences: list[SequenceInfo]) -> None:
    """Save sequence manifest to workspace."""
    data = {"version": 1, "sequences": [s.to_dict() for s in sequences]}
    content = json.dumps(data, ensure_ascii=False, indent=2)
    atomic_write(workspace / "sequences" / "manifest.json", content)


def load_sequence(workspace: Path, sequence_id: str) -> str:
    """Load sequence text by ID (via manifest lookup)."""
    sequences = load_manifest(workspace)
    for seq in sequences:
        if seq.id == sequence_id:
            path = workspace / "sequences" / seq.filename
            if not path.exists():
                raise FileNotFoundError(f"Sequence file not found: {path}")
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Sequence ID not in manifest: {sequence_id}")


def load_criteria(workspace: Path) -> str:
    """Load the canonical criteria.md."""
    path = workspace / "criteria.md"
    if not path.exists():
        raise FileNotFoundError(f"Criteria not found: {path}")
    return path.read_text(encoding="utf-8")


def validate_workspace(workspace: Path) -> list[str]:
    """Validate workspace structure. Returns list of error messages (empty = OK)."""
    errors: list[str] = []
    if not (workspace / "sequences").is_dir():
        errors.append("Missing sequences/ directory")
    if not (workspace / "criteria.md").exists():
        errors.append("Missing criteria.md")
    manifest_path = workspace / "sequences" / "manifest.json"
    if (workspace / "sequences").is_dir() and not manifest_path.exists():
        errors.append("Missing sequences/manifest.json")
    return errors
