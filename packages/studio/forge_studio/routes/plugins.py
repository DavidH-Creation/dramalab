"""Plugin API routes."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from forge_studio.plugins import get_plugin
from forge_studio.sse import EventSourceResponse

router = APIRouter()

# In-memory session tracking (v1 single-user)
_sessions: dict[str, object] = {}  # session_id -> plugin instance


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
    if hasattr(plugin, '_workspace') and plugin._workspace:
        from script_forge.state import load_state, load_history
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
    """SSE endpoint for reconnection - replays all rounds from history."""
    plugin = _get_session(name, session_id)

    async def event_generator():
        if hasattr(plugin, '_workspace') and plugin._workspace:
            from script_forge.state import load_history
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
    if hasattr(plugin, '_workspace') and plugin._workspace:
        import shutil
        shutil.rmtree(plugin._workspace, ignore_errors=True)
    return {"status": "deleted"}
