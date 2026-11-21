"""Command Line Interface for RepoContinuum."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from repocontinuum import __version__
from repocontinuum.config import IndexerSettings
from repocontinuum.domain.models import ParseStatus, RepositorySnapshot
from repocontinuum.indexing.indexer import RepositoryIndexer

app = typer.Typer(
    name="repocontinuum",
    help="RepoContinuum: Repository-aware software maintenance agent CLI",
    add_completion=False,
)

repo_app = typer.Typer(
    name="repo",
    help="Repository inspection and intelligence indexing",
    add_completion=False,
)
app.add_typer(repo_app)

console = Console()


@app.command()
def version() -> None:
    """Display RepoContinuum version and system environment info."""
    console.print(
        Panel.fit(
            f"[bold cyan]RepoContinuum[/bold cyan] version [bold green]{__version__}[/bold green]\n"
            f"Python: {sys.version.split()[0]} ({sys.platform})\n"
            "Architecture: Milestone 1 (Repository Intelligence Foundation)",
            title="System Info",
            border_style="cyan",
        )
    )


@repo_app.command(name="index")
def index_repo(
    path: Path = typer.Option(
        Path("."),
        "--path",
        "-p",
        help="Path to the local Python repository to index",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Path to save machine-readable JSON snapshot",
    ),
    max_size: int = typer.Option(
        1_048_576,
        "--max-size",
        help="Maximum file size in bytes to index (default: 1MB)",
    ),
    untracked: bool = typer.Option(
        True,
        "--untracked/--no-untracked",
        help="Whether to include untracked files",
    ),
) -> None:
    """Index a Python repository, display summary report, and export snapshot JSON."""
    settings = IndexerSettings(
        max_file_size_bytes=max_size,
        include_untracked=untracked,
    )
    indexer = RepositoryIndexer(settings=settings)

    with console.status("[bold blue]Indexing repository...[/bold blue]"):
        try:
            snapshot = indexer.index_repository(path)
        except Exception as e:
            console.print(f"[bold red]Indexing failed:[/bold red] {e}")
            raise typer.Exit(code=1)

    _display_snapshot_report(snapshot)

    if output:
        output_path = output.resolve()
        RepositoryIndexer.export_json(snapshot, output_path)
        console.print(f"[bold green]✓[/bold green] Snapshot saved to: [cyan]{output_path}[/cyan]")


@repo_app.command(name="report")
def report_repo(
    snapshot_path: Path = typer.Option(
        ...,
        "--snapshot",
        "-s",
        help="Path to existing JSON snapshot file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """Display a human-readable terminal report from an existing JSON snapshot."""
    try:
        snapshot = RepositoryIndexer.load_json(snapshot_path)
    except Exception as e:
        console.print(f"[bold red]Failed to load snapshot:[/bold red] {e}")
        raise typer.Exit(code=1)

    _display_snapshot_report(snapshot)


def _display_snapshot_report(snapshot: RepositorySnapshot) -> None:
    """Format and render rich terminal report for an indexed snapshot."""
    # Header metadata
    header_table = Table(show_header=False, box=None)
    header_table.add_row("[bold]Repository:[/bold]", snapshot.repository_name)
    header_table.add_row("[bold]Ref / Branch:[/bold]", snapshot.ref_name)
    header_table.add_row("[bold]Commit SHA:[/bold]", snapshot.commit_sha)
    header_table.add_row("[bold]Timestamp (UTC):[/bold]", snapshot.indexed_at)
    header_table.add_row("[bold]Indexer Version:[/bold]", snapshot.indexer_version)
    header_table.add_row("[bold]Config Hash:[/bold]", snapshot.config_hash[:16] + "...")

    console.print(
        Panel(
            header_table,
            title="[bold cyan]RepoContinuum — Repository Intelligence Snapshot[/bold cyan]",
            border_style="cyan",
        )
    )

    # Summary counts table
    summary_table = Table(title="Index Metrics Summary", show_lines=True)
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Count", justify="right")

    summary = snapshot.summary
    summary_table.add_row("Total Files Scanned", str(summary.total_files_scanned))
    summary_table.add_row("Indexed Python Files", f"[green]{summary.indexed_python_files}[/green]")
    summary_table.add_row("Skipped Files", f"[yellow]{summary.skipped_files}[/yellow]")
    summary_table.add_row(
        "Parse Failures",
        f"[red]{summary.parse_failures}[/red]" if summary.parse_failures > 0 else "0",
    )
    summary_table.add_row("Classes Discovered", str(summary.total_classes))
    summary_table.add_row("Functions Discovered", str(summary.total_functions))
    summary_table.add_row("Methods Discovered", str(summary.total_methods))
    summary_table.add_row("Imports Discovered", str(summary.total_imports))
    summary_table.add_row("Pytest Test Cases Discovered", f"[cyan]{summary.total_test_cases}[/cyan]")

    console.print(summary_table)

    # Parse failures breakdown if any
    if snapshot.parse_failures:
        err_table = Table(title="[bold red]Parse Failures[/bold red]", show_lines=True)
        err_table.add_column("File Path", style="red")
        err_table.add_column("Line", justify="right")
        err_table.add_column("Error Type")
        err_table.add_column("Message")

        for f_path in snapshot.parse_failures:
            f_meta = snapshot.files.get(f_path)
            if f_meta and f_meta.parse_error:
                err_table.add_row(
                    f_path,
                    str(f_meta.parse_error.line or "?"),
                    f_meta.parse_error.error_type,
                    f_meta.parse_error.message,
                )
        console.print(err_table)

    # Skipped files breakdown
    if snapshot.skipped_files:
        skip_table = Table(title="[bold yellow]Skipped Files Summary[/bold yellow]", show_lines=True)
        skip_table.add_column("Reason", style="bold yellow")
        skip_table.add_column("Count", justify="right")

        reasons_count = {}
        for sf in snapshot.skipped_files:
            reasons_count[sf.reason.value] = reasons_count.get(sf.reason.value, 0) + 1

        for r, cnt in sorted(reasons_count.items()):
            skip_table.add_row(r, str(cnt))

        console.print(skip_table)

    # Warnings if any
    if snapshot.warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for w in snapshot.warnings[:5]:
            console.print(f" • [yellow]{w}[/yellow]")
        if len(snapshot.warnings) > 5:
            console.print(f" • [dim]...and {len(snapshot.warnings) - 5} more warnings[/dim]")


if __name__ == "__main__":
    app()
