# src/scriptsmith/prompts/__init__.py
"""Prompt template loader."""

from __future__ import annotations

from pathlib import Path


_PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str, **kwargs: str) -> str:
    """Load a prompt template by name and fill placeholders.

    Templates use {placeholder} syntax. All kwargs are substituted.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    template = path.read_text(encoding="utf-8")
    return template.format(**kwargs)
