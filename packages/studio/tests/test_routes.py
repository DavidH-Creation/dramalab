import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json

pytestmark = pytest.mark.asyncio

async def test_plugin_init(client):
    """POST /api/plugins/script-forge/init should return session_id."""
    mock_plugin = MagicMock()
    mock_plugin.initialize = AsyncMock(return_value={
        "session_id": "abc123",
        "sequences": [{"id": "seq_01"}],
    })

    with patch("dramalab_studio.routes.plugins.get_plugin", return_value=mock_plugin):
        resp = await client.post(
            "/api/plugins/script-forge/init",
            json={"input_text": "test", "criteria_text": "criteria", "config": {"model": "sonnet"}},
        )
    assert resp.status_code == 200
    assert resp.json()["session_id"] == "abc123"

async def test_plugin_status_not_found(client):
    """GET /api/plugins/unknown/x/status should 404."""
    resp = await client.get("/api/plugins/unknown/x/status")
    assert resp.status_code == 404

async def test_plugin_stop(client):
    """POST /api/plugins/script-forge/{id}/stop should call stop()."""
    mock_plugin = MagicMock()
    mock_plugin.stop = AsyncMock()

    with patch("dramalab_studio.routes.plugins.get_plugin", return_value=mock_plugin), \
         patch("dramalab_studio.routes.plugins._sessions", {"abc": mock_plugin}):
        resp = await client.post("/api/plugins/script-forge/abc/stop")
    assert resp.status_code == 200

async def test_plugin_run_sse(client):
    """POST /api/plugins/script-forge/{id}/run should return SSE events."""
    mock_plugin = MagicMock()

    async def mock_run(config):
        from dramalab_studio.plugin_protocol import RoundResult
        yield RoundResult(
            round_number=1, status="keep", total_before=70, total_after=74,
            delta=4, target_dimension="对白", description="test",
            scores_before={"对白": 14}, scores_after={"对白": 18}, max_total=100,
        )

    mock_plugin.run = mock_run
    mock_plugin._worker = None

    with patch("dramalab_studio.routes.plugins._sessions", {"abc": mock_plugin}):
        resp = await client.post("/api/plugins/script-forge/abc/run")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert "event: round" in resp.text
    assert "event: complete" in resp.text

async def test_plugin_text(client):
    """GET /api/plugins/script-forge/{id}/text should return text."""
    mock_plugin = MagicMock()
    mock_plugin.get_current_text = AsyncMock(return_value="optimized text")

    with patch("dramalab_studio.routes.plugins._sessions", {"abc": mock_plugin}):
        resp = await client.get("/api/plugins/script-forge/abc/text")
    assert resp.status_code == 200
    assert resp.json()["text"] == "optimized text"

async def test_plugin_export(client):
    """GET /api/plugins/script-forge/{id}/export should return docx bytes."""
    mock_plugin = MagicMock()
    mock_plugin.export = AsyncMock(return_value=b"PK\x03\x04fake-docx")

    with patch("dramalab_studio.routes.plugins._sessions", {"abc": mock_plugin}):
        resp = await client.get("/api/plugins/script-forge/abc/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
