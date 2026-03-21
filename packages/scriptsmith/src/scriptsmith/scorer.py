# src/scriptsmith/scorer.py
"""Scoring engine: evaluate screenplay sequences via LLM backend."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Literal

from scriptsmith.backends import BackendProtocol
from scriptsmith.models import ScoreResult
from scriptsmith.prompts import load_prompt


def score(
    sequence_text: str,
    criteria: str,
    context: str,
    mode: Literal["macro", "micro"],
    backend: BackendProtocol,
    runs: int = 3,
    max_total: int | None = None,
) -> ScoreResult:
    """Score a sequence or synopsis against criteria.

    Runs `runs` independent evaluations and takes median per dimension.
    """
    template_name = f"score_{mode}"
    prompt = load_prompt(
        template_name,
        text=sequence_text,
        criteria=criteria,
        context=context,
    )

    raw_runs: list[dict] = []
    with ThreadPoolExecutor(max_workers=runs) as pool:
        futures = [pool.submit(backend.query_json, prompt) for _ in range(runs)]
        for future in as_completed(futures):
            raw_runs.append(future.result())

    # Auto-detect max_total from first run if not specified
    if max_total is None:
        scoring_dims = [k for k in raw_runs[0] if not k.startswith("_")]
        max_total = len(scoring_dims) * 10  # Assume 10-point scale

    return ScoreResult.from_raw_runs(raw_runs, max_total=max_total)
