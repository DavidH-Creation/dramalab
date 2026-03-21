# src/scriptsmith/cli.py
"""CLI entry point for ScriptSmith."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from scriptsmith import __version__

app = typer.Typer(
    name="scriptsmith",
    help="Iterative screenplay optimizer using LLM-as-judge loop.",
    no_args_is_help=True,
)
console = Console()


def _make_backend(model: str = "sonnet", timeout: int = 300):
    """Create the Claude CLI backend."""
    from scriptsmith.backends.claude_cli import ClaudeCLIBackend
    return ClaudeCLIBackend(model=model, timeout=timeout)


def _resolve_workspace(workspace: str | None) -> Path:
    """Resolve workspace path, defaulting to cwd."""
    if workspace:
        return Path(workspace)
    return Path.cwd()


@app.command()
def init(
    screenplay: str = typer.Argument(..., help="Path to screenplay .docx file"),
    criteria: Optional[str] = typer.Option(None, "--criteria", "-c", help="Path to criteria .docx or .md file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output workspace directory"),
    model: str = typer.Option("sonnet", "--model", "-m", help="Claude model for LLM calls"),
) -> None:
    """Initialize a new ScriptSmith workspace."""
    from docx import Document

    from scriptsmith.git_ops import git_init
    from scriptsmith.splitter import split_screenplay
    from scriptsmith.workspace import atomic_write

    screenplay_path = Path(screenplay)
    if not screenplay_path.exists():
        console.print(f"[red]File not found: {screenplay_path}[/red]")
        raise typer.Exit(1)

    # Determine output directory
    if output:
        ws = Path(output)
    else:
        ws = Path.cwd() / screenplay_path.stem

    ws.mkdir(parents=True, exist_ok=True)
    for d in ["input", "sequences", "derived", "experiments", "exports", ".scriptsmith"]:
        (ws / d).mkdir(exist_ok=True)

    # Copy inputs
    shutil.copy2(screenplay_path, ws / "input" / screenplay_path.name)

    # Handle criteria
    if criteria:
        criteria_path = Path(criteria)
        shutil.copy2(criteria_path, ws / "input" / criteria_path.name)
        if criteria_path.suffix == ".md":
            shutil.copy2(criteria_path, ws / "criteria.md")
        else:
            # Convert docx to markdown text
            doc = Document(str(criteria_path))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            atomic_write(ws / "criteria.md", text)
    else:
        atomic_write(ws / "criteria.md", "# Scoring Criteria\n\n(Define your criteria here)\n")

    # Create project config
    config_content = f"""[project]
name = "{screenplay_path.stem}"
created = "{__import__('datetime').date.today().isoformat()}"

[backend]
type = "claude_cli"
model = "{model}"
derive_model = "haiku"
timeout = 300

[scoring]
runs = 3
keep_threshold = 1

[loop]
stall_limit = 5
target_chars_min = 8000
target_chars_max = 15000

[splitter]
fallback_to_llm = true
"""
    atomic_write(ws / ".scriptsmith" / "project.toml", config_content)

    # Create .gitignore
    atomic_write(ws / ".gitignore", ".scriptsmith/.lock\n.scriptsmith/*.tmp\n")

    # Split screenplay
    console.print(f"Splitting screenplay...")
    try:
        backend = _make_backend(model=model)
    except Exception:
        backend = None  # Will fall back to regex-only splitting

    infos = split_screenplay(screenplay_path, ws, backend=backend)
    console.print(f"  Created {len(infos)} sequences")

    # Generate derived files (synopsis + context)
    if backend is not None:
        console.print("Generating derived files...")
        from scriptsmith.deriver import derive_all
        try:
            derive_all(ws, backend)
            console.print("  Generated synopsis.md and context.md")
        except Exception as e:
            console.print(f"  [yellow]Warning: could not generate derived files: {e}[/yellow]")
            console.print("  [yellow]Run 'scriptsmith derive' later to generate them.[/yellow]")

    # Init git
    git_init(ws)
    console.print(f"\n[green]Workspace created: {ws}[/green]")
    console.print(f"  Sequences: {len(infos)}")
    for info in infos:
        console.print(f"    {info.id}: {info.title} ({info.char_count} chars, {info.scene_count} scenes)")


@app.command()
def run(
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w"),
    mode: str = typer.Option("auto", "--mode", help="macro|micro|auto"),
    rounds: Optional[int] = typer.Option(None, "--rounds", "-n", help="Max rounds (default: until-stalled)"),
    sequence: Optional[str] = typer.Option(None, "--sequence", "-s", help="Target sequence ID"),
    fresh: bool = typer.Option(False, "--fresh", help="Ignore saved state, re-baseline"),
    model: str = typer.Option("sonnet", "--model", "-m"),
) -> None:
    """Run the optimization loop."""
    from scriptsmith.loop import run_loop
    from scriptsmith.state import acquire_lock, release_lock
    from scriptsmith.workspace import validate_workspace

    ws = _resolve_workspace(workspace)
    errors = validate_workspace(ws)
    if errors:
        for e in errors:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    if rounds == -1:
        console.print("[yellow]Warning: infinite mode. Press Ctrl+C to stop.[/yellow]")
        rounds = None
    elif rounds is None:
        rounds = None  # until-stalled

    backend = _make_backend(model=model)

    try:
        acquire_lock(ws)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    if fresh:
        state_path = ws / ".scriptsmith" / "state.json"
        state_path.unlink(missing_ok=True)

    try:
        run_loop(ws, mode=mode, rounds=rounds, backend=backend, sequence=sequence)  # type: ignore[arg-type]
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. State saved.[/yellow]")
    finally:
        release_lock(ws)


@app.command()
def status(
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w"),
) -> None:
    """Show current status and results summary."""
    from scriptsmith.state import load_state
    from scriptsmith.workspace import validate_workspace

    ws = _resolve_workspace(workspace)
    errors = validate_workspace(ws)
    if errors:
        for e in errors:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    # Show state
    state = load_state(ws)
    if state:
        console.print(f"Mode: {state.current_mode}")
        console.print(f"Round: {state.round_number}")
        console.print(f"Keeps: {state.total_keeps} | Discards: {state.total_discards}")
        if state.current_sequence:
            console.print(f"Current sequence: {state.current_sequence}")

    # Show results.tsv as table
    results_path = ws / "results.tsv"
    if results_path.exists():
        lines = results_path.read_text(encoding="utf-8").strip().split("\n")
        if len(lines) > 1:
            headers = lines[0].split("\t")
            table = Table(*headers, title="Experiments")
            for line in lines[1:]:
                table.add_row(*line.split("\t"))
            console.print(table)
    else:
        console.print("[dim]No experiments yet.[/dim]")


@app.command(name="score")
def score_cmd(
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w"),
    sequence: Optional[str] = typer.Option(None, "--sequence", "-s"),
    model: str = typer.Option("sonnet", "--model", "-m"),
) -> None:
    """Run a one-shot scoring (read-only, does not update state)."""
    from scriptsmith.scorer import score
    from scriptsmith.workspace import load_criteria, load_sequence, validate_workspace

    ws = _resolve_workspace(workspace)
    errors = validate_workspace(ws)
    if errors:
        for e in errors:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    backend = _make_backend(model=model)

    if sequence:
        text = load_sequence(ws, sequence)
        mode = "micro"
    else:
        synopsis_path = ws / "derived" / "synopsis.md"
        if synopsis_path.exists():
            text = synopsis_path.read_text(encoding="utf-8")
        else:
            console.print("[red]No synopsis found. Run 'derive' first or specify --sequence.[/red]")
            raise typer.Exit(1)
        mode = "macro"

    criteria = load_criteria(ws)
    context_path = ws / "derived" / "context.md"
    context = context_path.read_text(encoding="utf-8") if context_path.exists() else ""

    console.print(f"Scoring ({mode})...")
    result = score(text, criteria, context, mode, backend)  # type: ignore[arg-type]

    console.print(f"\nTotal: {result.total}/{result.max_total}")
    for dim, val in result.scores.items():
        console.print(f"  {dim}: {val}")


@app.command()
def export(
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output .docx path"),
) -> None:
    """Export sequences to a single docx file."""
    from scriptsmith.exporter import export_to_docx
    from scriptsmith.workspace import validate_workspace

    ws = _resolve_workspace(workspace)
    errors = validate_workspace(ws)
    if errors:
        for e in errors:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    if output:
        out_path = Path(output)
    else:
        out_path = ws / "exports" / "improved.docx"

    export_to_docx(ws, out_path)
    console.print(f"[green]Exported to {out_path}[/green]")


@app.command()
def derive(
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w"),
    model: str = typer.Option("haiku", "--model", "-m"),
) -> None:
    """Regenerate derived/synopsis.md and derived/context.md."""
    from scriptsmith.deriver import derive_all

    ws = _resolve_workspace(workspace)
    backend = _make_backend(model=model)
    console.print("Regenerating derived files...")
    derive_all(ws, backend)
    console.print("[green]Done.[/green]")


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-V", help="Show version"),
) -> None:
    if version:
        console.print(f"scriptsmith {__version__}")
        raise typer.Exit()
