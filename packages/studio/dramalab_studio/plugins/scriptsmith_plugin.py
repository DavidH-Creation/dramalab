"""ScriptSmith plugin adapter for DramaLab Studio."""

from __future__ import annotations

import asyncio
import queue
import tempfile
import threading
import uuid
from pathlib import Path
from typing import AsyncIterator

from dramalab_studio.plugin_protocol import RoundResult


class ScriptSmithPlugin:
    """Wrap the scriptsmith package as a DramaLab Studio plugin."""

    name = "scriptsmith"
    display_name = "ScriptSmith"

    def __init__(self, workdir: Path | None = None) -> None:
        self._workdir = workdir or Path(tempfile.gettempdir()) / "dramalab-studio"
        self._workdir.mkdir(parents=True, exist_ok=True)
        self._workspace: Path | None = None
        self._session_id: str | None = None
        self._stop_event: threading.Event | None = None
        self._worker: threading.Thread | None = None
        self._queue: queue.Queue | None = None

    async def initialize(self, input_text: str, criteria_text: str, config: dict) -> dict:
        """Create workspace, split screenplay, and derive context.

        Heavy work (split, derive) runs in a thread to avoid blocking
        the uvicorn event loop.
        """
        import logging

        logger = logging.getLogger(__name__)

        def _init_sync() -> tuple[list, "Path"]:
            from docx import Document as DocxDocument
            from scriptsmith.git_ops import git_init
            from scriptsmith.splitter import split_screenplay
            from scriptsmith.workspace import atomic_write

            session_id_inner = str(uuid.uuid4())[:8]
            ws = self._workdir / session_id_inner
            ws.mkdir(parents=True, exist_ok=True)

            for directory in ["input", "sequences", "derived", "experiments", "exports", ".scriptsmith"]:
                (ws / directory).mkdir(exist_ok=True)

            doc = DocxDocument()
            for line in input_text.split("\n"):
                if line.strip():
                    doc.add_paragraph(line)
            docx_path = ws / "input" / "screenplay.docx"
            doc.save(str(docx_path))

            atomic_write(ws / "criteria.md", criteria_text)

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
            atomic_write(ws / ".scriptsmith" / "project.toml", config_content)
            atomic_write(ws / ".gitignore", ".scriptsmith/.lock\n.scriptsmith/*.tmp\n")

            try:
                from scriptsmith.backends.claude_cli import ClaudeCLIBackend

                backend = ClaudeCLIBackend(
                    model=model,
                    reasoning_effort=config.get("reasoning_effort", "medium"),
                )
            except Exception:
                backend = None

            infos = split_screenplay(docx_path, ws, backend=backend)

            # Write fallback derived files immediately so init can return fast.
            # Real derive happens in the background or on first macro round.
            derived = ws / "derived"
            derived.mkdir(parents=True, exist_ok=True)
            if not (derived / "synopsis.md").exists():
                atomic_write(
                    derived / "synopsis.md",
                    "# Synopsis\n\n(Will be generated on first run.)\n",
                )
            if not (derived / "context.md").exists():
                atomic_write(
                    derived / "context.md",
                    "# Context\n\n(Will be generated on first run.)\n",
                )

            git_init(ws)

            # Kick off derive in background thread (non-blocking)
            if backend is not None:
                def _bg_derive():
                    try:
                        from scriptsmith.deriver import derive_all

                        logger.info("Background derive_all starting...")
                        derive_all(ws, backend, max_workers=3)
                        logger.info("Background derive_all completed")
                    except Exception as exc:
                        logger.warning("Background derive_all failed: %s", exc)

                bg = threading.Thread(target=_bg_derive, daemon=True)
                bg.start()

            return infos, ws, session_id_inner

        # Run the sync init in a thread so we don't block the event loop
        loop = asyncio.get_running_loop()
        infos, ws, session_id = await loop.run_in_executor(None, _init_sync)

        self._workspace = ws
        self._session_id = session_id

        return {
            "session_id": session_id,
            "sequences": [info.to_dict() for info in infos],
        }

    async def run(self, config: dict) -> AsyncIterator[RoundResult]:
        """Run the optimization loop in a background thread and stream rounds."""
        if self._workspace is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")

        import logging

        logger = logging.getLogger(__name__)

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
                logger.info("Worker starting: mode=%s rounds=%s", config.get("mode"), config.get("rounds"))
                run_loop(
                    ws,
                    mode=config.get("mode", "auto"),
                    rounds=config.get("rounds"),
                    backend=backend,
                    keep_threshold=config.get("keep_threshold", 1),
                    on_round=on_round,
                    stop_event=self._stop_event,
                )
                logger.info("Worker completed normally")
            except Exception as exc:
                logger.exception("Worker failed: %s", exc)
                self._queue.put(exc)
            finally:
                release_lock(ws)
                self._queue.put(None)

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()

        loop = asyncio.get_running_loop()
        try:
            while True:
                # Use timeout to detect if worker thread died unexpectedly
                try:
                    item = await loop.run_in_executor(
                        None, lambda: self._queue.get(timeout=10)
                    )
                except queue.Empty:
                    if self._worker is not None and not self._worker.is_alive():
                        logger.warning("Worker thread died without sending sentinel")
                        break
                    continue
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            # Cleanup: signal worker to stop and wait for it
            if self._stop_event is not None:
                self._stop_event.set()
            if self._worker is not None and self._worker.is_alive():
                self._worker.join(timeout=15)
            self._worker = None

    async def stop(self) -> None:
        """Signal the loop to stop after the current round."""
        if self._stop_event is not None:
            self._stop_event.set()

    async def get_current_text(self) -> str:
        """Read and concatenate all current sequences."""
        if self._workspace is None:
            return ""

        from scriptsmith.workspace import load_manifest

        sequences = load_manifest(self._workspace)
        parts = []
        for sequence in sequences:
            path = self._workspace / "sequences" / sequence.filename
            if path.exists():
                parts.append(path.read_text(encoding="utf-8"))
        return "\n\n---\n\n".join(parts)

    async def export(self) -> bytes:
        """Export the current workspace to a docx document."""
        if self._workspace is None:
            raise RuntimeError("No workspace")

        from scriptsmith.exporter import export_to_docx

        output_path = self._workspace / "exports" / "improved.docx"
        output_path.parent.mkdir(exist_ok=True)
        export_to_docx(self._workspace, output_path)
        return output_path.read_bytes()
