# DramaLab Studio 鈥?Web UI Design Spec

**Date:** 2026-03-21
**Status:** Draft
**Scope:** v1 鈥?local single-user, architecture ready for future multi-user/cloud

---

## 1. Overview

DramaLab Studio is a unified web application that hosts multiple creative-writing optimization tools. Each tool follows the same pattern: **left input 鈫?center config/criteria 鈫?right results**. v1 ships the "ScriptSmith" plugin (screenplay optimization). Future plugins: Storyboard Revision, Scene/Character Prompt Generation.

### Architecture

```
dramalab-studio/
鈹溾攢鈹€ frontend/           # Next.js app (React, TypeScript, shadcn/ui)
鈹溾攢鈹€ server/             # FastAPI gateway
鈹斺攢鈹€ plugins/
    鈹斺攢鈹€ scriptsmith/   # Adapter to existing scriptsmith Python package
```

- **frontend/** 鈥?Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui, Recharts for charts
- **server/** 鈥?FastAPI, serves REST API, manages plugin lifecycle, streams round results via SSE
- **plugins/** 鈥?Each plugin is a Python module conforming to a `DramaLabPlugin` protocol

### Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Frontend framework | Next.js (React) | Best agent code generation quality, easiest auth/cloud path |
| Backend framework | FastAPI | Already Python ecosystem, async SSE support |
| Component library | shadcn/ui + Tailwind | Free, composable, dark theme built-in |
| Chart library | Recharts | React-native, SVG-based, supports click interactions |
| Layout | Fixed 3-column | All info visible simultaneously, fits the workflow |
| Communication | REST + SSE | REST for CRUD, SSE for streaming round results |
| v1 deployment | Local only | `dramalab-studio start` launches both server + frontend |

---

## 2. UI Layout

### 2.1 Top Bar (48px)

| Element | Position | Behavior |
|---|---|---|
| Logo "DramaLab Studio" | Left | Static |
| Plugin tabs | Left, after logo | "鍓ф湰浼樺寲" (active), "鍒嗛暅淇敼", "鍦烘櫙鎻愮ず璇? (greyed if no plugin) |
| Status indicator | Right | Idle / "Running 路 Round 5/10" with pulsing dot |

### 2.2 Left Panel 鈥?Input (30% width)

- **File upload zone** 鈥?Drag-and-drop or click to upload `.docx` file
- **File badge** 鈥?Shows filename, size, remove button after upload
- **Textarea** 鈥?Editable text preview of the uploaded screenplay. Backend parses docx 鈫?text on upload, user can edit before running. This is the canonical input.
- **Behavior:** Upload replaces textarea content. Manual edits are preserved until next upload.

### 2.3 Center Panel 鈥?Config (22% width)

**Top section: Criteria**
- Upload zone for `.docx` / `.md` criteria file (smaller)
- Textarea for criteria text (editable, same as left panel pattern)

**Separator line**

**Bottom section: Parameters**

| Parameter | Control | Default | Options |
|---|---|---|---|
| Model | Dropdown | Sonnet | Sonnet, Opus, Haiku |
| Rounds | Number input | 10 | 1鈥?00 |
| Reasoning Effort | Dropdown | Medium | Low, Medium, High (passed as `--reasoning-effort` flag to `claude -p`) |
| Mode | Dropdown | Auto | Auto, Macro, Micro |
| Keep Threshold | Number input | 1 | 1鈥?0 (passed to `run_loop` via new `keep_threshold` parameter; min 1 to preserve stall detection semantics) |

**Start/Stop button** 鈥?Full-width, green "鈻?START" / red "鈴?STOP" toggle

### 2.4 Right Panel 鈥?Results (48% width)

#### 2.4.1 Score Summary Cards (top)

Three metric cards in a row:
- **褰撳墠鎬诲垎** 鈥?Large number, green
- **绱鎻愬崌** 鈥?Delta from baseline, yellow with +/- sign
- **杞** 鈥?"Current / Max", blue

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
- Header: "Round N 缁村害鍒嗘暟" (updates on point click)
- Default: shows latest completed round

#### 2.4.3 Round Timeline (bottom, scrollable)

Vertical list of round cards, newest first:

**Round card (collapsed):**
- Left border color: green (keep), red (discard), yellow (running)
- Content: Round number | Status badge | Target dimension + focus | Delta (+N / -N)

**Round card (expanded, on click):**
- Description of what was modified and why
- Dimension score tags showing before鈫抋fter for changed dimensions

---

## 3. Plugin Architecture

### 3.1 DramaLabPlugin Protocol

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
    scores_before: dict[str, int]  # dimension 鈫?score
    scores_after: dict[str, int]   # dimension 鈫?score
    max_total: int                 # Sum of all dimension max scores (same for before/after)

class DramaLabPlugin(Protocol):
    name: str            # e.g. "scriptsmith"
    display_name: str    # e.g. "鍓ф湰浼樺寲"

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

1. **`ClaudeCLIBackend` 鈥?add `reasoning_effort` parameter:**
   - Constructor: `def __init__(self, model, timeout, reasoning_effort="medium")`
   - `query()`: append `--reasoning-effort {self.reasoning_effort}` to the `claude -p` command

2. **`run_loop` 鈥?add `keep_threshold` parameter and `on_round` callback:**
   - Signature: `def run_loop(workspace, mode, rounds, backend, sequence=None, keep_threshold=1, on_round=None, stop_event=None)`
   - Replace hardcoded `delta >= 1` with `delta >= keep_threshold`
   - After each round's `ExperimentRecord` is created, call `on_round(record)` if provided
   - Check `stop_event.is_set()` at the top of each iteration to support graceful cancellation

3. **No other changes** 鈥?all existing CLI behavior, models, and tests remain unchanged.

#### 3.2.2 Plugin Methods

- **`initialize()`** 鈥?Full workspace setup sequence:
  1. Create workspace directory + subdirs (`input/`, `sequences/`, `derived/`, `experiments/`, `exports/`, `.scriptsmith/`)
  2. Write input text to a temp `.docx` file via `python-docx` (one paragraph per line 鈥?`split_screenplay()` requires a real `.docx`)
  3. Copy criteria text to `criteria.md`
  4. Generate `project.toml` config
  5. Create `.gitignore`
  6. Run `split_screenplay()` to segment into sequences
  7. Run `derive_all()` to generate synopsis + context (if backend available)
  8. Run `git_init()` to set up git tracking
  9. Return `{session_id, sequences: [...]}`

- **`run()`** 鈥?Runs optimization in a background thread:
  1. Acquire workspace lock via `acquire_lock(workspace)` (if already locked, raise 鈫?API returns 409)
  2. Create `threading.Event` as `stop_event`
  3. Create `queue.Queue` (thread-safe) as result channel
  4. Define `on_round(record: ExperimentRecord)` callback that converts `ExperimentRecord` 鈫?`RoundResult` and puts it on the queue. Callback is invoked **after** keep/discard side effects and history persistence complete, so SSE and `/status` stay consistent.
  5. Spawn `threading.Thread` calling `run_loop(workspace, ..., on_round=on_round, stop_event=stop_event, keep_threshold=config["keep_threshold"])` wrapped in `try/finally` that releases the lock and puts a `None` sentinel on the queue
  6. Async bridge: poll `queue.Queue` via `asyncio.get_event_loop().run_in_executor()`, yield `RoundResult` objects until `None` sentinel

- **`stop()`** 鈥?Sets `stop_event`, which `run_loop` checks at the top of each iteration. The loop finishes the current round (no mid-round cancellation), then exits. Lock is released by the `finally` block in the worker thread.

- **`get_current_text()`** 鈥?On-demand read: loads manifest, concatenates all `sequences/*.md` in order. Not called during run (live left-panel updates are v2). Used for: initial display after init, and final text after run completes.

- **`export()`** 鈥?Calls `export_to_docx()`, reads the output file, returns bytes

---

## 4. API Design

### 4.1 REST Endpoints

v1 allows one active session per plugin at a time. Session ID is returned by `init` and required on all subsequent calls.

```
POST   /api/plugins/{name}/init                鈥?Upload input + criteria text, get session ID
POST   /api/plugins/{name}/{session_id}/run    鈥?Start optimization (returns immediately)
POST   /api/plugins/{name}/{session_id}/stop   鈥?Stop running loop
GET    /api/plugins/{name}/{session_id}/status  鈥?Get current state (full rounds history)
GET    /api/plugins/{name}/{session_id}/text    鈥?Get current optimized text
GET    /api/plugins/{name}/{session_id}/export  鈥?Download result docx
GET    /api/plugins/{name}/{session_id}/stream  鈥?SSE stream of round results
DELETE /api/plugins/{name}/{session_id}         鈥?Clean up workspace
```

If a session is already active and `init` is called again, return 409 Conflict.

### 4.2 SSE Event Format

```
event: round
data: {"round_number": 5, "status": "keep", "total_before": 74, "total_after": 78, "delta": 4, "target_dimension": "瀵圭櫧璐ㄩ噺", "description": "...", "scores_before": {...}, "scores_after": {...}, "max_total": 100}

event: complete
data: {"total_rounds": 10, "final_score": 82, "total_improvement": 16}

event: error
data: {"message": "Claude CLI not found", "round": 6}
```

### 4.3 File Upload

`POST /api/upload` 鈥?Multipart form upload. Accepts `.docx` (extracts text via python-docx) and `.md`/`.txt` (reads as-is). Returns extracted text.

```json
{"text": "绗竴闆?姝荤鏉ヤ簡\n\n鍦烘櫙涓€锛氭浠 路 澶淺n...", "filename": "screenplay.docx", "size_kb": 156}
```

---

## 5. Frontend Structure

```
frontend/
鈹溾攢鈹€ app/
鈹?  鈹溾攢鈹€ layout.tsx              # Root layout with TopBar
鈹?  鈹溾攢鈹€ page.tsx                # Redirect to default plugin
鈹?  鈹斺攢鈹€ [plugin]/
鈹?      鈹斺攢鈹€ page.tsx            # Plugin workspace page
鈹溾攢鈹€ components/
鈹?  鈹溾攢鈹€ top-bar.tsx             # Logo + plugin tabs + status
鈹?  鈹溾攢鈹€ input-panel.tsx         # Left: upload + textarea
鈹?  鈹溾攢鈹€ config-panel.tsx        # Center: criteria + params + start/stop
鈹?  鈹溾攢鈹€ results-panel.tsx       # Right: scores + chart + timeline
鈹?  鈹溾攢鈹€ score-cards.tsx         # Three metric cards
鈹?  鈹溾攢鈹€ trend-chart.tsx         # Recharts area chart + dimension bars
鈹?  鈹溾攢鈹€ round-timeline.tsx      # Round card list
鈹?  鈹斺攢鈹€ file-upload.tsx         # Drag-and-drop upload zone
鈹溾攢鈹€ hooks/
鈹?  鈹溾攢鈹€ use-sse.ts              # SSE connection hook
鈹?  鈹斺攢鈹€ use-plugin.ts           # Plugin state management
鈹溾攢鈹€ lib/
鈹?  鈹斺攢鈹€ api.ts                  # API client functions
鈹斺攢鈹€ types/
    鈹斺攢鈹€ index.ts                # Shared TypeScript types
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
  鈫?POST /api/upload 鈫?returns text
  鈫?Frontend displays text in left panel textarea

User edits criteria + sets config, clicks START
  鈫?POST /api/plugins/scriptsmith/init {input_text, criteria_text, config}
  鈫?Returns {session_id, sequences: [...]}
  鈫?POST /api/plugins/scriptsmith/{session_id}/run
  鈫?Frontend connects to GET /api/plugins/scriptsmith/{session_id}/stream

Each round completes
  鈫?SSE event: round result
  鈫?Frontend appends to rounds[], updates chart + timeline + score cards
  鈫?If user clicks a chart data point 鈫?selectedRound updates 鈫?dimension bars re-render

User clicks STOP
  鈫?POST /api/plugins/scriptsmith/{session_id}/stop
  鈫?SSE event: complete

User clicks Export
  鈫?GET /api/plugins/scriptsmith/{session_id}/export 鈫?downloads .docx
```

---

## 7. Startup

v1 is local-only. Single command to start everything:

```bash
dramalab-studio start [--port 3000]
```

This:
1. Starts FastAPI server on port 8000 (or configurable)
2. Starts Next.js dev server on port 3000
3. Opens browser to `http://localhost:3000`

For production build: `dramalab-studio build` bundles Next.js static export, FastAPI serves it directly from a single port.

---

## 8. Project Setup

```toml
# pyproject.toml (root)
[project]
name = "dramalab-studio"
dependencies = [
    "fastapi>=0.110",
    "uvicorn>=0.29",
    "python-multipart>=0.0.9",
    "scriptsmith>=0.1.0",       # local dependency
]

[project.scripts]
dramalab-studio = "dramalab_studio.cli:app"
```

```json
// frontend/package.json (illustrative 鈥?exact versions resolved by create-next-app + shadcn init)
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
- Interactive trend chart (click point 鈫?dimension breakdown)
- Expandable round timeline
- Export to docx
- Local-only, single user

### v1 Out of Scope
- Storyboard / Scene-prompt plugins (tab placeholders only)
- Multi-user auth / login
- Cloud deployment
- Database (state lives in scriptsmith workspace on disk)
- Live left-panel text update during run (v2 鈥?show modified sequences in real-time)
- Undo/redo for text edits
- Dark/light theme toggle (dark only for v1)
- Internationalization
- Mobile responsive layout

---

## 10. Testing Strategy

### Backend
- Unit tests: Plugin protocol compliance, API endpoint responses, SSE event format
- Integration test: Full init 鈫?run 1 round 鈫?stop 鈫?export flow with MockBackend

### Frontend
- Component tests: Each panel renders correctly with mock data
- Hook tests: `use-sse` correctly parses SSE events, reconnects on error
- E2E (Playwright): Upload file 鈫?configure 鈫?start 鈫?wait for 1 round result 鈫?verify chart updates 鈫?stop 鈫?export

---

## 11. Error Handling

| Error | Handling |
|---|---|
| Claude CLI not found | SSE error event, frontend shows alert banner, suggests installing Claude |
| Upload wrong file type | Frontend validation: left panel accepts `.docx` only; criteria panel accepts `.docx` and `.md`. Reject other formats before upload. |
| Backend crash mid-round | SSE connection drops, frontend shows "Connection lost, retrying..." with auto-reconnect. On reconnect: fetch `GET /status` to get full state (including all past rounds), then resubscribe to SSE stream. SSE does not replay missed events. |
| Score parsing failure | Round marked as "error" status, timeline shows error card, loop continues |
| Workspace lock conflict | API returns 409 Conflict, frontend shows "Another session is running" |

