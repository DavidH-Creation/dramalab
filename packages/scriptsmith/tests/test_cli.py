# tests/test_cli.py
"""Tests for scriptsmith.cli."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from scriptsmith.cli import app

runner = CliRunner()


class TestStatusCommand:
    def test_status_no_workspace(self, tmp_path: Path):
        result = runner.invoke(app, ["status", "--workspace", str(tmp_path)])
        assert result.exit_code != 0 or "error" in result.stdout.lower() or "missing" in result.stdout.lower()

    def test_status_with_workspace(self, tmp_workspace: Path):
        # Create a minimal results.tsv
        (tmp_workspace / "results.tsv").write_text(
            "id\tsequence\tmode\ttarget\thypothesis\tbefore\tafter\tdelta\tstatus\n"
            "1\tseq_001\tmicro\t人物对白\ttest\t18/30\t20/30\t2\tkeep\n",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["status", "--workspace", str(tmp_workspace)])
        assert result.exit_code == 0


class TestDeriveCommand:
    def test_derive_calls_backend(self, tmp_workspace: Path):
        with patch("scriptsmith.cli._make_backend") as mock_make:
            from scriptsmith.backends.mock import MockBackend
            mock_backend = MockBackend(responses=[
                json.dumps({"scenes": [], "characters": [], "arc_position": "起",
                             "key_events": [], "transitions": {"from_previous": "", "to_next": ""}}),
                json.dumps({"scenes": [], "characters": [], "arc_position": "承",
                             "key_events": [], "transitions": {"from_previous": "", "to_next": ""}}),
                "synopsis", "context",
            ])
            mock_make.return_value = mock_backend
            result = runner.invoke(app, ["derive", "--workspace", str(tmp_workspace)])
            assert result.exit_code == 0
