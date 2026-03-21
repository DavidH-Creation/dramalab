"""CLI entry point for Forge Studio."""

from __future__ import annotations

import subprocess
import sys
import webbrowser
from pathlib import Path

import typer

app = typer.Typer(name="forge-studio", help="Web UI for creative-writing optimization tools.")


@app.command()
def start(
    port: int = typer.Option(3000, "--port", "-p", help="Frontend port"),
    api_port: int = typer.Option(8000, "--api-port", help="Backend API port"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser"),
) -> None:
    """Start Forge Studio (backend + frontend)."""
    import uvicorn
    from forge_studio.server import create_app

    typer.echo(f"Starting Forge Studio...")
    typer.echo(f"  API: http://localhost:{api_port}")
    typer.echo(f"  UI:  http://localhost:{port}")

    if not no_browser:
        webbrowser.open(f"http://localhost:{port}")

    app_instance = create_app()
    uvicorn.run(app_instance, host="0.0.0.0", port=api_port, log_level="info")


@app.callback()
def main() -> None:
    pass
