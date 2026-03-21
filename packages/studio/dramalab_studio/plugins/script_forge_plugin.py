"""Script-Forge plugin adapter for DramaLab Studio."""

from __future__ import annotations

import asyncio
import json
import queue
import tempfile
import threading
import uuid
from pathlib import Path
from typing import AsyncIterator

from dramalab_studio.plugin_protocol import DramaLabPlugin, RoundResult


class ScriptForgePlugin:
    """Wraps the script-forge package as a DramaLab Studio plugin."""

    name = "script-forge"
    display_name = "剧本优化"

    def __init__(self, workdir: Path | None = None) -> None:
        self._workdir = workdir or Path(tempfile.gettempdir()) / "dramalab-studio"
        self._workdir.mkdir(parents=True, exist_ok=True)
        self._workspace: Path | None = None
        self._session_id: str | None = None
        self._stop_event: threading.Event | None = None
        self._worker: threading.Thread | None = None
        self._queue: queue.Queue | None = None

    async def initialize(self, input_text: str, criteria_text: str, config: dict) -> dict:
        """Create workspace, split screenplay, derive files."""
        from docx import Document as DocxDocument
        from scriptsmith.git_ops import git_init
        from scriptsmith.splitter import split_screenplay
        from scriptsmith.workspace import atomic_write

        session_id = str(uuid.uuid4())[:8]
        ws = self._workdir / session_id
        ws.mkdir(parents=True, exist_ok=True)

        for d in ["input", "sequences", "derived", "experiments", "exports", ".script-forge"]:
            (ws / d).mkdir(exist_ok=True)

        # Write input as real .docx
        doc = DocxDocument()
        for line in input_text.split("\n"):
            if line.strip():
                doc.add_paragraph(line)
        docx_path = ws / "input" / "screenplay.docx"
        doc.save(str(docx_path))

        # Write criteria
        atomic_write(ws / "criteria.md", criteria_text)

        # Write project config
        model = config.get("model", "sonnet")
        config_content = f"""[project]
name = "dramalab-studio-session"
created = "{__import__('datetime').date.today().isoformat()}"

[backend]
type = "claude_cli"
model = "{model}"
derive_model = "haiku"
timeout = 300

[scoring]
runs = 3
keep_threshold = {config.get("keep_threshold", 1)}

[loop]
stall_limit = 5
target_chars_min = 8000
target_chars_max = 15000
"""
        atomic_write(ws / ".script-forge" / "project.toml", config_content)
        atomic_write(ws / ".gitignore", ".script-forge/.lock\n.script-forge/*.tmp\n")

        # Split screenplay
        try:
            from scriptsmith.backends.claude_cli import ClaudeCLIBackend
            backend = ClaudeCLIBackend(
                model=model,
                reasoning_effort=config.get("reasoning_effort", "medium"),
            )
        except Exception:
            backend = None

        infos = split_screenplay(docx_path, ws, backend=backend)

        # Derive
        if backend is not None:
            try:
                from scriptsmith.deriver import derive_all
                derive_all(ws, backend)
            except Exception:
                pass

        # Git init
        git_init(ws)

        self._workspace = ws
        self._session_id = session_id

        return {
            "session_id": session_id,
            "sequences": [info.to_dict() for info in infos],
        }

    async def run(self, config: dict) -> AsyncIterator[RoundResult]:
        """Run the optimization loop in a background thread, yield results."""
        if self._workspace is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")

        from scriptsmith.backends.claude_cli import ClaudeCLIBackend
        from scriptsmith.loop import run_loop
        from scriptsmith.state import acquire_lock, release_lock

        ws = self._workspace

        acquire_lock(ws)

        self._stop_event = threading.Event()
        self._queue = queue.Queue()
        round_counter = [0]

        def on_round(record):
            round_counter[0] += 1
            result = RoundResult.from_experiment_record(record, round_number=round_counter[0])
            self._queue.put(result)

        backend = ClaudeCLIBackend(
            model=config.get("model", "sonnet"),
            reasoning_effort=config.get("reasoning_effort", "medium"),
        )

        def worker():
            try:
                run_loop(
                    ws,
                    mode=config.get("mode", "auto"),
                    rounds=config.get("rounds"),
                    backend=backend,
                    keep_threshold=config.get("keep_threshold", 1),
                    on_round=on_round,
                    stop_event=self._stop_event,
                )
            except Exception as e:
                self._queue.put(e)
            finally:
                release_lock(ws)
                self._queue.put(None)  # Sentinel

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()

        # Async bridge: poll queue
        loop = asyncio.get_running_loop()
        while True:
            item = await loop.run_in_executor(None, self._queue.get)
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item

    async def stop(self) -> None:
        """Signal the loop to stop after current round."""
        if self._stop_event is not None:
            self._stop_event.set()

    async def get_current_text(self) -> str:
        """Read and concatenate all sequences."""
        if self._workspace is None:
            return ""
        from scriptsmith.workspace import load_manifest
        sequences = load_manifest(self._workspace)
        parts = []
        for seq in sequences:
            path = self._workspace / "sequences" / seq.filename
            if path.exists():
                parts.append(path.read_text(encoding="utf-8"))
        return "\n\n---\n\n".join(parts)

    async def export(self) -> bytes:
        """Export to docx and return bytes."""
        if self._workspace is None:
            raise RuntimeError("No workspace")
        from scriptsmith.exporter import export_to_docx
        out = self._workspace / "exports" / "improved.docx"
        out.parent.mkdir(exist_ok=True)
        export_to_docx(self._workspace, out)
        return out.read_bytes()
