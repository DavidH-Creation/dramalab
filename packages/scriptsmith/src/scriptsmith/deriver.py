# src/scriptsmith/deriver.py
"""Derive synopsis.md and context.md from sequences (cached, two-stage)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scriptsmith.backends import BackendProtocol
from scriptsmith.prompts import load_prompt
from scriptsmith.workspace import atomic_write, load_manifest


def derive_all(workspace: Path, backend: BackendProtocol) -> None:
    """Regenerate synopsis.md and context.md from sequences.

    Stage 1: Per-sequence structured summaries (cached by content hash).
    Stage 2: Aggregate summaries into global synopsis/context.
    """
    sequences = load_manifest(workspace)
    cache_dir = workspace / ".scriptsmith" / "summary_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Stage 1: Per-sequence summaries
    seq_summaries: list[dict] = []
    for seq in sequences:
        seq_path = workspace / "sequences" / seq.filename
        content = seq_path.read_text(encoding="utf-8")
        content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()[:12]
        cache_file = cache_dir / f"{seq.id}_{content_hash}.json"

        if cache_file.exists():
            summary = json.loads(cache_file.read_text(encoding="utf-8"))
        else:
            summary = backend.query_json(
                load_prompt("derive_seq_summary", text=content, seq_id=seq.id)
            )
            atomic_write(cache_file, json.dumps(summary, ensure_ascii=False))
            # Clean old cache files for this sequence
            for old in cache_dir.glob(f"{seq.id}_*.json"):
                if old != cache_file:
                    old.unlink()

        seq_summaries.append({"id": seq.id, **summary})

    # Stage 2: Aggregate
    aggregate_input = json.dumps(seq_summaries, ensure_ascii=False, indent=2)
    synopsis = backend.query(
        load_prompt("derive_synopsis", summaries=aggregate_input)
    )
    context = backend.query(
        load_prompt("derive_context", summaries=aggregate_input)
    )

    derived_dir = workspace / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(derived_dir / "synopsis.md", synopsis)
    atomic_write(derived_dir / "context.md", context)
