# src/script_forge/loop.py
"""Main optimization loop controller."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable, Literal

from rich.console import Console

from script_forge.backends import BackendProtocol
from script_forge.deriver import derive_all
from script_forge.git_ops import (
    apply_candidate,
    commit_keep,
    discard_candidate,
    reconcile_workspace,
)
from script_forge.models import ExperimentRecord, ProjectState, ScoreResult
from script_forge.modifier import modify
from script_forge.scorer import score
from script_forge.state import (
    append_history,
    load_history,
    load_state,
    save_state,
    update_results_tsv,
)
from script_forge.workspace import load_criteria, load_manifest, load_sequence

logger = logging.getLogger(__name__)
console = Console()


def should_stop(state: ProjectState, max_rounds: int | None, stall_limit: int) -> bool:
    """Determine if the loop should stop."""
    if state.auto_phase == "done":
        return True
    if max_rounds is not None and state.round_number >= max_rounds:
        return True
    if max_rounds is None and state.stall_count >= stall_limit:
        return True
    return False


def run_loop(
    workspace: Path,
    mode: Literal["macro", "micro", "auto"],
    rounds: int | None,
    backend: BackendProtocol,
    sequence: str | None = None,
    keep_threshold: int = 1,
    on_round: Callable[[ExperimentRecord], None] | None = None,
    stop_event: threading.Event | None = None,
) -> None:
    """Run the optimization loop."""
    # Reconcile before anything
    reconcile_workspace(workspace)

    # Load or init state
    existing = load_state(workspace)
    if existing is not None:
        state = existing
        if state.current_mode != mode and state.auto_phase is None:
            console.print(f"[yellow]Warning: saved state mode is '{state.current_mode}' but requested '{mode}'. Using saved state. Use --fresh to restart.[/yellow]")
        console.print(f"[yellow]Resuming from round {state.round_number}[/yellow]")
    else:
        state = ProjectState.default(mode=mode)

    criteria = load_criteria(workspace)
    sequences = load_manifest(workspace)
    stall_limit = 5

    # Set initial sequence for micro mode
    if sequence is not None:
        state.current_sequence = sequence
    elif state.current_sequence is None and state.current_mode == "micro" and sequences:
        state.current_sequence = sequences[0].id

    while not should_stop(state, rounds, stall_limit):
        if stop_event is not None and stop_event.is_set():
            break

        try:
            if state.current_mode == "macro":
                record = _run_macro_round(workspace, state, criteria, backend, keep_threshold=keep_threshold)
            else:
                record = _run_micro_round(workspace, state, criteria, backend, sequences, target_sequence=sequence, keep_threshold=keep_threshold)
        except Exception as e:
            logger.error("Round %d failed: %s", state.round_number, e)
            console.print(f"[red]Round {state.round_number} error: {e}[/red]")
            state.round_number += 1
            save_state(workspace, state)
            continue

        if on_round is not None and record is not None:
            on_round(record)

        # Auto mode transitions
        if state.auto_phase == "macro_initial" and state.macro_rounds_done >= 3:
            state.current_mode = "micro"
            state.auto_phase = "micro_sweep"
            state.stall_count = 0
            if sequences:
                state.current_sequence = sequences[0].id
            console.print("[cyan]Auto: transitioning to micro sweep[/cyan]")
        elif state.auto_phase == "micro_sweep":
            all_done = all(s.id in state.sequences_completed for s in sequences)
            if all_done:
                state.current_mode = "macro"
                state.auto_phase = "macro_validation"
                state.macro_rounds_done = 0
                state.stall_count = 0
                console.print("[cyan]Auto: transitioning to macro validation[/cyan]")
        elif state.auto_phase == "macro_validation" and state.macro_rounds_done >= 1:
            state.auto_phase = "done"

        save_state(workspace, state)

    save_state(workspace, state)
    _print_final_summary(workspace, state)


def _run_micro_round(
    workspace: Path,
    state: ProjectState,
    criteria: str,
    backend: BackendProtocol,
    sequences: list,
    target_sequence: str | None = None,
    keep_threshold: int = 1,
) -> ExperimentRecord | None:
    """Execute one micro round on the current sequence."""
    seq_id = state.current_sequence
    if seq_id is None:
        return

    console.print(f"\n[bold]Round {state.round_number + 1} (micro: {seq_id})[/bold]")

    # Load context
    context_path = workspace / "derived" / "context.md"
    context = context_path.read_text(encoding="utf-8") if context_path.exists() else ""
    seq_text = load_sequence(workspace, seq_id)

    # Score baseline (or use cached)
    if seq_id not in state.baseline_scores:
        console.print("  Scoring baseline...")
        baseline = score(seq_text, criteria, context, "micro", backend)
        state.baseline_scores[seq_id] = baseline.to_dict()
    else:
        baseline = ScoreResult.from_dict(state.baseline_scores[seq_id])

    console.print(f"  Baseline: {baseline.total}/{baseline.max_total} ({baseline.breakdown})")

    # Modify
    console.print(f"  Modifying (target: {baseline.weakest_dimension})...")
    history = load_history(workspace)
    seq_history = [r for r in history if r.sequence == seq_id]
    new_text, meta = modify(seq_text, criteria, context, baseline, seq_history, "micro", backend)

    if not new_text.strip():
        console.print("  [red]Empty modification, skipping[/red]")
        state.round_number += 1
        state.stall_count += 1
        return

    # Apply candidate
    apply_candidate(workspace, seq_id, new_text)

    # Re-score
    console.print("  Scoring candidate...")
    new_score = score(new_text, criteria, context, "micro", backend, max_total=baseline.max_total)
    delta = new_score.total - baseline.total

    console.print(f"  Candidate: {new_score.total}/{new_score.max_total} (delta={delta:+d})")

    # Record experiment
    state.last_experiment_id += 1
    record = ExperimentRecord(
        id=state.last_experiment_id,
        commit="",
        sequence=seq_id,
        mode="micro",
        target_dimension=meta["target_dimension"],
        hypothesis=meta["hypothesis"],
        scope=meta["scope"],
        score_before=baseline,
        score_after=new_score,
        delta=delta,
        status="keep" if delta >= keep_threshold else "discard",
        description=meta["description"],
    )

    # Keep or discard
    if delta >= keep_threshold:
        short_hash = commit_keep(workspace, seq_id, f"keep: {meta['description']} (delta={delta:+d})")
        record.commit = short_hash
        state.baseline_scores[seq_id] = new_score.to_dict()
        state.stall_count = 0
        state.total_keeps += 1
        console.print(f"  [green]KEEP (+{delta}) [{short_hash}][/green]")
    else:
        discard_candidate(workspace, seq_id)
        state.stall_count += 1
        state.total_discards += 1
        console.print(f"  [red]DISCARD ({delta:+d})[/red]")

    append_history(workspace, record)
    update_results_tsv(workspace, record)
    state.round_number += 1

    # Check stall → move to next sequence (works in both auto and standalone micro)
    if state.stall_count >= 5 and target_sequence is None:
        state.sequences_completed.append(seq_id)
        state.stall_count = 0
        # Find next uncompleted sequence
        for seq in sequences:
            if seq.id not in state.sequences_completed:
                state.current_sequence = seq.id
                console.print(f"  [yellow]Stalled on {seq_id}, moving to {seq.id}[/yellow]")
                break

    return record


def _run_macro_round(
    workspace: Path,
    state: ProjectState,
    criteria: str,
    backend: BackendProtocol,
    keep_threshold: int = 1,
) -> ExperimentRecord | None:
    """Execute one macro round."""
    console.print(f"\n[bold]Round {state.round_number + 1} (macro)[/bold]")

    # Regenerate derived files
    console.print("  Regenerating synopsis/context...")
    derive_all(workspace, backend)

    synopsis_path = workspace / "derived" / "synopsis.md"
    context_path = workspace / "derived" / "context.md"
    synopsis = synopsis_path.read_text(encoding="utf-8") if synopsis_path.exists() else ""
    context = context_path.read_text(encoding="utf-8") if context_path.exists() else ""

    # Score synopsis
    console.print("  Scoring synopsis...")
    global_score = score(synopsis, criteria, context, "macro", backend)
    console.print(f"  Global: {global_score.total}/{global_score.max_total}")

    if "global" not in state.baseline_scores:
        state.baseline_scores["global"] = global_score.to_dict()

    # Find the sequence most responsible for the weakest dimension
    # For now: pick the first uncompleted sequence
    sequences = load_manifest(workspace)
    target_seq = sequences[0]  # Simple heuristic for v1
    for seq in sequences:
        if seq.id not in state.sequences_completed:
            target_seq = seq
            break

    seq_text = load_sequence(workspace, target_seq.id)

    # Modify
    history = load_history(workspace)
    console.print(f"  Modifying {target_seq.id} (target: {global_score.weakest_dimension})...")
    new_text, meta = modify(seq_text, criteria, context, global_score, history, "macro", backend)

    if not new_text.strip():
        state.round_number += 1
        state.macro_rounds_done += 1
        return

    apply_candidate(workspace, target_seq.id, new_text)

    # Re-derive and re-score
    derive_all(workspace, backend)
    new_synopsis = (workspace / "derived" / "synopsis.md").read_text(encoding="utf-8")
    new_context = (workspace / "derived" / "context.md").read_text(encoding="utf-8")
    new_global = score(new_synopsis, criteria, new_context, "macro", backend)
    delta = new_global.total - global_score.total

    state.last_experiment_id += 1
    record = ExperimentRecord(
        id=state.last_experiment_id,
        commit="",
        sequence=target_seq.id,
        mode="macro",
        target_dimension=meta["target_dimension"],
        hypothesis=meta["hypothesis"],
        scope=meta["scope"],
        score_before=global_score,
        score_after=new_global,
        delta=delta,
        status="keep" if delta >= keep_threshold else "discard",
        description=meta["description"],
    )

    if delta >= keep_threshold:
        short_hash = commit_keep(workspace, target_seq.id, f"macro keep: {meta['description']} (delta={delta:+d})")
        record.commit = short_hash
        state.baseline_scores["global"] = new_global.to_dict()
        state.stall_count = 0
        state.total_keeps += 1
        console.print(f"  [green]KEEP (+{delta}) [{short_hash}][/green]")
    else:
        discard_candidate(workspace, target_seq.id)
        state.stall_count += 1
        state.total_discards += 1
        console.print(f"  [red]DISCARD ({delta:+d})[/red]")

    append_history(workspace, record)
    update_results_tsv(workspace, record)
    state.round_number += 1
    state.macro_rounds_done += 1

    return record


def _print_final_summary(workspace: Path, state: ProjectState) -> None:
    """Print final loop summary."""
    console.print("\n[bold]Loop complete[/bold]")
    console.print(f"  Rounds: {state.round_number}")
    console.print(f"  Keeps: {state.total_keeps}")
    console.print(f"  Discards: {state.total_discards}")
    if state.total_keeps + state.total_discards > 0:
        rate = state.total_keeps / (state.total_keeps + state.total_discards) * 100
        console.print(f"  Success rate: {rate:.0f}%")
