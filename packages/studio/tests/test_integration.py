"""Integration test: upload -> init -> status."""

import io
from unittest.mock import patch, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from dramalab_studio.server import create_app

pytestmark = pytest.mark.asyncio


@pytest.fixture
def app():
    return create_app()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_full_flow(client):
    """Test full flow: upload -> init -> status."""
    from docx import Document

    doc = Document()
    doc.add_paragraph("Episode 1")
    doc.add_paragraph("Scene 1")
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    resp = await client.post(
        "/api/upload",
        files={"file": ("test.docx", buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert resp.status_code == 200
    text = resp.json()["text"]

    with patch("scriptsmith.backends.claude_cli.ClaudeCLIBackend"), \
         patch("scriptsmith.splitter.split_screenplay") as mock_split, \
         patch("scriptsmith.deriver.derive_all"), \
         patch("scriptsmith.git_ops.git_init"):
        mock_split.return_value = [
            MagicMock(
                id="seq_01",
                filename="seq_01.md",
                title="Ep 1",
                char_count=100,
                scene_count=1,
                markers=[],
                to_dict=lambda: {"id": "seq_01", "filename": "seq_01.md"},
            )
        ]

        resp = await client.post(
            "/api/plugins/scriptsmith/init",
            json={
                "input_text": text,
                "criteria_text": "Structure: 20",
                "config": {"model": "sonnet"},
            },
        )
        assert resp.status_code == 200
        session_id = resp.json()["session_id"]

    resp = await client.get(f"/api/plugins/scriptsmith/{session_id}/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "idle"
