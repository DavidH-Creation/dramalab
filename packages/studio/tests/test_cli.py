from typer.testing import CliRunner
from dramalab_studio.cli import app

runner = CliRunner()

def test_help():
    """CLI should show help text."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "dramalab" in result.output.lower() or "DramaLab" in result.output

def test_start_help():
    """start command should show help."""
    result = runner.invoke(app, ["start", "--help"])
    assert result.exit_code == 0
    assert "--port" in result.output
    assert "--api-port" in result.output
    assert "--no-browser" in result.output
