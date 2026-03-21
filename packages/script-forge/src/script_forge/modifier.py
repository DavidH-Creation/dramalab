# src/script_forge/modifier.py
"""Modification engine: generate candidate screenplay changes via LLM backend."""

from __future__ import annotations

from typing import Literal

from script_forge.backends import BackendProtocol
from script_forge.models import ExperimentRecord, ScoreResult
from script_forge.prompts import load_prompt


def modify(
    sequence_text: str,
    criteria: str,
    context: str,
    current_score: ScoreResult,
    history: list[ExperimentRecord],
    mode: Literal["macro", "micro"],
    backend: BackendProtocol,
) -> tuple[str, dict]:
    """Generate a candidate modification for the sequence.

    Returns (modified_text, experiment_metadata_dict).
    """
    weakest = current_score.weakest_dimension
    weakest_score = current_score.scores[weakest]

    # Build failed experiments summary
    failed = [r for r in history if r.status == "discard" and r.target_dimension == weakest]
    if failed:
        failed_summary = "\n".join(
            f"- [{r.id}] {r.hypothesis} → 失败 (delta={r.delta})" for r in failed[-5:]
        )
    else:
        failed_summary = "无"

    # Extract dimension-specific criteria (best effort: look for heading)
    dimension_criteria = _extract_dimension_criteria(criteria, weakest)

    template_name = f"modify_{mode}"
    prompt = load_prompt(
        template_name,
        text=sequence_text,
        criteria=criteria,
        context=context,
        breakdown=current_score.breakdown,
        weakest_dimension=weakest,
        weakest_score=str(weakest_score),
        dimension_criteria=dimension_criteria,
        failed_experiments=failed_summary,
    )

    result = backend.query_json(prompt)

    modified_text = result.get("modified_text", "")
    meta = {
        "target_dimension": result.get("target_dimension", weakest),
        "hypothesis": result.get("hypothesis", ""),
        "scope": result.get("scope", ""),
        "description": result.get("description", ""),
    }

    return modified_text, meta


def _extract_dimension_criteria(criteria: str, dimension: str) -> str:
    """Extract the section of criteria text relevant to a specific dimension."""
    lines = criteria.split("\n")
    capturing = False
    captured: list[str] = []

    for line in lines:
        if dimension in line and ("#" in line or "##" in line):
            capturing = True
            captured.append(line)
        elif capturing:
            if line.startswith("#") and dimension not in line:
                break
            captured.append(line)

    return "\n".join(captured) if captured else f"（未找到 {dimension} 的具体标准）"
