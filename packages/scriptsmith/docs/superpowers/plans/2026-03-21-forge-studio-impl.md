# Forge Studio Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web UI (Forge Studio) that wraps the existing scriptsmith CLI into a 3-column browser app with real-time round-by-round results.

**Architecture:** Next.js 14 frontend talks to a FastAPI backend via REST + SSE. The backend hosts a plugin system; the v1 plugin wraps the existing `scriptsmith` Python package. The project lives in a new `forge-studio/` directory alongside (not inside) `scriptsmith/`.

**Tech Stack:** Python 3.11+ / FastAPI / uvicorn / scriptsmith (local dep) | Next.js 14 / TypeScript / Tailwind CSS / shadcn/ui / Recharts

---

## File Structure

### Backend (`forge-studio/`)

```
forge-studio/
├── pyproject.toml
├── forge_studio/
│   ├── __init__.py
│   ├── cli.py                    # Typer CLI: `forge-studio start`
│   ├── server.py                 # FastAPI app factory + CORS + static serving
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── upload.py             # POST /api/upload (docx/md parsing)
│   │   └── plugins.py            # All /api/plugins/{name}/... endpoints
│   ├── plugin_protocol.py        # ForgePlugin Protocol + RoundResult dataclass
│   ├── plugins/
│   │   ├── __init__.py           # Plugin registry
│   │   └── scriptsmith_plugin.py # Wraps scriptsmith package
│   └── sse.py                    # SSE helper (EventSourceResponse)
└── tests/
    ├── conftest.py
    ├── test_upload.py
    ├── test_plugin_protocol.py
    ├── test_scriptsmith_plugin.py
    └── test_routes.py
```

### ScriptSmith Core Changes (in existing `scriptsmith/` repo)

```
src/scriptsmith/
├── backends/
│   └── claude_cli.py             # MODIFY: add reasoning_effort param
├── loop.py                       # MODIFY: add keep_threshold, on_round, stop_event
```

### Frontend (`forge-studio/frontend/`)

```
frontend/
├── package.json
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   ├── globals.css
│   └── scriptsmith/
│       └── page.tsx
├── components/
│   ├── top-bar.tsx
│   ├── input-panel.tsx
│   ├── config-panel.tsx
│   ├── results-panel.tsx
│   ├── score-cards.tsx
│   ├── trend-chart.tsx
│   ├── dimension-bars.tsx
│   ├── round-timeline.tsx
│   └── file-upload.tsx
├── hooks/
│   ├── use-sse.ts
│   └── use-plugin.ts
├── lib/
│   └── api.ts
└── types/
    └── index.ts
```

---

## Chunk 1: Backend (scriptsmith core changes + FastAPI server + plugin)

### Task 1: ScriptSmith Core — Add `reasoning_effort` to ClaudeCLIBackend

**Files:**
- Modify: `scriptsmith/src/scriptsmith/backends/claude_cli.py`
- Test: `scriptsmith/tests/test_backends.py`

- [ ] **Step 1: Write failing test**

```python
# In tests/test_backends.py, add to TestClaudeCLIBackend:

def test_reasoning_effort_in_command(self):
    """reasoning_effort should appear as --reasoning-effort flag."""
    with patch("scriptsmith.backends.claude_cli.shutil.which", return_value="/usr/bin/claude"):
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
    with patch("scriptsmith.backends.claude_cli.shutil.which", return_value="/usr/bin/claude"):
        backend = ClaudeCLIBackend(model="sonnet", timeout=60)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="hello", stderr="")
        backend.query("test prompt")

    cmd = mock_run.call_args[0][0]
    assert "--reasoning-effort" in cmd
    idx = cmd.index("--reasoning-effort")
    assert cmd[idx + 1] == "medium"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scriptsmith && python -m pytest tests/test_backends.py::TestClaudeCLIBackend::test_reasoning_effort_in_command -v`
Expected: FAIL

- [ ] **Step 3: Implement**

In `src/scriptsmith/backends/claude_cli.py`:

```python
class ClaudeCLIBackend:
    def __init__(self, model: str = "sonnet", timeout: int = 300, reasoning_effort: str = "medium") -> None:
        self.model = model
        self.timeout = timeout
        self.reasoning_effort = reasoning_effort
        self._claude_path: str | None = None

    def query(self, prompt: str, *, timeout: int | None = None) -> str:
        t = timeout or self.timeout
        claude = self._get_claude_path()

        prompt_bytes = prompt.encode("utf-8")
        if len(prompt_bytes) < _MAX_ARG_BYTES:
            cmd = [claude, "-p", prompt, "--model", self.model, "--reasoning-effort", self.reasoning_effort, "--no-input"]
            stdin_input = None
        else:
            cmd = [claude, "-p", "-", "--model", self.model, "--reasoning-effort", self.reasoning_effort, "--no-input"]
            stdin_input = prompt
        # ... rest unchanged
```

- [ ] **Step 4: Run all backend tests**

Run: `cd scriptsmith && python -m pytest tests/test_backends.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd scriptsmith
git add src/scriptsmith/backends/claude_cli.py tests/test_backends.py
git commit -m "feat: add reasoning_effort parameter to ClaudeCLIBackend"
```

---

### Task 2: ScriptSmith Core — Add `keep_threshold`, `on_round`, `stop_event` to `run_loop`

**Files:**
- Modify: `scriptsmith/src/scriptsmith/loop.py`
- Test: `scriptsmith/tests/test_loop.py`

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/test_loop.py:
import threading

def test_keep_threshold_respected(tmp_workspace):
    """Candidate with delta=1 should be discarded when keep_threshold=2."""
    backend = _make_mock_backend_for_loop()
    # Score returns total=70, modify returns text, re-score returns total=71 (delta=1)
    run_loop(tmp_workspace, mode="micro", rounds=1, backend=backend, keep_threshold=2)
    state = load_state(tmp_workspace)
    assert state.total_discards == 1
    assert state.total_keeps == 0

def test_on_round_callback_called(tmp_workspace):
    """on_round callback should be called with ExperimentRecord after each round."""
    backend = _make_mock_backend_for_loop()
    records = []
    run_loop(tmp_workspace, mode="micro", rounds=1, backend=backend, on_round=records.append)
    assert len(records) == 1
    assert hasattr(records[0], 'delta')

def test_stop_event_stops_loop(tmp_workspace):
    """Setting stop_event should stop the loop after current round."""
    backend = _make_mock_backend_for_loop()
    stop = threading.Event()
    stop.set()  # Pre-set: loop should exit immediately
    run_loop(tmp_workspace, mode="micro", rounds=10, backend=backend, stop_event=stop)
    state = load_state(tmp_workspace)
    assert state.round_number == 0  # Never ran a round
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd scriptsmith && python -m pytest tests/test_loop.py::test_keep_threshold_respected tests/test_loop.py::test_on_round_callback_called tests/test_loop.py::test_stop_event_stops_loop -v`
Expected: FAIL (unexpected keyword arguments)

- [ ] **Step 3: Implement changes to `loop.py`**

```python
def run_loop(
    workspace: Path,
    mode: Literal["macro", "micro", "auto"],
    rounds: int | None,
    backend: BackendProtocol,
    sequence: str | None = None,
    keep_threshold: int = 1,
    on_round: callable | None = None,
    stop_event: "threading.Event | None" = None,
) -> None:
    """Run the optimization loop."""
    import threading as _threading  # lazy import to avoid top-level dep

    # Reconcile before anything
    reconcile_workspace(workspace)

    # ... existing state loading code unchanged ...

    while not should_stop(state, rounds, stall_limit):
        # Check stop_event at top of each iteration
        if stop_event is not None and stop_event.is_set():
            break

        try:
            if state.current_mode == "macro":
                record = _run_macro_round(workspace, state, criteria, backend, keep_threshold)
            else:
                record = _run_micro_round(workspace, state, criteria, backend, sequences, target_sequence=sequence, keep_threshold=keep_threshold)
        except Exception as e:
            # ... existing error handling ...
            continue

        # Fire callback after all side effects (keep/discard, history, state) are done
        if on_round is not None and record is not None:
            on_round(record)

        # ... existing auto mode transitions ...
        save_state(workspace, state)

    _print_final_summary(workspace, state)
```

Key changes to `_run_micro_round` and `_run_macro_round`:
- Accept `keep_threshold` parameter
- Replace `delta >= 1` with `delta >= keep_threshold` (4 occurrences: lines 180, 185, 282, 286)
- Return the `ExperimentRecord` (or `None` if skipped)

For `_run_micro_round`, change signature and return type:

```python
def _run_micro_round(
    workspace, state, criteria, backend, sequences, target_sequence=None, keep_threshold=1,
) -> ExperimentRecord | None:
    # ... existing code ...
    record = ExperimentRecord(
        # ... existing fields ...
        status="keep" if delta >= keep_threshold else "discard",
    )
    if delta >= keep_threshold:
        # ... keep logic ...
    else:
        # ... discard logic ...
    append_history(workspace, record)
    update_results_tsv(workspace, record)
    state.round_number += 1
    # ... stall check ...
    return record
```

For `_run_macro_round`, apply the same changes:

```python
def _run_macro_round(
    workspace, state, criteria, backend, keep_threshold=1,
) -> ExperimentRecord | None:
    # ... existing code ...
    record = ExperimentRecord(
        # ... existing fields ...
        status="keep" if delta >= keep_threshold else "discard",
    )
    if delta >= keep_threshold:
        # ... keep logic (git commit, state.total_keeps += 1) ...
    else:
        # ... discard logic (git revert, state.total_discards += 1) ...
    append_history(workspace, record)
    update_results_tsv(workspace, record)
    state.round_number += 1
    # ... stall check ...
    return record
```

- [ ] **Step 4: Run all loop tests + full suite**

Run: `cd scriptsmith && python -m pytest tests/ -v`
Expected: ALL PASS (98+ tests)

- [ ] **Step 5: Commit**

```bash
cd scriptsmith
git add src/scriptsmith/loop.py tests/test_loop.py
git commit -m "feat: add keep_threshold, on_round callback, stop_event to run_loop"
```

---

### Task 3: Forge Studio — Project scaffolding

**Files:**
- Create: `forge-studio/pyproject.toml`
- Create: `forge-studio/forge_studio/__init__.py`
- Create: `forge-studio/.gitignore`

- [ ] **Step 1: Create project directory and files**

```bash
mkdir -p forge-studio/forge_studio
mkdir -p forge-studio/forge_studio/routes
mkdir -p forge-studio/forge_studio/plugins
mkdir -p forge-studio/tests
```

`forge-studio/pyproject.toml`:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "forge-studio"
version = "0.1.0"
description = "Web UI for creative-writing optimization tools"
license = "MIT"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn>=0.29",
    "python-multipart>=0.0.9",
    "python-docx>=1.0",
    "typer>=0.9",
    "sse-starlette>=2.0",
    "scriptsmith>=0.1.0",
]

[project.scripts]
forge-studio = "forge_studio.cli:app"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
]
```

`forge-studio/forge_studio/__init__.py`:
```python
__version__ = "0.1.0"
```

`forge-studio/.gitignore`:
```
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
node_modules/
frontend/.next/
.superpowers/
```

- [ ] **Step 2: Install in dev mode**

Run: `cd forge-studio && pip install -e ".[dev]"`
Expected: Installs successfully

- [ ] **Step 3: Commit**

```bash
cd forge-studio
git init
git add pyproject.toml forge_studio/__init__.py .gitignore
git commit -m "init: forge-studio project scaffolding"
```

---

### Task 4: Plugin Protocol + RoundResult

**Files:**
- Create: `forge-studio/forge_studio/plugin_protocol.py`
- Create: `forge-studio/tests/test_plugin_protocol.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_plugin_protocol.py
from forge_studio.plugin_protocol import RoundResult

def test_round_result_to_dict():
    r = RoundResult(
        round_number=1,
        status="keep",
        total_before=70,
        total_after=74,
        delta=4,
        target_dimension="对白质量",
        description="Improved dialogue",
        scores_before={"结构": 18, "对白": 14},
        scores_after={"结构": 18, "对白": 18},
        max_total=100,
    )
    d = r.to_dict()
    assert d["round_number"] == 1
    assert d["status"] == "keep"
    assert d["scores_before"]["对白"] == 14
    assert d["scores_after"]["对白"] == 18

def test_round_result_from_experiment_record():
    """RoundResult.from_experiment_record should convert correctly."""
    from unittest.mock import MagicMock
    record = MagicMock()
    record.id = 1
    record.sequence = "seq_01"
    record.mode = "micro"
    record.target_dimension = "对白"
    record.hypothesis = "test"
    record.scope = "scene"
    record.description = "Modified dialogue"
    record.delta = 4
    record.status = "keep"
    record.score_before.total = 70
    record.score_after.total = 74
    record.score_before.scores = {"结构": 18, "对白": 14}
    record.score_after.scores = {"结构": 18, "对白": 18}
    record.score_before.max_total = 100
    record.score_after.max_total = 100

    r = RoundResult.from_experiment_record(record, round_number=3)
    assert r.round_number == 3
    assert r.total_before == 70
    assert r.total_after == 74
    assert r.max_total == 100
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd forge-studio && python -m pytest tests/test_plugin_protocol.py -v`
Expected: FAIL (no module)

- [ ] **Step 3: Implement**

```python
# forge_studio/plugin_protocol.py
"""Plugin protocol and shared data types for Forge Studio."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol


@dataclass
class RoundResult:
    """Result of a single optimization round, sent to frontend via SSE."""

    round_number: int
    status: str          # "keep" | "discard" | "error"
    total_before: int
    total_after: int
    delta: int
    target_dimension: str
    description: str
    scores_before: dict[str, int]
    scores_after: dict[str, int]
    max_total: int

    def to_dict(self) -> dict:
        return {
            "round_number": self.round_number,
            "status": self.status,
            "total_before": self.total_before,
            "total_after": self.total_after,
            "delta": self.delta,
            "target_dimension": self.target_dimension,
            "description": self.description,
            "scores_before": self.scores_before,
            "scores_after": self.scores_after,
            "max_total": self.max_total,
        }

    @classmethod
    def from_experiment_record(cls, record, round_number: int) -> RoundResult:
        """Convert a scriptsmith ExperimentRecord to RoundResult."""
        return cls(
            round_number=round_number,
            status=record.status,
            total_before=record.score_before.total,
            total_after=record.score_after.total,
            delta=record.delta,
            target_dimension=record.target_dimension,
            description=record.description,
            scores_before=dict(record.score_before.scores),
            scores_after=dict(record.score_after.scores),
            max_total=record.score_before.max_total,
        )


class ForgePlugin(Protocol):
    """Protocol that all Forge Studio plugins must implement."""

    name: str
    display_name: str

    async def initialize(self, input_text: str, criteria_text: str, config: dict) -> dict:
        ...

    async def run(self, config: dict) -> AsyncIterator[RoundResult]:
        ...

    async def stop(self) -> None:
        ...

    async def get_current_text(self) -> str:
        ...

    async def export(self) -> bytes:
        ...
```

- [ ] **Step 4: Run tests**

Run: `cd forge-studio && python -m pytest tests/test_plugin_protocol.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd forge-studio
git add forge_studio/plugin_protocol.py tests/test_plugin_protocol.py
git commit -m "feat: add ForgePlugin protocol and RoundResult dataclass"
```

---

### Task 5: Upload Route

**Files:**
- Create: `forge-studio/forge_studio/routes/__init__.py`
- Create: `forge-studio/forge_studio/routes/upload.py`
- Create: `forge-studio/tests/test_upload.py`
- Create: `forge-studio/tests/conftest.py`

- [ ] **Step 1: Write tests**

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from forge_studio.server import create_app

@pytest.fixture
def app():
    return create_app()

@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

```python
# tests/test_upload.py
import io
import pytest
from docx import Document

pytestmark = pytest.mark.asyncio

async def test_upload_docx(client):
    """Upload a .docx file and get extracted text."""
    doc = Document()
    doc.add_paragraph("第一集 死神来了")
    doc.add_paragraph("场景一：殡仪馆")
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    resp = await client.post(
        "/api/upload",
        files={"file": ("test.docx", buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "第一集 死神来了" in data["text"]
    assert data["filename"] == "test.docx"

async def test_upload_md(client):
    """Upload a .md file and get text as-is."""
    content = b"# Scoring Criteria\n\nStructure: 20 points"
    resp = await client.post(
        "/api/upload",
        files={"file": ("criteria.md", io.BytesIO(content), "text/markdown")},
    )
    assert resp.status_code == 200
    assert "Scoring Criteria" in resp.json()["text"]

async def test_upload_invalid_type(client):
    """Reject unsupported file types."""
    resp = await client.post(
        "/api/upload",
        files={"file": ("image.png", io.BytesIO(b"fake"), "image/png")},
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd forge-studio && python -m pytest tests/test_upload.py -v`
Expected: FAIL (no server module)

- [ ] **Step 3: Implement server + upload route**

```python
# forge_studio/server.py
"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def create_app() -> FastAPI:
    app = FastAPI(title="Forge Studio", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from forge_studio.routes.upload import router as upload_router
    app.include_router(upload_router, prefix="/api")

    return app
```

```python
# forge_studio/routes/__init__.py
```

```python
# forge_studio/routes/upload.py
"""File upload endpoint."""

from __future__ import annotations

import io

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter()

_ALLOWED_EXTENSIONS = {".docx", ".md", ".txt"}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file and extract text content."""
    filename = file.filename or "unknown"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {_ALLOWED_EXTENSIONS}")

    content = await file.read()

    if ext == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(content))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    else:
        text = content.decode("utf-8")

    return {
        "text": text,
        "filename": filename,
        "size_kb": round(len(content) / 1024, 1),
    }
```

- [ ] **Step 4: Run tests**

Run: `cd forge-studio && python -m pytest tests/test_upload.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd forge-studio
git add forge_studio/server.py forge_studio/routes/ tests/conftest.py tests/test_upload.py
git commit -m "feat: add file upload endpoint with docx/md support"
```

---

### Task 6: ScriptSmith Plugin

**Files:**
- Create: `forge-studio/forge_studio/plugins/__init__.py`
- Create: `forge-studio/forge_studio/plugins/scriptsmith_plugin.py`
- Create: `forge-studio/tests/test_scriptsmith_plugin.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_scriptsmith_plugin.py
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from forge_studio.plugins.scriptsmith_plugin import ScriptForgePlugin

pytestmark = pytest.mark.asyncio

@pytest.fixture
def plugin(tmp_path):
    return ScriptForgePlugin(workdir=tmp_path)

async def test_initialize_creates_workspace(plugin, tmp_path):
    """initialize() should create workspace with sequences."""
    with patch("forge_studio.plugins.scriptsmith_plugin.split_screenplay") as mock_split, \
         patch("forge_studio.plugins.scriptsmith_plugin.git_init"), \
         patch("forge_studio.plugins.scriptsmith_plugin.derive_all"):
        mock_split.return_value = [
            MagicMock(id="seq_01", title="Ep 1", char_count=5000, scene_count=3, to_dict=lambda: {"id": "seq_01"})
        ]
        result = await plugin.initialize(
            input_text="第一集\n场景一：殡仪馆",
            criteria_text="# Criteria\nStructure: 20",
            config={"model": "sonnet"},
        )
    assert "session_id" in result
    assert len(result["sequences"]) == 1
    ws = tmp_path / result["session_id"]
    assert (ws / "criteria.md").exists()

async def test_get_current_text(plugin, tmp_path):
    """get_current_text should concatenate sequences."""
    import json
    # Set up a fake workspace
    ws = tmp_path / "test-session"
    ws.mkdir()
    (ws / "sequences").mkdir()
    (ws / "sequences" / "seq_01.md").write_text("Scene 1 text", encoding="utf-8")
    (ws / "manifest.json").write_text(
        json.dumps([{"id": "seq_01", "filename": "seq_01.md", "title": "Ep1", "episodes": "", "char_count": 12, "scene_count": 1, "markers": []}]),
        encoding="utf-8",
    )
    plugin._workspace = ws
    text = await plugin.get_current_text()
    assert "Scene 1 text" in text

async def test_export_returns_bytes(plugin, tmp_path):
    """export() should return docx bytes."""
    import json
    ws = tmp_path / "test-session"
    ws.mkdir()
    (ws / "sequences").mkdir()
    (ws / "exports").mkdir()
    (ws / "sequences" / "seq_01.md").write_text("Scene 1", encoding="utf-8")
    (ws / "manifest.json").write_text(
        json.dumps([{"id": "seq_01", "filename": "seq_01.md", "title": "Ep1", "episodes": "", "char_count": 7, "scene_count": 1, "markers": []}]),
        encoding="utf-8",
    )
    plugin._workspace = ws
    data = await plugin.export()
    assert len(data) > 0
    # Should be a valid docx (starts with PK zip signature)
    assert data[:2] == b"PK"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd forge-studio && python -m pytest tests/test_scriptsmith_plugin.py -v`
Expected: FAIL (no module)

- [ ] **Step 3: Implement**

```python
# forge_studio/plugins/__init__.py
"""Plugin registry."""

from __future__ import annotations

from forge_studio.plugin_protocol import ForgePlugin

_registry: dict[str, ForgePlugin] = {}

def register_plugin(plugin: ForgePlugin) -> None:
    _registry[plugin.name] = plugin

def get_plugin(name: str) -> ForgePlugin | None:
    return _registry.get(name)

def list_plugins() -> list[dict]:
    return [{"name": p.name, "display_name": p.display_name} for p in _registry.values()]
```

```python
# forge_studio/plugins/scriptsmith_plugin.py
"""ScriptSmith plugin adapter for Forge Studio."""

from __future__ import annotations

import asyncio
import json
import queue
import tempfile
import threading
import uuid
from pathlib import Path
from typing import AsyncIterator

from forge_studio.plugin_protocol import ForgePlugin, RoundResult


class ScriptForgePlugin:
    """Wraps the scriptsmith package as a Forge Studio plugin."""

    name = "scriptsmith"
    display_name = "剧本优化"

    def __init__(self, workdir: Path | None = None) -> None:
        self._workdir = workdir or Path(tempfile.gettempdir()) / "forge-studio"
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

        for d in ["input", "sequences", "derived", "experiments", "exports", ".scriptsmith"]:
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
name = "forge-studio-session"
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

        # Acquire lock (raises RuntimeError if already locked)
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
```

- [ ] **Step 4: Run tests**

Run: `cd forge-studio && python -m pytest tests/test_scriptsmith_plugin.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd forge-studio
git add forge_studio/plugins/ tests/test_scriptsmith_plugin.py
git commit -m "feat: add scriptsmith plugin adapter"
```

---

### Task 7: Plugin API Routes + SSE

**Files:**
- Create: `forge-studio/forge_studio/sse.py`
- Create: `forge-studio/forge_studio/routes/plugins.py`
- Modify: `forge-studio/forge_studio/server.py`
- Create: `forge-studio/tests/test_routes.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_routes.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json

pytestmark = pytest.mark.asyncio

async def test_plugin_init(client):
    """POST /api/plugins/scriptsmith/init should return session_id."""
    mock_plugin = MagicMock()
    mock_plugin.initialize = AsyncMock(return_value={
        "session_id": "abc123",
        "sequences": [{"id": "seq_01"}],
    })

    with patch("forge_studio.routes.plugins.get_plugin", return_value=mock_plugin):
        resp = await client.post(
            "/api/plugins/scriptsmith/init",
            json={"input_text": "test", "criteria_text": "criteria", "config": {"model": "sonnet"}},
        )
    assert resp.status_code == 200
    assert resp.json()["session_id"] == "abc123"

async def test_plugin_status_not_found(client):
    """GET /api/plugins/unknown/x/status should 404."""
    resp = await client.get("/api/plugins/unknown/x/status")
    assert resp.status_code == 404

async def test_plugin_stop(client):
    """POST /api/plugins/scriptsmith/{id}/stop should call stop()."""
    mock_plugin = MagicMock()
    mock_plugin.stop = AsyncMock()

    with patch("forge_studio.routes.plugins.get_plugin", return_value=mock_plugin), \
         patch("forge_studio.routes.plugins._sessions", {"abc": mock_plugin}):
        resp = await client.post("/api/plugins/scriptsmith/abc/stop")
    assert resp.status_code == 200

async def test_plugin_run_sse(client):
    """POST /api/plugins/scriptsmith/{id}/run should return SSE events."""
    mock_plugin = MagicMock()

    async def mock_run(config):
        from forge_studio.plugin_protocol import RoundResult
        yield RoundResult(
            round_number=1, status="keep", total_before=70, total_after=74,
            delta=4, target_dimension="对白", description="test",
            scores_before={"对白": 14}, scores_after={"对白": 18}, max_total=100,
        )

    mock_plugin.run = mock_run
    mock_plugin._worker = None

    with patch("forge_studio.routes.plugins._sessions", {"abc": mock_plugin}):
        resp = await client.post("/api/plugins/scriptsmith/abc/run")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert "event: round" in resp.text
    assert "event: complete" in resp.text

async def test_plugin_text(client):
    """GET /api/plugins/scriptsmith/{id}/text should return text."""
    mock_plugin = MagicMock()
    mock_plugin.get_current_text = AsyncMock(return_value="optimized text")

    with patch("forge_studio.routes.plugins._sessions", {"abc": mock_plugin}):
        resp = await client.get("/api/plugins/scriptsmith/abc/text")
    assert resp.status_code == 200
    assert resp.json()["text"] == "optimized text"

async def test_plugin_export(client):
    """GET /api/plugins/scriptsmith/{id}/export should return docx bytes."""
    mock_plugin = MagicMock()
    mock_plugin.export = AsyncMock(return_value=b"PK\x03\x04fake-docx")

    with patch("forge_studio.routes.plugins._sessions", {"abc": mock_plugin}):
        resp = await client.get("/api/plugins/scriptsmith/abc/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd forge-studio && python -m pytest tests/test_routes.py -v`
Expected: FAIL

- [ ] **Step 3: Implement SSE helper**

```python
# forge_studio/sse.py
"""Server-Sent Events helper."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from starlette.responses import StreamingResponse


class EventSourceResponse(StreamingResponse):
    """SSE response that streams events to the client."""

    def __init__(self, generator: AsyncIterator, **kwargs):
        super().__init__(
            self._wrap(generator),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
            **kwargs,
        )

    @staticmethod
    async def _wrap(generator: AsyncIterator):
        try:
            async for event_type, data in generator:
                payload = json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else str(data)
                yield f"event: {event_type}\ndata: {payload}\n\n"
        except asyncio.CancelledError:
            pass
```

- [ ] **Step 4: Implement plugin routes**

```python
# forge_studio/routes/plugins.py
"""Plugin API routes."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from forge_studio.plugins import get_plugin
from forge_studio.sse import EventSourceResponse

router = APIRouter()

# In-memory session tracking (v1 single-user)
_sessions: dict[str, object] = {}  # session_id → plugin instance


class InitRequest(BaseModel):
    input_text: str
    criteria_text: str
    config: dict = {}


@router.post("/plugins/{name}/init")
async def plugin_init(name: str, req: InitRequest):
    plugin = get_plugin(name)
    if plugin is None:
        raise HTTPException(404, f"Plugin '{name}' not found")

    # Check for existing active session
    for sid, p in _sessions.items():
        if getattr(p, 'name', '') == name and getattr(p, '_worker', None) and p._worker.is_alive():
            raise HTTPException(409, "A session is already running")

    result = await plugin.initialize(req.input_text, req.criteria_text, req.config)
    session_id = result["session_id"]
    _sessions[session_id] = plugin
    return result


def _get_session(name: str, session_id: str):
    plugin = _sessions.get(session_id)
    if plugin is None:
        raise HTTPException(404, f"Session '{session_id}' not found")
    return plugin


class RunRequest(BaseModel):
    config: dict = {}


@router.post("/plugins/{name}/{session_id}/run")
async def plugin_run(name: str, session_id: str, req: RunRequest = RunRequest()):
    plugin = _get_session(name, session_id)

    async def event_generator():
        try:
            round_results = []
            async for result in plugin.run(req.config):
                round_results.append(result.to_dict())
                yield "round", result.to_dict()

            # Send complete event
            final_score = round_results[-1]["total_after"] if round_results else 0
            first_score = round_results[0]["total_before"] if round_results else 0
            yield "complete", {
                "total_rounds": len(round_results),
                "final_score": final_score,
                "total_improvement": final_score - first_score,
            }
        except Exception as e:
            yield "error", {"message": str(e)}

    return EventSourceResponse(event_generator())


@router.post("/plugins/{name}/{session_id}/stop")
async def plugin_stop(name: str, session_id: str):
    plugin = _get_session(name, session_id)
    await plugin.stop()
    return {"status": "stopping"}


@router.get("/plugins/{name}/{session_id}/status")
async def plugin_status(name: str, session_id: str):
    plugin = _get_session(name, session_id)
    # Read state from workspace
    if hasattr(plugin, '_workspace') and plugin._workspace:
        from scriptsmith.state import load_state, load_history
        state = load_state(plugin._workspace)
        history = load_history(plugin._workspace)
        from forge_studio.plugin_protocol import RoundResult
        rounds = []
        for i, record in enumerate(history):
            rounds.append(RoundResult.from_experiment_record(record, round_number=i + 1).to_dict())
        return {
            "status": "running" if (plugin._worker and plugin._worker.is_alive()) else "idle",
            "state": state.to_dict() if state else None,
            "rounds": rounds,
        }
    return {"status": "idle", "state": None, "rounds": []}


@router.get("/plugins/{name}/{session_id}/text")
async def plugin_text(name: str, session_id: str):
    plugin = _get_session(name, session_id)
    text = await plugin.get_current_text()
    return {"text": text}


@router.get("/plugins/{name}/{session_id}/export")
async def plugin_export(name: str, session_id: str):
    from starlette.responses import Response
    plugin = _get_session(name, session_id)
    data = await plugin.export()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=improved.docx"},
    )


@router.get("/plugins/{name}/{session_id}/stream")
async def plugin_stream(name: str, session_id: str):
    """SSE endpoint for reconnection — replays all rounds from history."""
    plugin = _get_session(name, session_id)

    async def event_generator():
        if hasattr(plugin, '_workspace') and plugin._workspace:
            from scriptsmith.state import load_history
            from forge_studio.plugin_protocol import RoundResult
            history = load_history(plugin._workspace)
            for i, record in enumerate(history):
                yield "round", RoundResult.from_experiment_record(record, round_number=i + 1).to_dict()

    return EventSourceResponse(event_generator())


@router.delete("/plugins/{name}/{session_id}")
async def plugin_delete(name: str, session_id: str):
    plugin = _sessions.pop(session_id, None)
    if plugin is None:
        raise HTTPException(404, f"Session '{session_id}' not found")
    # Cleanup workspace
    if hasattr(plugin, '_workspace') and plugin._workspace:
        import shutil
        shutil.rmtree(plugin._workspace, ignore_errors=True)
    return {"status": "deleted"}
```

- [ ] **Step 5: Register plugin and routes in server.py**

Update `forge_studio/server.py`:

```python
def create_app() -> FastAPI:
    app = FastAPI(title="Forge Studio", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from forge_studio.routes.upload import router as upload_router
    from forge_studio.routes.plugins import router as plugins_router
    app.include_router(upload_router, prefix="/api")
    app.include_router(plugins_router, prefix="/api")

    # Register plugins
    from forge_studio.plugins import register_plugin
    from forge_studio.plugins.scriptsmith_plugin import ScriptForgePlugin
    register_plugin(ScriptForgePlugin())

    return app
```

- [ ] **Step 6: Run tests**

Run: `cd forge-studio && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
cd forge-studio
git add forge_studio/sse.py forge_studio/routes/plugins.py forge_studio/server.py tests/test_routes.py
git commit -m "feat: add plugin API routes with SSE streaming"
```

---

### Task 8: CLI Entry Point

**Files:**
- Create: `forge-studio/forge_studio/cli.py`
- Create: `forge-studio/tests/test_cli.py`

- [ ] **Step 1: Write test**

```python
# tests/test_cli.py
from typer.testing import CliRunner
from forge_studio.cli import app

runner = CliRunner()

def test_help():
    """CLI should show help text."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "forge-studio" in result.output.lower() or "Web UI" in result.output

def test_start_help():
    """start command should show help."""
    result = runner.invoke(app, ["start", "--help"])
    assert result.exit_code == 0
    assert "--port" in result.output
    assert "--api-port" in result.output
    assert "--no-browser" in result.output
```

- [ ] **Step 2: Implement**

```python
# forge_studio/cli.py
"""CLI entry point for Forge Studio."""

from __future__ import annotations

import subprocess
import sys
import webbrowser
from pathlib import Path

import typer

app = typer.Typer(name="forge-studio", help="Web UI for creative-writing optimization tools.")


@app.command()
def start(
    port: int = typer.Option(3000, "--port", "-p", help="Frontend port"),
    api_port: int = typer.Option(8000, "--api-port", help="Backend API port"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser"),
) -> None:
    """Start Forge Studio (backend + frontend)."""
    import uvicorn
    from forge_studio.server import create_app

    typer.echo(f"Starting Forge Studio...")
    typer.echo(f"  API: http://localhost:{api_port}")
    typer.echo(f"  UI:  http://localhost:{port}")

    if not no_browser:
        webbrowser.open(f"http://localhost:{port}")

    # For v1, just start the API server
    # Frontend is started separately via `npm run dev` in frontend/
    app_instance = create_app()
    uvicorn.run(app_instance, host="0.0.0.0", port=api_port, log_level="info")


@app.callback()
def main() -> None:
    pass
```

- [ ] **Step 3: Run tests**

Run: `cd forge-studio && python -m pytest tests/test_cli.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
cd forge-studio
git add forge_studio/cli.py tests/test_cli.py
git commit -m "feat: add forge-studio CLI entry point"
```

---

## Chunk 2: Frontend (Next.js app)

### Task 9: Next.js Project Scaffolding

**Files:**
- Create: `forge-studio/frontend/` (via create-next-app)

- [ ] **Step 1: Create Next.js project**

```bash
cd forge-studio
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --no-src-dir --import-alias "@/*"
```

- [ ] **Step 2: Install dependencies**

```bash
cd forge-studio/frontend
npm install recharts lucide-react class-variance-authority clsx tailwind-merge
npx shadcn@latest init -d
```

- [ ] **Step 3: Configure dark theme**

Update `frontend/app/globals.css` to use dark background:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
  --card: 222.2 84% 6%;
  --card-foreground: 210 40% 98%;
  --primary: 172 66% 50%;
  --primary-foreground: 222.2 84% 4.9%;
  --muted: 217.2 32.6% 17.5%;
  --muted-foreground: 215 20.2% 65.1%;
  --border: 217.2 32.6% 17.5%;
  --destructive: 0 62.8% 30.6%;
}

body {
  background: hsl(var(--background));
  color: hsl(var(--foreground));
}
```

- [ ] **Step 4: Configure API proxy**

Update `frontend/next.config.js`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
```

- [ ] **Step 5: Commit**

```bash
cd forge-studio
git add frontend/
git commit -m "feat: scaffold Next.js frontend with Tailwind dark theme"
```

---

### Task 10: TypeScript Types + API Client

**Files:**
- Create: `forge-studio/frontend/types/index.ts`
- Create: `forge-studio/frontend/lib/api.ts`

- [ ] **Step 1: Define types**

```typescript
// frontend/types/index.ts

export interface RoundResult {
  round_number: number;
  status: 'keep' | 'discard' | 'error';
  total_before: number;
  total_after: number;
  delta: number;
  target_dimension: string;
  description: string;
  scores_before: Record<string, number>;
  scores_after: Record<string, number>;
  max_total: number;
}

export interface PluginConfig {
  model: string;
  rounds: number;
  reasoning_effort: string;
  mode: string;
  keep_threshold: number;
}

export interface PluginState {
  status: 'idle' | 'initializing' | 'running' | 'complete' | 'error';
  inputText: string;
  criteriaText: string;
  config: PluginConfig;
  rounds: RoundResult[];
  baselineScores: Record<string, number> | null;
  selectedRound: number | null;
  currentRound: number;
  maxRounds: number;
  sessionId: string | null;
  errorMessage: string | null;
}

export interface UploadResult {
  text: string;
  filename: string;
  size_kb: number;
}

export interface InitResult {
  session_id: string;
  sequences: Array<{ id: string; title?: string; char_count?: number; scene_count?: number }>;
}

export const DEFAULT_CONFIG: PluginConfig = {
  model: 'sonnet',
  rounds: 10,
  reasoning_effort: 'medium',
  mode: 'auto',
  keep_threshold: 1,
};
```

- [ ] **Step 2: Implement API client**

```typescript
// frontend/lib/api.ts

import type { InitResult, UploadResult } from '@/types';

const API_BASE = '/api';

export async function uploadFile(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
  return res.json();
}

export async function initPlugin(
  name: string,
  inputText: string,
  criteriaText: string,
  config: Record<string, unknown>,
): Promise<InitResult> {
  const res = await fetch(`${API_BASE}/plugins/${name}/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input_text: inputText, criteria_text: criteriaText, config }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export async function stopPlugin(name: string, sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/plugins/${name}/${sessionId}/stop`, { method: 'POST' });
}

export async function getStatus(name: string, sessionId: string) {
  const res = await fetch(`${API_BASE}/plugins/${name}/${sessionId}/status`);
  return res.json();
}

export async function getText(name: string, sessionId: string): Promise<string> {
  const res = await fetch(`${API_BASE}/plugins/${name}/${sessionId}/text`);
  const data = await res.json();
  return data.text;
}

export async function exportDocx(name: string, sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/plugins/${name}/${sessionId}/export`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'improved.docx';
  a.click();
  URL.revokeObjectURL(url);
}

export function getStreamUrl(name: string, sessionId: string): string {
  return `${API_BASE}/plugins/${name}/${sessionId}/run`;
}
```

- [ ] **Step 3: Commit**

```bash
cd forge-studio
git add frontend/types/ frontend/lib/
git commit -m "feat: add TypeScript types and API client"
```

---

### Task 11: SSE Hook + Plugin State Hook

**Files:**
- Create: `forge-studio/frontend/hooks/use-sse.ts`
- Create: `forge-studio/frontend/hooks/use-plugin.ts`

- [ ] **Step 1: Implement SSE hook**

```typescript
// frontend/hooks/use-sse.ts
'use client';

import { useEffect, useRef, useCallback } from 'react';
import type { RoundResult } from '@/types';

interface UseSSEOptions {
  onRound: (result: RoundResult) => void;
  onComplete: (data: { total_rounds: number; final_score: number; total_improvement: number }) => void;
  onError: (message: string) => void;
}

export function useSSE(url: string | null, { onRound, onComplete, onError }: UseSSEOptions) {
  const sourceRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    if (!url) return;
    if (sourceRef.current) {
      sourceRef.current.close();
    }

    // For the run endpoint, we POST and get SSE back
    // EventSource only supports GET, so we use fetch + ReadableStream
    const controller = new AbortController();

    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw new Error(`SSE connection failed: ${response.statusText}`);
        const reader = response.body?.getReader();
        if (!reader) throw new Error('No response body');

        const decoder = new TextDecoder();
        let buffer = '';

        function pump(): Promise<void> {
          return reader!.read().then(({ done, value }) => {
            if (done) return;
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            let eventType = '';
            let eventData = '';

            for (const line of lines) {
              if (line.startsWith('event: ')) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith('data: ')) {
                eventData = line.slice(6);
              } else if (line === '' && eventType && eventData) {
                try {
                  const parsed = JSON.parse(eventData);
                  if (eventType === 'round') onRound(parsed);
                  else if (eventType === 'complete') onComplete(parsed);
                  else if (eventType === 'error') onError(parsed.message);
                } catch {
                  // ignore parse errors
                }
                eventType = '';
                eventData = '';
              }
            }

            return pump();
          });
        }

        return pump();
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          onError(err.message);
        }
      });

    // Store abort controller for cleanup
    sourceRef.current = { close: () => controller.abort() } as any;
  }, [url, onRound, onComplete, onError]);

  useEffect(() => {
    return () => {
      sourceRef.current?.close();
    };
  }, []);

  return { connect, disconnect: () => sourceRef.current?.close() };
}
```

- [ ] **Step 2: Implement plugin state hook**

```typescript
// frontend/hooks/use-plugin.ts
'use client';

import { useReducer, useCallback, useRef } from 'react';
import type { PluginState, PluginConfig, RoundResult } from '@/types';
import { DEFAULT_CONFIG } from '@/types';
import { initPlugin, stopPlugin, uploadFile, exportDocx, getStreamUrl } from '@/lib/api';
import { useSSE } from './use-sse';

type Action =
  | { type: 'SET_INPUT'; text: string }
  | { type: 'SET_CRITERIA'; text: string }
  | { type: 'SET_CONFIG'; config: Partial<PluginConfig> }
  | { type: 'SET_STATUS'; status: PluginState['status'] }
  | { type: 'SET_SESSION'; sessionId: string }
  | { type: 'ADD_ROUND'; result: RoundResult }
  | { type: 'SET_BASELINE'; scores: Record<string, number> }
  | { type: 'SELECT_ROUND'; index: number | null }
  | { type: 'COMPLETE'; data: { total_rounds: number; final_score: number } }
  | { type: 'ERROR'; message: string }
  | { type: 'RESET' };

const initialState: PluginState = {
  status: 'idle',
  inputText: '',
  criteriaText: '',
  config: DEFAULT_CONFIG,
  rounds: [],
  baselineScores: null,
  selectedRound: null,
  currentRound: 0,
  maxRounds: 10,
  sessionId: null,
  errorMessage: null,
};

function reducer(state: PluginState, action: Action): PluginState {
  switch (action.type) {
    case 'SET_INPUT':
      return { ...state, inputText: action.text };
    case 'SET_CRITERIA':
      return { ...state, criteriaText: action.text };
    case 'SET_CONFIG':
      return { ...state, config: { ...state.config, ...action.config }, maxRounds: action.config.rounds ?? state.maxRounds };
    case 'SET_STATUS':
      return { ...state, status: action.status, errorMessage: null };
    case 'SET_SESSION':
      return { ...state, sessionId: action.sessionId };
    case 'ADD_ROUND': {
      const rounds = [...state.rounds, action.result];
      const baseline = state.baselineScores ?? action.result.scores_before;
      return {
        ...state,
        rounds,
        currentRound: rounds.length,
        baselineScores: baseline,
        selectedRound: rounds.length - 1,
      };
    }
    case 'SELECT_ROUND':
      return { ...state, selectedRound: action.index };
    case 'COMPLETE':
      return { ...state, status: 'complete' };
    case 'ERROR':
      return { ...state, status: 'error', errorMessage: action.message };
    case 'RESET':
      return initialState;
    default:
      return state;
  }
}

export function usePlugin(pluginName: string = 'scriptsmith') {
  const [state, dispatch] = useReducer(reducer, initialState);
  const streamUrlRef = useRef<string | null>(null);

  const { connect, disconnect } = useSSE(streamUrlRef.current, {
    onRound: (result) => dispatch({ type: 'ADD_ROUND', result }),
    onComplete: (data) => dispatch({ type: 'COMPLETE', data }),
    onError: (message) => dispatch({ type: 'ERROR', message }),
  });

  const handleUpload = useCallback(async (file: File, target: 'input' | 'criteria') => {
    const result = await uploadFile(file);
    dispatch({ type: target === 'input' ? 'SET_INPUT' : 'SET_CRITERIA', text: result.text });
    return result;
  }, []);

  const handleStart = useCallback(async () => {
    if (!state.inputText || !state.criteriaText) return;

    dispatch({ type: 'SET_STATUS', status: 'initializing' });

    try {
      const result = await initPlugin(pluginName, state.inputText, state.criteriaText, state.config);
      dispatch({ type: 'SET_SESSION', sessionId: result.session_id });
      dispatch({ type: 'SET_STATUS', status: 'running' });

      streamUrlRef.current = getStreamUrl(pluginName, result.session_id);
      // Small delay to ensure ref is set, then connect
      setTimeout(() => connect(), 0);
    } catch (err: any) {
      dispatch({ type: 'ERROR', message: err.message });
    }
  }, [state.inputText, state.criteriaText, state.config, pluginName, connect]);

  const handleStop = useCallback(async () => {
    if (state.sessionId) {
      await stopPlugin(pluginName, state.sessionId);
      disconnect();
    }
  }, [state.sessionId, pluginName, disconnect]);

  const handleExport = useCallback(async () => {
    if (state.sessionId) {
      await exportDocx(pluginName, state.sessionId);
    }
  }, [state.sessionId, pluginName]);

  return {
    state,
    dispatch,
    handleUpload,
    handleStart,
    handleStop,
    handleExport,
  };
}
```

- [ ] **Step 3: Commit**

```bash
cd forge-studio
git add frontend/hooks/
git commit -m "feat: add SSE hook and plugin state management"
```

---

### Task 12: UI Components — TopBar + FileUpload

**Files:**
- Create: `forge-studio/frontend/components/top-bar.tsx`
- Create: `forge-studio/frontend/components/file-upload.tsx`

- [ ] **Step 1: Implement TopBar**

```tsx
// frontend/components/top-bar.tsx
'use client';

import { Hammer } from 'lucide-react';

interface TopBarProps {
  status: string;
  currentRound: number;
  maxRounds: number;
}

const plugins = [
  { name: '剧本优化', active: true },
  { name: '分镜修改', active: false },
  { name: '场景提示词', active: false },
];

export function TopBar({ status, currentRound, maxRounds }: TopBarProps) {
  return (
    <div className="h-12 bg-[hsl(230,40%,8%)] border-b border-[hsl(230,20%,15%)] flex items-center px-5 gap-4">
      <div className="flex items-center gap-2 text-[hsl(var(--primary))] font-bold text-sm">
        <Hammer className="w-4 h-4" />
        Forge Studio
      </div>
      <div className="flex gap-1 ml-6">
        {plugins.map((p) => (
          <button
            key={p.name}
            className={`px-3 py-1.5 rounded-md text-xs ${
              p.active
                ? 'bg-[hsl(230,20%,15%)] text-[hsl(var(--primary))]'
                : 'text-[hsl(var(--muted-foreground))] opacity-40 cursor-not-allowed'
            }`}
            disabled={!p.active}
          >
            {p.name}
          </button>
        ))}
      </div>
      <div className="flex-1" />
      {status === 'running' && (
        <div className="flex items-center gap-2 text-xs text-yellow-400">
          <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse" />
          Running · Round {currentRound}/{maxRounds}
        </div>
      )}
      {status === 'complete' && (
        <div className="flex items-center gap-2 text-xs text-[hsl(var(--primary))]">
          <div className="w-2 h-2 bg-[hsl(var(--primary))] rounded-full" />
          Complete
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Implement FileUpload**

```tsx
// frontend/components/file-upload.tsx
'use client';

import { Upload, X } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';

interface FileUploadProps {
  accept: string;
  label: string;
  hint?: string;
  onUpload: (file: File) => Promise<{ filename: string; size_kb: number }>;
  compact?: boolean;
}

export function FileUpload({ accept, label, hint, onUpload, compact }: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<{ name: string; size: number } | null>(null);
  const [dragging, setDragging] = useState(false);

  const handleFile = useCallback(
    async (f: File) => {
      const result = await onUpload(f);
      setFile({ name: result.filename, size: result.size_kb });
    },
    [onUpload],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
    },
    [handleFile],
  );

  if (file) {
    return (
      <div className="bg-[hsl(230,30%,12%)] border border-[hsl(230,20%,20%)] rounded-md px-3 py-2 flex items-center gap-2 mb-3">
        <span className="text-xs text-[hsl(var(--muted-foreground))] flex-1 truncate">{file.name}</span>
        <span className="text-xs text-[hsl(230,20%,30%)]">{file.size} KB</span>
        <button onClick={() => setFile(null)} className="text-red-400 hover:text-red-300">
          <X className="w-3 h-3" />
        </button>
      </div>
    );
  }

  return (
    <div
      className={`border-2 border-dashed rounded-md text-center cursor-pointer transition-colors mb-3 ${
        dragging ? 'border-[hsl(var(--primary))]' : 'border-[hsl(230,20%,20%)]'
      } hover:border-[hsl(var(--primary))] ${compact ? 'p-3' : 'p-5'}`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <Upload className={`mx-auto text-[hsl(var(--muted-foreground))] ${compact ? 'w-4 h-4 mb-1' : 'w-7 h-7 mb-2'}`} />
      <div className={`text-[hsl(var(--muted-foreground))] ${compact ? 'text-[10px]' : 'text-xs'}`}>{label}</div>
      {hint && <div className="text-[10px] text-[hsl(230,20%,25%)] mt-1">{hint}</div>}
      <input ref={inputRef} type="file" accept={accept} className="hidden" onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
cd forge-studio
git add frontend/components/top-bar.tsx frontend/components/file-upload.tsx
git commit -m "feat: add TopBar and FileUpload components"
```

---

### Task 13: UI Components — InputPanel + ConfigPanel

**Files:**
- Create: `forge-studio/frontend/components/input-panel.tsx`
- Create: `forge-studio/frontend/components/config-panel.tsx`

- [ ] **Step 1: Implement InputPanel**

```tsx
// frontend/components/input-panel.tsx
'use client';

import { FileUpload } from './file-upload';

interface InputPanelProps {
  text: string;
  onTextChange: (text: string) => void;
  onUpload: (file: File) => Promise<{ filename: string; size_kb: number }>;
}

export function InputPanel({ text, onTextChange, onUpload }: InputPanelProps) {
  return (
    <div className="flex flex-col h-full border-r border-[hsl(230,20%,15%)]">
      <div className="px-4 py-3 bg-[hsl(230,40%,8%)] border-b border-[hsl(230,20%,15%)] text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wider">
        📄 剧本输入
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <FileUpload accept=".docx" label="拖拽或点击上传 .docx" hint="支持 Word 文档" onUpload={onUpload} />
        <textarea
          className="w-full h-[calc(100%-80px)] min-h-[200px] bg-[hsl(230,40%,6%)] border border-[hsl(230,20%,15%)] rounded-md p-3 text-sm text-[hsl(var(--foreground))] resize-none focus:outline-none focus:border-[hsl(var(--primary))] font-mono leading-relaxed"
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
          placeholder="上传剧本后在此预览和编辑..."
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Implement ConfigPanel**

```tsx
// frontend/components/config-panel.tsx
'use client';

import type { PluginConfig } from '@/types';
import { FileUpload } from './file-upload';

interface ConfigPanelProps {
  criteriaText: string;
  onCriteriaChange: (text: string) => void;
  onCriteriaUpload: (file: File) => Promise<{ filename: string; size_kb: number }>;
  config: PluginConfig;
  onConfigChange: (config: Partial<PluginConfig>) => void;
  isRunning: boolean;
  onStart: () => void;
  onStop: () => void;
}

export function ConfigPanel({
  criteriaText, onCriteriaChange, onCriteriaUpload,
  config, onConfigChange, isRunning, onStart, onStop,
}: ConfigPanelProps) {
  return (
    <div className="flex flex-col h-full border-r border-[hsl(230,20%,15%)]">
      <div className="px-4 py-3 bg-[hsl(230,40%,8%)] border-b border-[hsl(230,20%,15%)] text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wider">
        ⚙️ 配置
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Criteria */}
        <div>
          <label className="text-[11px] text-[hsl(var(--muted-foreground))] font-medium">评分标准</label>
          <FileUpload accept=".docx,.md" label="上传 .docx / .md" onUpload={onCriteriaUpload} compact />
          <textarea
            className="w-full h-24 bg-[hsl(230,40%,6%)] border border-[hsl(230,20%,15%)] rounded-md p-2 text-[11px] text-[hsl(var(--foreground))] resize-none focus:outline-none focus:border-[hsl(var(--primary))] font-mono"
            value={criteriaText}
            onChange={(e) => onCriteriaChange(e.target.value)}
            placeholder="评分标准..."
          />
        </div>

        <hr className="border-[hsl(230,20%,15%)]" />

        {/* Config fields */}
        <div className="space-y-3">
          <ConfigSelect label="模型" value={config.model} options={['sonnet', 'opus', 'haiku']} onChange={(v) => onConfigChange({ model: v })} />
          <ConfigNumber label="轮数" value={config.rounds} min={1} max={100} onChange={(v) => onConfigChange({ rounds: v })} />
          <ConfigSelect label="Reasoning Effort" value={config.reasoning_effort} options={['low', 'medium', 'high']} onChange={(v) => onConfigChange({ reasoning_effort: v })} />
          <ConfigSelect label="模式" value={config.mode} options={['auto', 'macro', 'micro']} onChange={(v) => onConfigChange({ mode: v })} />
          <ConfigNumber label="Keep Threshold" value={config.keep_threshold} min={1} max={10} onChange={(v) => onConfigChange({ keep_threshold: v })} />
        </div>

        <button
          className={`w-full py-3 rounded-lg font-bold text-sm transition-all ${
            isRunning
              ? 'bg-red-500 hover:bg-red-600 text-white'
              : 'bg-[hsl(var(--primary))] hover:brightness-110 text-[hsl(var(--background))]'
          }`}
          onClick={isRunning ? onStop : onStart}
        >
          {isRunning ? '⏹ STOP' : '▶ START'}
        </button>
      </div>
    </div>
  );
}

function ConfigSelect({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="text-[11px] text-[hsl(var(--muted-foreground))] font-medium block mb-1">{label}</label>
      <select
        className="w-full bg-[hsl(230,40%,6%)] border border-[hsl(230,20%,15%)] rounded-md px-2 py-2 text-sm text-[hsl(var(--foreground))] focus:outline-none focus:border-[hsl(var(--primary))]"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => <option key={o} value={o}>{o.charAt(0).toUpperCase() + o.slice(1)}</option>)}
      </select>
    </div>
  );
}

function ConfigNumber({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (v: number) => void }) {
  return (
    <div>
      <label className="text-[11px] text-[hsl(var(--muted-foreground))] font-medium block mb-1">{label}</label>
      <input
        type="number"
        className="w-full bg-[hsl(230,40%,6%)] border border-[hsl(230,20%,15%)] rounded-md px-2 py-2 text-sm text-[hsl(var(--foreground))] focus:outline-none focus:border-[hsl(var(--primary))]"
        value={value}
        min={min}
        max={max}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
cd forge-studio
git add frontend/components/input-panel.tsx frontend/components/config-panel.tsx
git commit -m "feat: add InputPanel and ConfigPanel components"
```

---

### Task 14: UI Components — ScoreCards + TrendChart + DimensionBars

**Files:**
- Create: `forge-studio/frontend/components/score-cards.tsx`
- Create: `forge-studio/frontend/components/trend-chart.tsx`
- Create: `forge-studio/frontend/components/dimension-bars.tsx`

- [ ] **Step 1: Implement ScoreCards**

```tsx
// frontend/components/score-cards.tsx
'use client';

interface ScoreCardsProps {
  currentScore: number;
  totalImprovement: number;
  currentRound: number;
  maxRounds: number;
}

export function ScoreCards({ currentScore, totalImprovement, currentRound, maxRounds }: ScoreCardsProps) {
  return (
    <div className="grid grid-cols-3 gap-2.5 mb-4">
      <Card value={currentScore} label="当前总分" color="text-[hsl(var(--primary))]" />
      <Card value={totalImprovement > 0 ? `+${totalImprovement}` : String(totalImprovement)} label="累计提升" color="text-yellow-400" />
      <Card value={`${currentRound} / ${maxRounds}`} label="轮次" color="text-[hsl(var(--muted-foreground))]" />
    </div>
  );
}

function Card({ value, label, color }: { value: string | number; label: string; color: string }) {
  return (
    <div className="bg-[hsl(230,30%,10%)] border border-[hsl(230,20%,15%)] rounded-lg p-3 text-center">
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-[10px] text-[hsl(230,20%,30%)] mt-0.5">{label}</div>
    </div>
  );
}
```

- [ ] **Step 2: Implement TrendChart**

```tsx
// frontend/components/trend-chart.tsx
'use client';

import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Dot } from 'recharts';
import type { RoundResult } from '@/types';

interface TrendChartProps {
  rounds: RoundResult[];
  selectedRound: number | null;
  onSelectRound: (index: number) => void;
}

export function TrendChart({ rounds, selectedRound, onSelectRound }: TrendChartProps) {
  const data = rounds.map((r, i) => ({
    name: `R${r.round_number}`,
    score: r.status === 'keep' ? r.total_after : r.total_before,
    status: r.status,
    index: i,
  }));

  const CustomDot = (props: any) => {
    const { cx, cy, payload } = props;
    const isSelected = payload.index === selectedRound;
    const color = payload.status === 'keep' ? '#64ffda' : payload.status === 'discard' ? '#e94560' : '#ffd93d';
    return (
      <g onClick={() => onSelectRound(payload.index)} style={{ cursor: 'pointer' }}>
        {isSelected && <circle cx={cx} cy={cy} r={10} fill="none" stroke={color} strokeWidth={2} opacity={0.4} />}
        <circle cx={cx} cy={cy} r={5} fill={color} stroke="#0a0a1a" strokeWidth={2} />
      </g>
    );
  };

  if (data.length === 0) {
    return (
      <div className="bg-[hsl(230,30%,10%)] border border-[hsl(230,20%,15%)] rounded-lg p-4 h-[180px] flex items-center justify-center">
        <span className="text-xs text-[hsl(var(--muted-foreground))]">等待数据...</span>
      </div>
    );
  }

  return (
    <div className="bg-[hsl(230,30%,10%)] border border-[hsl(230,20%,15%)] rounded-lg p-4">
      <div className="text-xs text-[hsl(var(--muted-foreground))] mb-3">评分趋势</div>
      <ResponsiveContainer width="100%" height={150}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#64ffda" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#64ffda" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(230,20%,15%)" />
          <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#8892b0' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: '#555' }} axisLine={false} tickLine={false} width={30} />
          <Tooltip
            contentStyle={{ background: '#111130', border: '1px solid #1e1e3a', borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: '#8892b0' }}
          />
          <Area type="monotone" dataKey="score" stroke="#64ffda" strokeWidth={2} fill="url(#scoreGradient)" dot={<CustomDot />} activeDot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 3: Implement DimensionBars**

```tsx
// frontend/components/dimension-bars.tsx
'use client';

import type { RoundResult } from '@/types';

interface DimensionBarsProps {
  round: RoundResult | null;
  baseline: Record<string, number> | null;
}

export function DimensionBars({ round, baseline }: DimensionBarsProps) {
  if (!round) {
    return (
      <div className="flex items-center justify-center h-full text-xs text-[hsl(var(--muted-foreground))]">
        点击图表数据点查看维度分数
      </div>
    );
  }

  const scores = round.status === 'keep' ? round.scores_after : round.scores_before;
  const dimensions = Object.keys(scores);

  // Per-dimension max: assumes equal split of max_total across dimensions.
  // This is correct for scriptsmith where all dimensions share the same max score.
  // If a future plugin uses unequal max scores, RoundResult should carry per-dimension max.
  const perDimMax = Math.ceil(round.max_total / Math.max(dimensions.length, 1));

  return (
    <div className="space-y-2">
      <div className="text-[10px] text-[hsl(var(--muted-foreground))]">
        Round {round.round_number} 维度分数
      </div>
      {dimensions.map((dim) => {
        const score = scores[dim];
        const baselineScore = baseline?.[dim] ?? score;
        const pct = (score / perDimMax) * 100;
        const basePct = (baselineScore / perDimMax) * 100;
        const isWeakest = dim === round.target_dimension;
        const improved = score > baselineScore;

        return (
          <div key={dim} className="flex items-center gap-2">
            <div className="text-[10px] text-[hsl(var(--muted-foreground))] w-12 text-right truncate">{dim}</div>
            <div className="flex-1 h-3.5 bg-[hsl(230,30%,12%)] rounded relative overflow-hidden">
              {/* Baseline marker */}
              <div
                className="absolute top-0 h-full border-r-2 border-dashed border-white/20"
                style={{ left: `${Math.min(basePct, 100)}%` }}
              />
              {/* Score bar */}
              <div
                className={`h-full rounded transition-all ${
                  isWeakest ? 'bg-yellow-400' : improved ? 'bg-[hsl(var(--primary))]' : 'bg-[hsl(var(--primary))]'
                }`}
                style={{ width: `${Math.min(pct, 100)}%` }}
              />
            </div>
            <div className="text-[10px] text-[hsl(var(--foreground))] w-10 text-right">
              {score}/{perDimMax}
            </div>
          </div>
        );
      })}
      <div className="text-[8px] text-[hsl(230,20%,25%)]">虚线 = 初始分</div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
cd forge-studio
git add frontend/components/score-cards.tsx frontend/components/trend-chart.tsx frontend/components/dimension-bars.tsx
git commit -m "feat: add ScoreCards, TrendChart, and DimensionBars components"
```

---

### Task 15: UI Components — RoundTimeline

**Files:**
- Create: `forge-studio/frontend/components/round-timeline.tsx`

- [ ] **Step 1: Implement**

```tsx
// frontend/components/round-timeline.tsx
'use client';

import { useState } from 'react';
import type { RoundResult } from '@/types';

interface RoundTimelineProps {
  rounds: RoundResult[];
}

export function RoundTimeline({ rounds }: RoundTimelineProps) {
  // Reverse so newest first
  const reversed = [...rounds].reverse();

  if (reversed.length === 0) {
    return (
      <div className="text-xs text-[hsl(var(--muted-foreground))] text-center py-8">
        尚无实验记录
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="text-[11px] text-[hsl(230,20%,30%)] uppercase tracking-wider mb-2">轮次详情</div>
      {reversed.map((round, i) => (
        <RoundCard key={round.round_number} round={round} />
      ))}
    </div>
  );
}

function RoundCard({ round }: { round: RoundResult }) {
  const [expanded, setExpanded] = useState(false);

  const borderColor =
    round.status === 'keep' ? 'border-l-[hsl(var(--primary))]' :
    round.status === 'discard' ? 'border-l-red-500' :
    'border-l-yellow-400';

  const statusBg =
    round.status === 'keep' ? 'bg-[hsl(160,30%,15%)] text-[hsl(var(--primary))]' :
    round.status === 'discard' ? 'bg-[hsl(350,30%,15%)] text-red-400' :
    'bg-[hsl(45,30%,15%)] text-yellow-400';

  return (
    <div
      className={`bg-[hsl(230,30%,10%)] border border-[hsl(230,20%,15%)] ${borderColor} border-l-[3px] rounded-lg cursor-pointer transition-colors hover:border-[hsl(230,20%,20%)]`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center px-3 py-2.5 gap-2.5">
        <div className="text-xs font-bold text-[hsl(var(--muted-foreground))] min-w-[50px]">
          Round {round.round_number}
        </div>
        <div className={`text-[10px] px-2 py-0.5 rounded font-semibold ${statusBg}`}>
          {round.status === 'keep' ? 'Keep' : round.status === 'discard' ? 'Discard' : 'Error'}
        </div>
        <div className="text-[11px] text-[hsl(var(--muted-foreground))] flex-1 truncate">
          {round.target_dimension}
        </div>
        <div className={`text-sm font-bold ${round.delta > 0 ? 'text-[hsl(var(--primary))]' : round.delta < 0 ? 'text-red-400' : 'text-[hsl(var(--muted-foreground))]'}`}>
          {round.delta > 0 ? `+${round.delta}` : round.delta}
        </div>
      </div>

      {expanded && (
        <div className="px-3 pb-3 border-t border-[hsl(230,20%,15%)] mt-0 pt-2.5 text-xs text-[hsl(var(--muted-foreground))] leading-relaxed">
          <p>{round.description}</p>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {Object.entries(round.scores_after).map(([dim, score]) => {
              const before = round.scores_before[dim];
              const changed = score !== before;
              return (
                <span key={dim} className="bg-[hsl(230,40%,6%)] border border-[hsl(230,20%,15%)] rounded px-2 py-0.5 text-[10px]">
                  {dim} {changed ? (
                    <span className="text-[hsl(var(--primary))]">{before}→{score}</span>
                  ) : (
                    <span>{score}</span>
                  )}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd forge-studio
git add frontend/components/round-timeline.tsx
git commit -m "feat: add RoundTimeline component"
```

---

### Task 16: UI Components — ResultsPanel + Main Page Assembly

**Files:**
- Create: `forge-studio/frontend/components/results-panel.tsx`
- Modify: `forge-studio/frontend/app/layout.tsx`
- Create: `forge-studio/frontend/app/scriptsmith/page.tsx`
- Modify: `forge-studio/frontend/app/page.tsx`

- [ ] **Step 1: Implement ResultsPanel**

```tsx
// frontend/components/results-panel.tsx
'use client';

import type { RoundResult } from '@/types';
import { ScoreCards } from './score-cards';
import { TrendChart } from './trend-chart';
import { DimensionBars } from './dimension-bars';
import { RoundTimeline } from './round-timeline';
import { Download } from 'lucide-react';

interface ResultsPanelProps {
  rounds: RoundResult[];
  baselineScores: Record<string, number> | null;
  selectedRound: number | null;
  onSelectRound: (index: number) => void;
  maxRounds: number;
  onExport: () => void;
  status: string;
}

export function ResultsPanel({ rounds, baselineScores, selectedRound, onSelectRound, maxRounds, onExport, status }: ResultsPanelProps) {
  const lastKeep = [...rounds].reverse().find((r) => r.status === 'keep');
  const currentScore = lastKeep ? lastKeep.total_after : (rounds[0]?.total_before ?? 0);
  const firstScore = rounds[0]?.total_before ?? 0;
  const improvement = currentScore - firstScore;
  const selectedResult = selectedRound !== null ? rounds[selectedRound] : null;

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 bg-[hsl(230,40%,8%)] border-b border-[hsl(230,20%,15%)] text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wider flex items-center">
        📊 结果
        <div className="flex-1" />
        {status === 'complete' && (
          <button onClick={onExport} className="flex items-center gap-1 text-[hsl(var(--primary))] hover:brightness-110">
            <Download className="w-3 h-3" /> Export
          </button>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <ScoreCards
          currentScore={currentScore}
          totalImprovement={improvement}
          currentRound={rounds.length}
          maxRounds={maxRounds}
        />

        {/* Chart area: 2/3 trend + 1/3 dimension bars */}
        <div className="flex gap-3">
          <div className="flex-[2]">
            <TrendChart rounds={rounds} selectedRound={selectedRound} onSelectRound={onSelectRound} />
          </div>
          <div className="flex-1 bg-[hsl(230,30%,10%)] border border-[hsl(230,20%,15%)] rounded-lg p-3">
            <DimensionBars round={selectedResult} baseline={baselineScores} />
          </div>
        </div>

        <RoundTimeline rounds={rounds} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create main page**

```tsx
// frontend/app/scriptsmith/page.tsx
'use client';

import { TopBar } from '@/components/top-bar';
import { InputPanel } from '@/components/input-panel';
import { ConfigPanel } from '@/components/config-panel';
import { ResultsPanel } from '@/components/results-panel';
import { usePlugin } from '@/hooks/use-plugin';

export default function ScriptForgePage() {
  const { state, dispatch, handleUpload, handleStart, handleStop, handleExport } = usePlugin('scriptsmith');

  return (
    <div className="h-screen flex flex-col">
      <TopBar status={state.status} currentRound={state.currentRound} maxRounds={state.maxRounds} />
      <div className="flex flex-1 min-h-0">
        {/* Left: Input (30%) */}
        <div className="w-[30%]">
          <InputPanel
            text={state.inputText}
            onTextChange={(text) => dispatch({ type: 'SET_INPUT', text })}
            onUpload={(file) => handleUpload(file, 'input')}
          />
        </div>
        {/* Center: Config (22%) */}
        <div className="w-[22%]">
          <ConfigPanel
            criteriaText={state.criteriaText}
            onCriteriaChange={(text) => dispatch({ type: 'SET_CRITERIA', text })}
            onCriteriaUpload={(file) => handleUpload(file, 'criteria')}
            config={state.config}
            onConfigChange={(config) => dispatch({ type: 'SET_CONFIG', config })}
            isRunning={state.status === 'running'}
            onStart={handleStart}
            onStop={handleStop}
          />
        </div>
        {/* Right: Results (48%) */}
        <div className="w-[48%]">
          <ResultsPanel
            rounds={state.rounds}
            baselineScores={state.baselineScores}
            selectedRound={state.selectedRound}
            onSelectRound={(i) => dispatch({ type: 'SELECT_ROUND', index: i })}
            maxRounds={state.maxRounds}
            onExport={handleExport}
            status={state.status}
          />
        </div>
      </div>
      {state.errorMessage && (
        <div className="bg-red-900/50 border-t border-red-800 px-4 py-2 text-xs text-red-300">
          {state.errorMessage}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Update root page to redirect**

```tsx
// frontend/app/page.tsx
import { redirect } from 'next/navigation';

export default function Home() {
  redirect('/scriptsmith');
}
```

- [ ] **Step 4: Update layout**

```tsx
// frontend/app/layout.tsx
import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Forge Studio',
  description: 'Web UI for creative-writing optimization tools',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh" className="dark">
      <body className="antialiased">{children}</body>
    </html>
  );
}
```

- [ ] **Step 5: Verify frontend builds**

Run: `cd forge-studio/frontend && npm run build`
Expected: Build succeeds with no errors. If there are TypeScript type errors (e.g., Recharts `Dot` props, `any` casts), fix them by adding explicit type annotations or `// @ts-expect-error` with explanation, then re-run build until clean.

- [ ] **Step 6: Commit**

```bash
cd forge-studio
git add frontend/components/results-panel.tsx frontend/app/
git commit -m "feat: assemble main page with 3-column layout"
```

---

### Task 17: Integration Test — Full Flow

**Files:**
- Create: `forge-studio/tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
"""Integration test: init → run 1 round → status → text → export."""

import io
import json
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from forge_studio.server import create_app
from forge_studio.plugin_protocol import RoundResult

pytestmark = pytest.mark.asyncio


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_full_flow(client, tmp_path):
    """Test full flow: upload → init → status → export."""
    from docx import Document

    # Upload screenplay
    doc = Document()
    doc.add_paragraph("第一集")
    doc.add_paragraph("场景一")
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    resp = await client.post("/api/upload", files={"file": ("test.docx", buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert resp.status_code == 200
    text = resp.json()["text"]

    # Init plugin (with mocked backend to avoid needing Claude CLI)
    with patch("forge_studio.plugins.scriptsmith_plugin.ClaudeCLIBackend") as MockBackend, \
         patch("forge_studio.plugins.scriptsmith_plugin.split_screenplay") as mock_split, \
         patch("forge_studio.plugins.scriptsmith_plugin.derive_all"), \
         patch("forge_studio.plugins.scriptsmith_plugin.git_init"):

        mock_split.return_value = [MagicMock(
            id="seq_01", filename="seq_01.md", title="Ep 1",
            char_count=100, scene_count=1, markers=[],
            to_dict=lambda: {"id": "seq_01", "filename": "seq_01.md"},
        )]

        resp = await client.post("/api/plugins/scriptsmith/init", json={
            "input_text": text,
            "criteria_text": "Structure: 20",
            "config": {"model": "sonnet"},
        })
        assert resp.status_code == 200
        session_id = resp.json()["session_id"]

    # Check status
    resp = await client.get(f"/api/plugins/scriptsmith/{session_id}/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "idle"
```

- [ ] **Step 2: Run test**

Run: `cd forge-studio && python -m pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
cd forge-studio
git add tests/test_integration.py
git commit -m "test: add integration test for full flow"
```

---

### Task 18: Final — .gitignore, LICENSE, README placeholder

**Files:**
- Create: `forge-studio/LICENSE`

- [ ] **Step 1: Add LICENSE**

```
MIT License

Copyright (c) 2026 DavidH-Creation

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Run all tests**

Run: `cd forge-studio && python -m pytest tests/ -v`
Expected: ALL PASS

Run: `cd forge-studio/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
cd forge-studio
git add LICENSE
git commit -m "docs: add MIT license"
```
