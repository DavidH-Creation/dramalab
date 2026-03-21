# tests/test_splitter.py
"""Tests for scriptsmith.splitter."""

from __future__ import annotations

from pathlib import Path

import pytest

from scriptsmith.splitter import (
    extract_text_from_docx,
    find_markers,
    group_into_episodes,
    merge_into_sequences,
)


class TestExtractText:
    def test_extracts_paragraphs(self, tmp_path: Path):
        """Test with the sample_script.docx fixture."""
        fixture = Path(__file__).parent / "fixtures" / "sample_script.docx"
        if not fixture.exists():
            pytest.skip("sample_script.docx fixture not generated yet")
        paragraphs = extract_text_from_docx(fixture)
        assert len(paragraphs) > 0
        # Should contain scene markers
        full_text = "\n".join(paragraphs)
        assert "场1-1" in full_text


class TestFindMarkers:
    def test_chinese_scene_markers(self):
        text = "场1-1 日 内 办公室\n内容\n场1-2 夜 外 街道\n内容"
        markers = find_markers(text)
        assert len(markers) >= 2

    def test_chinese_episode_markers(self):
        text = "第1集：新手村\n内容\n第2集：初战\n内容"
        markers = find_markers(text)
        assert len(markers) >= 2

    def test_english_int_ext_markers(self):
        text = "INT. OFFICE - DAY\nDialogue.\nEXT. STREET - NIGHT\nMore dialogue."
        markers = find_markers(text)
        assert len(markers) >= 2

    def test_no_markers(self):
        text = "这是一段没有场景标记的纯散文。"
        markers = find_markers(text)
        assert len(markers) == 0


class TestGroupIntoEpisodes:
    def test_groups_by_episode(self):
        text = "第1集\n场1-1\n内容A\n场1-2\n内容B\n第2集\n场2-1\n内容C"
        markers = find_markers(text)
        episodes = group_into_episodes(text, markers)
        assert len(episodes) >= 2

    def test_single_episode(self):
        text = "场1-1\n内容A\n场1-2\n内容B"
        markers = find_markers(text)
        episodes = group_into_episodes(text, markers)
        assert len(episodes) >= 1


class TestMergeIntoSequences:
    def test_respects_max_chars(self):
        # Create episodes of known sizes
        episodes = [
            ("ep1", "A" * 5000),
            ("ep2", "B" * 5000),
            ("ep3", "C" * 5000),
            ("ep4", "D" * 5000),
        ]
        sequences = merge_into_sequences(episodes, max_chars=12000)
        for _, text in sequences:
            assert len(text) <= 12000

    def test_never_splits_episode(self):
        episodes = [
            ("ep1", "A" * 14000),  # Just under max
        ]
        sequences = merge_into_sequences(episodes, min_chars=8000, max_chars=15000)
        assert len(sequences) == 1
        assert len(sequences[0][1]) == 14000
