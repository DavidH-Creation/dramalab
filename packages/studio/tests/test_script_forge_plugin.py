import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock
from forge_studio.plugins.script_forge_plugin import ScriptForgePlugin

pytestmark = pytest.mark.asyncio


@pytest.fixture
def plugin(tmp_path):
    return ScriptForgePlugin(workdir=tmp_path)


async def test_initialize_creates_workspace(plugin, tmp_path):
    """initialize() should create workspace with sequences."""
    with patch("script_forge.splitter.split_screenplay") as mock_split, \
         patch("script_forge.git_ops.git_init"), \
         patch("script_forge.deriver.derive_all"):
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
    ws = tmp_path / "test-session"
    ws.mkdir()
    (ws / "sequences").mkdir()
    (ws / "sequences" / "seq_01.md").write_text("Scene 1 text", encoding="utf-8")
    (ws / "sequences" / "manifest.json").write_text(
        json.dumps({"sequences": [{"id": "seq_01", "filename": "seq_01.md", "title": "Ep1", "episodes": "", "char_count": 12, "scene_count": 1, "markers": []}]}),
        encoding="utf-8",
    )
    plugin._workspace = ws
    text = await plugin.get_current_text()
    assert "Scene 1 text" in text


async def test_export_returns_bytes(plugin, tmp_path):
    """export() should return docx bytes."""
    ws = tmp_path / "test-session"
    ws.mkdir()
    (ws / "sequences").mkdir()
    (ws / "exports").mkdir()
    (ws / "sequences" / "seq_01.md").write_text("Scene 1", encoding="utf-8")
    (ws / "sequences" / "manifest.json").write_text(
        json.dumps({"sequences": [{"id": "seq_01", "filename": "seq_01.md", "title": "Ep1", "episodes": "", "char_count": 7, "scene_count": 1, "markers": []}]}),
        encoding="utf-8",
    )
    plugin._workspace = ws
    data = await plugin.export()
    assert len(data) > 0
    assert data[:2] == b"PK"
