# src/script_forge/state.py
"""State persistence: state.json, history.jsonl, results.tsv, process lock."""

from __future__ import annotations

import json
import os
from pathlib import Path

from script_forge.models import ExperimentRecord, ProjectState
from script_forge.workspace import atomic_write


def save_state(workspace: Path, state: ProjectState) -> None:
    """Atomically save state to .script-forge/state.json."""
    content = json.dumps(state.to_dict(), ensure_ascii=False, indent=2)
    atomic_write(workspace / ".script-forge" / "state.json", content)


def load_state(workspace: Path) -> ProjectState | None:
    """Load state from .script-forge/state.json. Returns None if missing."""
    path = workspace / ".script-forge" / "state.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return ProjectState.from_dict(data)


def append_history(workspace: Path, record: ExperimentRecord) -> None:
    """Append an experiment record to history.jsonl."""
    path = workspace / ".script-forge" / "history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record.to_dict(), ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


def load_history(workspace: Path) -> list[ExperimentRecord]:
    """Load all experiment records from history.jsonl."""
    path = workspace / ".script-forge" / "history.jsonl"
    if not path.exists():
        return []
    records: list[ExperimentRecord] = []
    for line in path.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            records.append(ExperimentRecord.from_dict(json.loads(line)))
    return records


def update_results_tsv(workspace: Path, record: ExperimentRecord) -> None:
    """Append a row to results.tsv (human-readable summary)."""
    path = workspace / "results.tsv"
    header = "id\tsequence\tmode\ttarget\thypothesis\tbefore\tafter\tdelta\tstatus\n"

    if not path.exists():
        path.write_text(header, encoding="utf-8")

    row = (
        f"{record.id}\t{record.sequence}\t{record.mode}\t"
        f"{record.target_dimension}\t{record.hypothesis}\t"
        f"{record.score_before.total}/{record.score_before.max_total}\t"
        f"{record.score_after.total}/{record.score_after.max_total}\t"
        f"{record.delta}\t{record.status}\n"
    )
    with open(path, "a", encoding="utf-8") as f:
        f.write(row)


def _is_process_alive(pid: int) -> bool:
    """Check if a process is alive (cross-platform safe)."""
    import sys
    if sys.platform == "win32":
        # os.kill(pid, 0) on Windows actually kills the process!
        # Use ctypes OpenProcess instead.
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def acquire_lock(workspace: Path) -> None:
    """Acquire a process lock. Raises RuntimeError if already locked."""
    lock_path = workspace / ".script-forge" / ".lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if lock_path.exists():
        pid_str = lock_path.read_text(encoding="utf-8").strip()
        try:
            pid = int(pid_str)
            if _is_process_alive(pid):
                raise RuntimeError(
                    f"Another script-forge process is already running (PID {pid})"
                )
        except ValueError:
            pass
        # Stale lock — process is dead, clean up
        lock_path.unlink(missing_ok=True)

    lock_path.write_text(str(os.getpid()), encoding="utf-8")


def release_lock(workspace: Path) -> None:
    """Release the process lock."""
    lock_path = workspace / ".script-forge" / ".lock"
    lock_path.unlink(missing_ok=True)
