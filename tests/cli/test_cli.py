"""Unit tests for RepoContinuum Typer CLI interface."""

from pathlib import Path
from typer.testing import CliRunner
from repocontinuum.cli import app

runner = CliRunner()


def test_cli_version_command() -> None:
    """Verify version command outputs RepoContinuum version info."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "RepoContinuum" in result.stdout
    assert "0.1.0" in result.stdout


def test_cli_index_command_and_report(tmp_path: Path) -> None:
    """Verify repo index command runs, prints summary table, and exports JSON snapshot."""
    # Create sample repo
    repo = tmp_path / "cli_sample_repo"
    repo.mkdir()
    (repo / "app.py").write_text("def hello() -> str:\n    return 'world'\n", encoding="utf-8")

    output_json = tmp_path / "snapshot.json"
    result = runner.invoke(
        app,
        ["repo", "index", "--path", str(repo), "--output", str(output_json)],
    )

    assert result.exit_code == 0
    assert "Repository Intelligence Snapshot" in result.stdout
    assert "Indexed Python Files" in result.stdout
    assert output_json.exists()

    # Test reading the exported snapshot with repo report command
    report_result = runner.invoke(
        app,
        ["repo", "report", "--snapshot", str(output_json)],
    )
    assert report_result.exit_code == 0
    assert "Index Metrics Summary" in report_result.stdout


def test_cli_index_invalid_path() -> None:
    """Verify repo index command exits cleanly with non-zero exit code on invalid path."""
    result = runner.invoke(app, ["repo", "index", "--path", "C:/non_existent_folder_xyz_123"])
    assert result.exit_code != 0
