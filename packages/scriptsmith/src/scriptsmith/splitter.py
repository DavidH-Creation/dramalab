# src/scriptsmith/splitter.py
"""Split a screenplay docx into sequence segments."""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document

from scriptsmith.backends import BackendProtocol
from scriptsmith.models import SequenceInfo
from scriptsmith.workspace import atomic_write, save_manifest

# Marker patterns
_CHINESE_SCENE = re.compile(r"场(\d+)-(\d+)")
_CHINESE_EPISODE = re.compile(r"第(.{1,4})集")
_CHINESE_ACT = re.compile(r"第(.{1,3})幕")
_ENGLISH_SCENE = re.compile(r"(INT\.|EXT\.)\s+", re.IGNORECASE)
_ENGLISH_ACT = re.compile(r"ACT\s+(\w+)", re.IGNORECASE)
_ENGLISH_SCENE_NUM = re.compile(r"SCENE\s+(\d+)", re.IGNORECASE)


def extract_text_from_docx(path: Path) -> list[str]:
    """Extract paragraph texts from a docx file."""
    doc = Document(str(path))
    return [p.text for p in doc.paragraphs if p.text.strip()]


def find_markers(text: str) -> list[dict]:
    """Find structural markers (scenes, episodes, acts) in text.

    Returns list of {"type": "scene"|"episode"|"act", "match": str, "pos": int}.
    """
    markers: list[dict] = []

    for pattern, marker_type in [
        (_CHINESE_EPISODE, "episode"),
        (_CHINESE_ACT, "act"),
        (_CHINESE_SCENE, "scene"),
        (_ENGLISH_ACT, "act"),
        (_ENGLISH_SCENE_NUM, "scene"),
        (_ENGLISH_SCENE, "scene"),
    ]:
        for m in pattern.finditer(text):
            markers.append({
                "type": marker_type,
                "match": m.group(0),
                "pos": m.start(),
            })

    markers.sort(key=lambda x: x["pos"])
    return markers


def group_into_episodes(text: str, markers: list[dict]) -> list[tuple[str, str]]:
    """Group text into episodes based on markers.

    Returns list of (episode_label, episode_text) tuples.
    """
    # Find episode-level markers; fall back to scene markers if no episodes
    episode_markers = [m for m in markers if m["type"] == "episode"]
    if not episode_markers:
        episode_markers = [m for m in markers if m["type"] in ("act", "scene")]

    if not episode_markers:
        return [("full", text)]

    episodes: list[tuple[str, str]] = []
    for i, marker in enumerate(episode_markers):
        start = marker["pos"]
        end = episode_markers[i + 1]["pos"] if i + 1 < len(episode_markers) else len(text)
        label = marker["match"].strip()
        content = text[start:end].strip()
        if content:
            episodes.append((label, content))

    return episodes


def merge_into_sequences(
    episodes: list[tuple[str, str]],
    max_chars: int = 15000,
    min_chars: int = 0,
) -> list[tuple[str, str]]:
    """Merge episodes into sequences respecting size bounds.

    Greedy: accumulate episodes until adding next would exceed max_chars.
    Never split mid-episode.
    """
    if not episodes:
        return []

    sequences: list[tuple[str, str]] = []
    current_label_parts: list[str] = []
    current_text_parts: list[str] = []
    current_size = 0

    for label, content in episodes:
        content_len = len(content)

        if current_size > 0 and current_size + content_len > max_chars:
            # Flush current accumulator
            seq_label = f"{current_label_parts[0]}..{current_label_parts[-1]}" if len(current_label_parts) > 1 else current_label_parts[0]
            sequences.append((seq_label, "\n\n".join(current_text_parts)))
            current_label_parts = []
            current_text_parts = []
            current_size = 0

        current_label_parts.append(label)
        current_text_parts.append(content)
        current_size += content_len

    # Flush remaining
    if current_text_parts:
        seq_label = f"{current_label_parts[0]}..{current_label_parts[-1]}" if len(current_label_parts) > 1 else current_label_parts[0]
        sequences.append((seq_label, "\n\n".join(current_text_parts)))

    return sequences


def split_screenplay(
    docx_path: Path,
    workspace: Path,
    backend: BackendProtocol | None = None,
    max_chars: int = 15000,
) -> list[SequenceInfo]:
    """Split a screenplay docx into sequence files in workspace/sequences/.

    Returns list of SequenceInfo describing each segment.
    """
    paragraphs = extract_text_from_docx(docx_path)
    full_text = "\n".join(paragraphs)
    markers = find_markers(full_text)

    # If too few markers and backend available, use windowed fallback
    if len(markers) < 3 and backend is not None:
        markers = _windowed_marker_scan(full_text, backend)

    episodes = group_into_episodes(full_text, markers)
    sequences = merge_into_sequences(episodes, max_chars=max_chars)

    seq_dir = workspace / "sequences"
    seq_dir.mkdir(parents=True, exist_ok=True)
    infos: list[SequenceInfo] = []

    for i, (label, text) in enumerate(sequences, 1):
        seq_id = f"seq_{i:03d}"
        filename = f"{seq_id}_{_sanitize(label)}.md"
        atomic_write(seq_dir / filename, text)

        # Count scene markers within this sequence
        seq_markers = find_markers(text)
        scene_markers = [m["match"] for m in seq_markers if m["type"] == "scene"]

        info = SequenceInfo(
            id=seq_id,
            filename=filename,
            title=label,
            episodes=label,
            char_count=len(text),
            scene_count=len(scene_markers) or 1,
            markers=scene_markers,
        )
        infos.append(info)

    save_manifest(workspace, infos)
    return infos


def _windowed_marker_scan(
    text: str,
    backend: BackendProtocol,
    window_size: int = 5000,
    overlap: int = 500,
) -> list[dict]:
    """Scan full text in overlapping windows to discover markers via LLM."""
    all_markers: list[dict] = []
    pos = 0

    while pos < len(text):
        end = min(pos + window_size, len(text))
        window = text[pos:end]

        try:
            result = backend.query_json(
                f"以下是剧本的一个片段（字符位置 {pos}-{end}）。"
                f"请识别其中的结构性标记（场景/集/幕的分界点）。\n\n"
                f"---\n{window}\n---\n\n"
                f"输出 JSON 列表：[{{\"type\": \"scene|episode|act\", \"match\": \"标记文本\", \"offset\": 在片段中的字符偏移}}]"
            )
            if isinstance(result, list):
                for m in result:
                    m["pos"] = pos + m.get("offset", 0)
                    all_markers.append(m)
        except Exception:
            pass  # Window scan failure is non-fatal

        pos += window_size - overlap

    # Deduplicate by position (within 50 chars)
    unique: list[dict] = []
    for m in sorted(all_markers, key=lambda x: x.get("pos", 0)):
        if not unique or abs(m.get("pos", 0) - unique[-1].get("pos", 0)) > 50:
            unique.append(m)

    return unique


def _sanitize(label: str) -> str:
    """Sanitize a label for use in filenames."""
    safe = re.sub(r"[^\w\u4e00-\u9fff-]", "_", label)
    return safe[:40].strip("_") or "unnamed"
