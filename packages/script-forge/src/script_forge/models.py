# src/script_forge/models.py
"""Data classes for Script-Forge."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median


@dataclass
class ScoreResult:
    """Result of scoring a sequence or synopsis."""

    scores: dict[str, int]
    total: int
    max_total: int
    breakdown: str
    raw_runs: list[dict]

    @classmethod
    def from_raw_runs(cls, runs: list[dict], max_total: int) -> ScoreResult:
        """Compute median scores from multiple independent scoring runs."""
        if not runs:
            raise ValueError("At least one scoring run required")

        dimensions = list(runs[0].keys())
        # Filter out internal keys like _rationale
        dimensions = [d for d in dimensions if not d.startswith("_")]

        scores: dict[str, int] = {}
        for dim in dimensions:
            values = [r[dim] for r in runs if dim in r]
            scores[dim] = int(median(values))

        total = sum(scores.values())
        breakdown = ",".join(str(scores[d]) for d in dimensions)

        return cls(
            scores=scores,
            total=total,
            max_total=max_total,
            breakdown=breakdown,
            raw_runs=runs,
        )

    @property
    def weakest_dimension(self) -> str:
        """Return the dimension with the lowest score."""
        return min(self.scores, key=self.scores.get)  # type: ignore[arg-type]

    def to_dict(self) -> dict:
        return {
            "scores": self.scores,
            "total": self.total,
            "max_total": self.max_total,
            "breakdown": self.breakdown,
            "raw_runs": self.raw_runs,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ScoreResult:
        required = ("scores", "total", "max_total", "breakdown", "raw_runs")
        missing = [k for k in required if k not in d]
        if missing:
            raise ValueError(f"ScoreResult missing required keys: {missing}")
        return cls(**d)


@dataclass
class ExperimentRecord:
    """Record of a single modify-score experiment."""

    id: int
    commit: str  # Short git hash (empty string if not yet committed)
    sequence: str
    mode: str
    target_dimension: str
    hypothesis: str
    scope: str
    score_before: ScoreResult
    score_after: ScoreResult
    delta: int
    status: str  # "keep" | "discard" | "error" | "crashed"
    description: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "commit": self.commit,
            "sequence": self.sequence,
            "mode": self.mode,
            "target_dimension": self.target_dimension,
            "hypothesis": self.hypothesis,
            "scope": self.scope,
            "score_before": self.score_before.to_dict(),
            "score_after": self.score_after.to_dict(),
            "delta": self.delta,
            "status": self.status,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ExperimentRecord:
        return cls(
            id=d["id"],
            commit=d.get("commit", ""),
            sequence=d["sequence"],
            mode=d["mode"],
            target_dimension=d["target_dimension"],
            hypothesis=d["hypothesis"],
            scope=d["scope"],
            score_before=ScoreResult.from_dict(d["score_before"]),
            score_after=ScoreResult.from_dict(d["score_after"]),
            delta=d["delta"],
            status=d["status"],
            description=d["description"],
        )


@dataclass
class SequenceInfo:
    """Metadata about a single sequence segment."""

    id: str
    filename: str
    title: str
    episodes: str
    char_count: int
    scene_count: int
    markers: list[str]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "title": self.title,
            "episodes": self.episodes,
            "char_count": self.char_count,
            "scene_count": self.scene_count,
            "markers": self.markers,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SequenceInfo:
        return cls(**d)


@dataclass
class ProjectState:
    """Resumable loop state, persisted to .script-forge/state.json."""

    version: int = 1
    current_mode: str = "micro"
    auto_phase: str | None = None
    current_sequence: str | None = None
    round_number: int = 0
    stall_count: int = 0
    macro_rounds_done: int = 0
    total_keeps: int = 0
    total_discards: int = 0
    sequences_completed: list[str] = field(default_factory=list)
    baseline_scores: dict[str, dict] = field(default_factory=dict)
    last_experiment_id: int = 0
    backend: str = "claude_cli"
    model: str = "sonnet"

    @classmethod
    def default(cls, mode: str) -> ProjectState:
        """Create a default state for the given mode."""
        state = cls()
        if mode == "auto":
            state.current_mode = "macro"
            state.auto_phase = "macro_initial"
        else:
            state.current_mode = mode
            state.auto_phase = None
        return state

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "current_mode": self.current_mode,
            "auto_phase": self.auto_phase,
            "current_sequence": self.current_sequence,
            "round_number": self.round_number,
            "stall_count": self.stall_count,
            "macro_rounds_done": self.macro_rounds_done,
            "total_keeps": self.total_keeps,
            "total_discards": self.total_discards,
            "sequences_completed": self.sequences_completed,
            "baseline_scores": self.baseline_scores,
            "last_experiment_id": self.last_experiment_id,
            "backend": self.backend,
            "model": self.model,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ProjectState:
        return cls(
            version=d.get("version", 1),
            current_mode=d["current_mode"],
            auto_phase=d.get("auto_phase"),
            current_sequence=d.get("current_sequence"),
            round_number=d.get("round_number", 0),
            stall_count=d.get("stall_count", 0),
            macro_rounds_done=d.get("macro_rounds_done", 0),
            total_keeps=d.get("total_keeps", 0),
            total_discards=d.get("total_discards", 0),
            sequences_completed=d.get("sequences_completed", []),
            baseline_scores=d.get("baseline_scores", {}),
            last_experiment_id=d.get("last_experiment_id", 0),
            backend=d.get("backend", "claude_cli"),
            model=d.get("model", "sonnet"),
        )
