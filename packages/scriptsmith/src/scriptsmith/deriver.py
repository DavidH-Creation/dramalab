# src/scriptsmith/deriver.py
"""Derive synopsis.md and context.md from sequences (cached, two-stage).

Stage 1 runs per-sequence summaries in parallel via ThreadPoolExecutor.
Stage 2 aggregates summaries into synopsis + context (two parallel calls).
All stages use content-hash caching to skip unchanged sequences.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from scriptsmith.backends import BackendProtocol
from scriptsmith.backends import BackendError
from scriptsmith.prompts import load_prompt
from scriptsmith.workspace import atomic_write, load_manifest

logger = logging.getLogger(__name__)

# Type for optional progress callback: (stage, current, total, detail)
ProgressCallback = Callable[[str, int, int, str], None]


def _derived_is_fresh(workspace: Path, max_age_seconds: int = 300) -> bool:
    """Check if derived files exist and are recent enough to skip re-derive."""
    synopsis = workspace / "derived" / "synopsis.md"
    context = workspace / "derived" / "context.md"
    if not synopsis.exists() or not context.exists():
        return False
    # Check if files are placeholder/fallback (too small to be real)
    if synopsis.stat().st_size < 200 or context.stat().st_size < 200:
        return False
    age = time.time() - synopsis.stat().st_mtime
    return age < max_age_seconds


def _summarize_one(
    seq_id: str,
    seq_path: Path,
    cache_dir: Path,
    backend: BackendProtocol,
) -> dict:
    """Summarize a single sequence, with cache lookup."""
    content = seq_path.read_text(encoding="utf-8")
    content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()[:12]
    cache_file = cache_dir / f"{seq_id}_{content_hash}.json"

    if cache_file.exists():
        logger.debug("Cache hit for %s", seq_id)
        return {"id": seq_id, **json.loads(cache_file.read_text(encoding="utf-8"))}

    logger.info("Summarizing %s (%d chars)...", seq_id, len(content))
    summary = backend.query_json(
        load_prompt("derive_seq_summary", text=content, seq_id=seq_id)
    )
    atomic_write(cache_file, json.dumps(summary, ensure_ascii=False))

    # Clean old cache files for this sequence
    for old in cache_dir.glob(f"{seq_id}_*.json"):
        if old != cache_file:
            old.unlink()

    return {"id": seq_id, **summary}


def derive_all(
    workspace: Path,
    backend: BackendProtocol,
    *,
    max_workers: int = 3,
    on_progress: ProgressCallback | None = None,
    skip_if_fresh: bool = False,
) -> None:
    """Regenerate synopsis.md and context.md from sequences.

    Stage 1: Per-sequence structured summaries (parallel, cached).
    Stage 2: Aggregate summaries into global synopsis + context (parallel).

    Args:
        workspace: Project workspace path.
        backend: LLM backend to use.
        max_workers: Max parallel Claude CLI calls for Stage 1.
        on_progress: Optional callback (stage, current, total, detail).
        skip_if_fresh: If True, skip re-derive when derived files exist
            and were modified within the last 5 minutes.
    """
    if skip_if_fresh and _derived_is_fresh(workspace):
        logger.info("Derived files are fresh, skipping re-derive")
        return

    sequences = load_manifest(workspace)
    cache_dir = workspace / ".scriptsmith" / "summary_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    total_seqs = len(sequences)

    # ── Stage 1: Parallel per-sequence summaries ──
    if on_progress:
        on_progress("summarize", 0, total_seqs, "Starting per-sequence summaries...")

    seq_summaries: list[dict] = [{} for _ in range(total_seqs)]  # Preserve order
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {}
        for idx, seq in enumerate(sequences):
            seq_path = workspace / "sequences" / seq.filename
            future = pool.submit(_summarize_one, seq.id, seq_path, cache_dir, backend)
            future_to_idx[future] = idx

        done_count = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            seq_id = sequences[idx].id
            done_count += 1
            try:
                seq_summaries[idx] = future.result()
                logger.info("Summarized %s (%d/%d)", seq_id, done_count, total_seqs)
                if on_progress:
                    on_progress("summarize", done_count, total_seqs, f"Done: {seq_id}")
            except (BackendError, Exception) as exc:
                errors.append(f"{seq_id}: {exc}")
                logger.warning("Failed to summarize %s: %s", seq_id, exc)
                if on_progress:
                    on_progress("summarize", done_count, total_seqs, f"Failed: {seq_id}")

    # Filter out empty entries from failed summaries
    seq_summaries = [s for s in seq_summaries if s]

    if not seq_summaries:
        raise BackendError(
            f"All sequence summaries failed: {'; '.join(errors)}"
        )

    if errors:
        logger.warning(
            "%d/%d summaries failed, continuing with partial data: %s",
            len(errors), total_seqs, "; ".join(errors),
        )

    # ── Stage 2: Aggregate into synopsis + context (parallel) ──
    if on_progress:
        on_progress("aggregate", 0, 2, "Generating synopsis and context...")

    aggregate_input = json.dumps(seq_summaries, ensure_ascii=False, indent=2)
    synopsis_prompt = load_prompt("derive_synopsis", summaries=aggregate_input)
    context_prompt = load_prompt("derive_context", summaries=aggregate_input)

    synopsis: str | None = None
    context: str | None = None

    with ThreadPoolExecutor(max_workers=2) as pool:
        syn_future = pool.submit(backend.query, synopsis_prompt)
        ctx_future = pool.submit(backend.query, context_prompt)

        try:
            synopsis = syn_future.result()
            if on_progress:
                on_progress("aggregate", 1, 2, "Synopsis done")
        except Exception as exc:
            logger.warning("Synopsis generation failed: %s", exc)

        try:
            context = ctx_future.result()
            if on_progress:
                on_progress("aggregate", 2, 2, "Context done")
        except Exception as exc:
            logger.warning("Context generation failed: %s", exc)

    # ── Write results ──
    derived_dir = workspace / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)

    if synopsis:
        atomic_write(derived_dir / "synopsis.md", synopsis)
        logger.info("Wrote derived/synopsis.md")
    else:
        # Write a minimal fallback from summaries
        fallback = "# Synopsis (auto-generated from summaries)\n\n"
        for s in seq_summaries:
            sid = s.get("id", "?")
            events = s.get("key_events", [])
            fallback += f"## {sid}\n"
            for e in events:
                fallback += f"- {e}\n"
            fallback += "\n"
        atomic_write(derived_dir / "synopsis.md", fallback)
        logger.info("Wrote derived/synopsis.md (fallback from summaries)")

    if context:
        atomic_write(derived_dir / "context.md", context)
        logger.info("Wrote derived/context.md")
    else:
        # Write a minimal fallback from summaries
        fallback = "# Context (auto-generated from summaries)\n\n## Characters\n"
        all_chars: list[str] = []
        for s in seq_summaries:
            all_chars.extend(s.get("characters", []))
        for ch in sorted(set(all_chars)):
            fallback += f"- {ch}\n"
        atomic_write(derived_dir / "context.md", fallback)
        logger.info("Wrote derived/context.md (fallback from summaries)")

    if on_progress:
        on_progress("complete", 1, 1, "Derive complete")
