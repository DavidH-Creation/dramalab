# src/script_forge/backends/mock.py
"""Mock backend for testing. No LLM calls."""

from __future__ import annotations

from script_forge.backends import extract_json


class MockBackend:
    """Deterministic backend that cycles through pre-configured responses."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.call_count = 0
        self.prompts: list[str] = []

    def query(self, prompt: str, **kwargs) -> str:  # noqa: ARG002
        self.prompts.append(prompt)
        resp = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return resp

    def query_json(self, prompt: str, **kwargs) -> dict:
        raw = self.query(prompt, **kwargs)
        return extract_json(raw)
