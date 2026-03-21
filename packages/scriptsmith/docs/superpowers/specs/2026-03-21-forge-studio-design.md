# Forge Studio — Web UI Design Spec

**Date:** 2026-03-21
**Status:** Draft
**Scope:** v1 — local single-user, architecture ready for future multi-user/cloud

---

## 1. Overview

Forge Studio is a unified web application that hosts multiple creative-writing optimization tools. Each tool follows the same pattern: **left input → center config/criteria → right results**. v1 ships the "Script Forge" plugin (screenplay optimization). Future plugins: Storyboard Revision, Scene/Character Prompt Generation.

### Architecture

```
forge-studio/
├── frontend/           # Next.js app (React, TypeScript, shadcn/ui)
├── server/             # FastAPI gateway
└── plugins/
    └── scriptsmith/   # Adapter to existing scriptsmith Python package
```

- **frontend/** — Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui, Recharts for charts
- **server/** — FastAPI, serves REST API, manages plugin lifecycle, streams round results via SSE
- **plugins/** — Each plugin is a Python module conforming to a `ForgePlugin` protocol

### Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Frontend framework | Next.js (React) | Best agent code generation quality, easiest auth/cloud path |
| Backend framework | FastAPI | Already Python ecosystem, async SSE support |
| Component library | shadcn/ui + Tailwind | Free, composable, dark theme built-in |
| Chart library | Recharts | React-native, SVG-based, supports click interactions |
| Layout | Fixed 3-column | All info visible simultaneously, fits the workflow |
| Communication | REST + SSE | REST for CRUD, SSE for streaming round results |
| v1 deployment | Local only | `forge-studio start` launches both server + frontend |

---

## 2. UI Layout

### 2.1 Top Bar (48px)

| Element | Position | Behavior |
|---|---|---|
| Logo "Forge Studio" | Left | Static |
| Plugin tabs | Left, after logo | "剧本优化" (active), "分镜修改", "场景提示词" (greyed if no plugin) |
| Status indicator | Right | Idle / "Running · Round 5/10" with pulsing dot |

### 2.2 Left Panel — Input (30% width)

- **File upload zone** — Drag-and-drop or click to upload `.docx` file
- **File badge** — Shows filename, size, remove button after upload
- **Textarea** — Editable text preview of the uploaded screenplay. Backend parses docx → text on upload, user can edit before running. This is the canonical input.
- **Behavior:** Upload replaces textarea content. Manual edits are preserved until next upload.

### 2.3 Center Panel — Config (22% width)

**Top section: Criteria**
- Upload zone for `.docx` / `.md` criteria file (smaller)
- Textarea for criteria text (editable, same as left panel pattern)

**Separator line**

**Bottom section: Parameters**

| Parameter | Control | Default | Options |
|---|---|---|---|
| Model | Dropdown | Sonnet | Sonnet, Opus, Haiku |
| Rounds | Number input | 10 | 1–100 |
| Reasoning Effort | Dropdown | Medium | Low, Medium, High (passed as `--reasoning-effort` flag to `claude -p`) |
| Mode | Dropdown | Auto | Auto, Macro, Micro |
| Keep Threshold | Number input | 1 | 1–10 (passed to `run_loop` via new `keep_threshold` parameter; min 1 to preserve stall detection semantics) |

**Start/Stop button** — Full-width, green "▶ START" / red "⏹ STOP" toggle

### 2.4 Right Panel — Results (48% width)

#### 2.4.1 Score Summary Cards (top)

Three metric cards in a row:
- **当前总分** — Large number, green
- **累计提升** — Delta from baseline, yellow with +/- sign
- **轮次** — "Current / Max", blue

#### 2.4.2 Trend Chart (middle)

**Layout:** Left 2/3 = line chart, Right 1/3 = dimension bar chart

**Line chart (Recharts `AreaChart`):**
- X-axis: Round numbers (R1, R2, ...)
- Y-axis: Total score
- Area fill with gradient (teal, 30% opacity)
- Data points colored by status: green (keep), red (discard), yellow (running)
- **Click interaction:** Clicking a data point updates the right-side dimension bar chart to show that round's scores. Active point gets a highlight ring.
- Horizontal dashed grid lines for reference

**Dimension bar chart (right side):**
- One horizontal bar per scoring dimension
- Bar fill shows current score, dashed vertical line shows initial (baseline) score
- Color: green if improved from baseline, yellow if weakest dimension
- Label: dimension name (left), score "N/M" (right)
- Header: "Round N 维度分数" (updates on point click)
- Default: shows latest completed round

#### 2.4.3 Round Timeline (bottom, scrollable)

Vertical list of round cards, newest first:

**Round card (collapsed):**
- Left border color: green (keep), red (discard), yellow (running)
- Content: Round number | Status badge | Target dimension + focus | Delta (+N / -N)

**Round card (expanded, on click):**
- Description of what was modified and why
- Dimension score tags showing before→after for changed dimensions

---

## 3. Plugin Architecture

### 3.1 ForgePlugin Protocol

```python
from typing import Protocol, AsyncIterator

class RoundResult:
    """Emitted after each optimization round."""
    round_number: int
    status: str          # "keep" | "discard" | "error"
    total_before: int
    total_after: int
    delta: int
    target_dimension: str
    description: str
    scores_before: dict[str, int]  # dimension → score
    scores_after: dict[str, int]   # dimension → score
    max_total: int                 # Sum of all dimension max scores (same for before/after)

class ForgePlugin(Protocol):
    name: str            # e.g. "scriptsmith"
    display_name: str    # e.g. "剧本优化"

    async def initialize(self, input_text: str, criteria_text: str, config: dict) -> dict:
        """Set up workspace, return initial state (e.g. sequence info)."""
        ...

    async def run(self, config: dict) -> AsyncIterator[RoundResult]:
        """Run optimization loop, yielding results per round."""
        ...

    async def stop(self) -> None:
        """Gracefully stop the running loop."""
        ...

    async def get_current_text(self) -> str:
        """Return current optimized text (for left panel live update)."""
        ...

    async def export(self) -> bytes:
        """Export result as docx bytes."""
        ...
```

### 3.2 ScriptSmith Plugin

The v1 plugin wraps the existing `scriptsmith` Python package.

#### 3.2.1 Required Changes to `scriptsmith` Core

The plugin adapter requires these targeted changes to the existing `scriptsmith` package:

1. **`ClaudeCLIBackend` — add `reasoning_effort` parameter:**
   - Constructor: `def __init__(self, model, timeout, reasoning_effort="medium")`
   - `query()`: append `--reasoning-effort {self.reasoning_effort}` to the `claude -p` command

2. **`run_loop` — add `keep_threshold` parameter and `on_round` callback:**
   - Signature: `def run_loop(workspace, mode, rounds, backend, sequence=None, keep_threshold=1, on_round=None, stop_event=None)`
   - Replace hardcoded `delta >= 1` with `delta >= keep_threshold`
   - After each round's `ExperimentRecord` is created, call `on_round(record)` if provided
   - Check `stop_event.is_set()` at the top of each iteration to support graceful cancellation

3. **No other changes** — all existing CLI behavior, models, and tests remain unchanged.

#### 3.2.2 Plugin Methods

- **`initialize()`** — Full workspace setup sequence:
  1. Create workspace directory + subdirs (`input/`, `sequences/`, `derived/`, `experiments/`, `exports/`, `.scriptsmith/`)
  2. Write input text to a temp `.docx` file via `python-docx` (one paragraph per line — `split_screenplay()` requires a real `.docx`)
  3. Copy criteria text to `criteria.md`
  4. Generate `project.toml` config
  5. Create `.gitignore`
  6. Run `split_screenplay()` to segment into sequences
  7. Run `derive_all()` to generate synopsis + context (if backend available)
  8. Run `git_init()` to set up git tracking
  9. Return `{session_id, sequences: [...]}`

- **`run()`** — Runs optimization in a background thread:
  1. Acquire workspace lock via `acquire_lock(workspace)` (if already locked, raise → API returns 409)
  2. Create `threading.Event` as `stop_event`
  3. Create `queue.Queue` (thread-safe) as result channel
  4. Define `on_round(record: ExperimentRecord)` callback that converts `ExperimentRecord` → `RoundResult` and puts it on the queue. Callback is invoked **after** keep/discard side effects and history persistence complete, so SSE and `/status` stay consistent.
  5. Spawn `threading.Thread` calling `run_loop(workspace, ..., on_round=on_round, stop_event=stop_event, keep_threshold=config["keep_threshold"])` wrapped in `try/finally` that releases the lock and puts a `None` sentinel on the queue
  6. Async bridge: poll `queue.Queue` via `asyncio.get_event_loop().run_in_executor()`, yield `RoundResult` objects until `None` sentinel

- **`stop()`** — Sets `stop_event`, which `run_loop` checks at the top of each iteration. The loop finishes the current round (no mid-round cancellation), then exits. Lock is released by the `finally` block in the worker thread.

- **`get_current_text()`** — On-demand read: loads manifest, concatenates all `sequences/*.md` in order. Not called during run (live left-panel updates are v2). Used for: initial display after init, and final text after run completes.

- **`export()`** — Calls `export_to_docx()`, reads the output file, returns bytes

---

## 4. API Design

### 4.1 REST Endpoints

v1 allows one active session per plugin at a time. Session ID is returned by `init` and required on all subsequent calls.

```
POST   /api/plugins/{name}/init                — Upload input + criteria text, get session ID
POST   /api/plugins/{name}/{session_id}/run    — Start optimization (returns immediately)
POST   /api/plugins/{name}/{session_id}/stop   — Stop running loop
GET    /api/plugins/{name}/{session_id}/status  — Get current state (full rounds history)
GET    /api/plugins/{name}/{session_id}/text    — Get current optimized text
GET    /api/plugins/{name}/{session_id}/export  — Download result docx
GET    /api/plugins/{name}/{session_id}/stream  — SSE stream of round results
DELETE /api/plugins/{name}/{session_id}         — Clean up workspace
```

If a session is already active and `init` is called again, return 409 Conflict.

### 4.2 SSE Event Format

```
event: round
data: {"round_number": 5, "status": "keep", "total_before": 74, "total_after": 78, "delta": 4, "target_dimension": "对白质量", "description": "...", "scores_before": {...}, "scores_after": {...}, "max_total": 100}

event: complete
data: {"total_rounds": 10, "final_score": 82, "total_improvement": 16}

event: error
data: {"message": "Claude CLI not found", "round": 6}
```

### 4.3 File Upload

`POST /api/upload` — Multipart form upload. Accepts `.docx` (extracts text via python-docx) and `.md`/`.txt` (reads as-is). Returns extracted text.

```json
{"text": "第一集 死神来了\n\n场景一：殡仪馆 · 夜\n...", "filename": "screenplay.docx", "size_kb": 156}
```

---

## 5. Frontend Structure

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout with TopBar
│   ├── page.tsx                # Redirect to default plugin
│   └── [plugin]/
│       └── page.tsx            # Plugin workspace page
├── components/
│   ├── top-bar.tsx             # Logo + plugin tabs + status
│   ├── input-panel.tsx         # Left: upload + textarea
│   ├── config-panel.tsx        # Center: criteria + params + start/stop
│   ├── results-panel.tsx       # Right: scores + chart + timeline
│   ├── score-cards.tsx         # Three metric cards
│   ├── trend-chart.tsx         # Recharts area chart + dimension bars
│   ├── round-timeline.tsx      # Round card list
│   └── file-upload.tsx         # Drag-and-drop upload zone
├── hooks/
│   ├── use-sse.ts              # SSE connection hook
│   └── use-plugin.ts           # Plugin state management
├── lib/
│   └── api.ts                  # API client functions
└── types/
    └── index.ts                # Shared TypeScript types
```

### State Management

Use React context + `useReducer` for plugin state. No external state library needed for v1.

```typescript
interface PluginState {
  status: 'idle' | 'initializing' | 'running' | 'complete' | 'error';
  inputText: string;
  criteriaText: string;
  config: PluginConfig;
  rounds: RoundResult[];
  baselineScores: Record<string, number> | null;
  selectedRound: number | null;  // For chart click interaction
  currentRound: number;
  maxRounds: number;
}
```

---

## 6. Data Flow

```
User uploads .docx
  → POST /api/upload → returns text
  → Frontend displays text in left panel textarea

User edits criteria + sets config, clicks START
  → POST /api/plugins/scriptsmith/init {input_text, criteria_text, config}
  → Returns {session_id, sequences: [...]}
  → POST /api/plugins/scriptsmith/{session_id}/run
  → Frontend connects to GET /api/plugins/scriptsmith/{session_id}/stream

Each round completes
  → SSE event: round result
  → Frontend appends to rounds[], updates chart + timeline + score cards
  → If user clicks a chart data point → selectedRound updates → dimension bars re-render

User clicks STOP
  → POST /api/plugins/scriptsmith/{session_id}/stop
  → SSE event: complete

User clicks Export
  → GET /api/plugins/scriptsmith/{session_id}/export → downloads .docx
```

---

## 7. Startup

v1 is local-only. Single command to start everything:

```bash
forge-studio start [--port 3000]
```

This:
1. Starts FastAPI server on port 8000 (or configurable)
2. Starts Next.js dev server on port 3000
3. Opens browser to `http://localhost:3000`

For production build: `forge-studio build` bundles Next.js static export, FastAPI serves it directly from a single port.

---

## 8. Project Setup

```toml
# pyproject.toml (root)
[project]
name = "forge-studio"
dependencies = [
    "fastapi>=0.110",
    "uvicorn>=0.29",
    "python-multipart>=0.0.9",
    "scriptsmith>=0.1.0",       # local dependency
]

[project.scripts]
forge-studio = "forge_studio.cli:app"
```

```json
// frontend/package.json (illustrative — exact versions resolved by create-next-app + shadcn init)
{
  "dependencies": {
    "next": "^14",
    "react": "^18",
    "recharts": "^2",
    "lucide-react": "^0.400",
    "class-variance-authority": "^0.7",
    "tailwindcss": "^3"
  }
}
```
Note: shadcn/ui components are copied into the project (not npm packages). Radix primitives are installed per-component by `npx shadcn-ui add`.

---

## 9. Scope Boundaries

### v1 In Scope
- ScriptSmith plugin only (other tabs visible but disabled)
- Fixed 3-column layout
- File upload + textarea editing for input and criteria
- 5 config parameters (model, rounds, reasoning effort, mode, keep threshold)
- Real-time SSE streaming of round results
- Interactive trend chart (click point → dimension breakdown)
- Expandable round timeline
- Export to docx
- Local-only, single user

### v1 Out of Scope
- Storyboard / Scene-prompt plugins (tab placeholders only)
- Multi-user auth / login
- Cloud deployment
- Database (state lives in scriptsmith workspace on disk)
- Live left-panel text update during run (v2 — show modified sequences in real-time)
- Undo/redo for text edits
- Dark/light theme toggle (dark only for v1)
- Internationalization
- Mobile responsive layout

---

## 10. Testing Strategy

### Backend
- Unit tests: Plugin protocol compliance, API endpoint responses, SSE event format
- Integration test: Full init → run 1 round → stop → export flow with MockBackend

### Frontend
- Component tests: Each panel renders correctly with mock data
- Hook tests: `use-sse` correctly parses SSE events, reconnects on error
- E2E (Playwright): Upload file → configure → start → wait for 1 round result → verify chart updates → stop → export

---

## 11. Error Handling

| Error | Handling |
|---|---|
| Claude CLI not found | SSE error event, frontend shows alert banner, suggests installing Claude |
| Upload wrong file type | Frontend validation: left panel accepts `.docx` only; criteria panel accepts `.docx` and `.md`. Reject other formats before upload. |
| Backend crash mid-round | SSE connection drops, frontend shows "Connection lost, retrying..." with auto-reconnect. On reconnect: fetch `GET /status` to get full state (including all past rounds), then resubscribe to SSE stream. SSE does not replay missed events. |
| Score parsing failure | Round marked as "error" status, timeline shows error card, loop continues |
| Workspace lock conflict | API returns 409 Conflict, frontend shows "Another session is running" |
