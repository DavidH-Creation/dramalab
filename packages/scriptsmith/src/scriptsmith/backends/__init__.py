# src/scriptsmith/backends/__init__.py
"""Backend protocol and shared utilities for LLM adapters."""

from __future__ import annotations

import json
import re
from typing import Protocol


class BackendError(Exception):
    """Raised when a backend operation fails."""


def extract_json(raw: str) -> dict | list:
    """Extract a JSON object or array from LLM response text.

    Handles: plain JSON, markdown code fences, JSON embedded in prose.
    Raises BackendError if no valid JSON found.
    """
    # Strategy 1: Try parsing the whole string
    stripped = raw.strip()
    if stripped.startswith(("{", "[")):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # Strategy 2: Extract from markdown code fence
    fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find first { ... } or [ ... ] block via regex
    brace_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw, re.DOTALL)
    bracket_match = re.search(r"\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]", raw, re.DOTALL)
    # Prefer whichever appears first in the text
    candidates = []
    if brace_match:
        candidates.append(brace_match)
    if bracket_match:
        candidates.append(bracket_match)
    candidates.sort(key=lambda m: m.start())
    for m in candidates:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # Strategy 4: More aggressive nested brace/bracket matching
    for open_ch, close_ch in [("{", "}"), ("[", "]")]:
        depth = 0
        start = None
        for i, ch in enumerate(raw):
            if ch == open_ch:
                if depth == 0:
                    start = i
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        return json.loads(raw[start : i + 1])
                    except json.JSONDecodeError:
                        start = None

    raise BackendError(f"No valid JSON found in response ({len(raw)} chars)")


class BackendProtocol(Protocol):
    """Protocol that all LLM backends must implement."""

    def query(self, prompt: str, *, timeout: int = 300) -> str:
        """Send prompt, return response text."""
        ...

    def query_json(self, prompt: str, *, timeout: int = 300, retries: int = 2) -> dict | list:
        """Send prompt, parse JSON from response. Retry on parse failure."""
        ...
