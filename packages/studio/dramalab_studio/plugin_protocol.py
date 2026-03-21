"""Plugin protocol and shared data types for DramaLab Studio."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol


@dataclass
class RoundResult:
    """Result of a single optimization round, sent to frontend via SSE."""

    round_number: int
    status: str          # "keep" | "discard" | "error"
    total_before: int
    total_after: int
    delta: int
    target_dimension: str
    description: str
    scores_before: dict[str, int]
    scores_after: dict[str, int]
    max_total: int

    def to_dict(self) -> dict:
        return {
            "round_number": self.round_number,
            "status": self.status,
            "total_before": self.total_before,
            "total_after": self.total_after,
            "delta": self.delta,
            "target_dimension": self.target_dimension,
            "description": self.description,
            "scores_before": self.scores_before,
            "scores_after": self.scores_after,
            "max_total": self.max_total,
        }

    @classmethod
    def from_experiment_record(cls, record, round_number: int) -> RoundResult:
        """Convert a script_forge ExperimentRecord to RoundResult."""
        return cls(
            round_number=round_number,
            status=record.status,
            total_before=record.score_before.total,
            total_after=record.score_after.total,
            delta=record.delta,
            target_dimension=record.target_dimension,
            description=record.description,
            scores_before=dict(record.score_before.scores),
            scores_after=dict(record.score_after.scores),
            max_total=record.score_before.max_total,
        )


class DramaLabPlugin(Protocol):
    """Protocol that all DramaLab Studio plugins must implement."""

    name: str
    display_name: str

    async def initialize(self, input_text: str, criteria_text: str, config: dict) -> dict:
        ...

    async def run(self, config: dict) -> AsyncIterator[RoundResult]:
        ...

    async def stop(self) -> None:
        ...

    async def get_current_text(self) -> str:
        ...

    async def export(self) -> bytes:
        ...
