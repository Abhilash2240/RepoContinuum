"""Command Line Interface for RepoContinuum."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from repocontinuum import __version__
from repocontinuum.config import IndexerSettings
from repocontinuum.domain.models import ParseStatus, RepositorySnapshot
from repocontinuum.domain.planning import ObligationStatus, TaskStatus
from repocontinuum.domain.verification import CheckStatus, VerificationRunStatus
from repocontinuum.execution.sandbox import DockerSandboxRunner, FakeSandboxRunner
from repocontinuum.indexing.indexer import RepositoryIndexer
from repocontinuum.patching.diff_parser import UnifiedDiffParser
from repocontinuum.patching.security import PatchSecurityValidator
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.repository import TaskChainRepository
from repocontinuum.planning.service import TaskChainService

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

chain_app = typer.Typer(
    name="chain",
    help="Task chain, dependency DAG, and obligation ledger management",
    add_completion=False,
)
app.add_typer(chain_app)

patch_app = typer.Typer(
    name="patch",
    help="Unified diff proposal and path security validation",
    add_completion=False,
)
app.add_typer(patch_app)

verify_app = typer.Typer(
    name="verify",
    help="Isolated verification execution and evidence reporting",
    add_completion=False,
)
app.add_typer(verify_app)

console = Console()


def _get_service() -> TaskChainService:
    """Initialize database and return a TaskChainService instance."""
    db = DatabaseManager()
    db.create_tables()
    repo = TaskChainRepository(db)
    return TaskChainService(repo)


# ================= System / Version Commands =================

@app.command()
def version() -> None:
    """Display RepoContinuum version and system environment info."""
    console.print(
        Panel.fit(
            f"[bold cyan]RepoContinuum[/bold cyan] version [bold green]{__version__}[/bold green]\n"
            f"Python: {sys.version.split()[0]} ({sys.platform})\n"
            "Architecture: Milestone 1 (Indexer) + Milestone 2 (Task Chains & Obligation Ledger)",
            title="System Info",
            border_style="cyan",
        )
    )


# ================= Repository Indexer Commands =================

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

    if snapshot.warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for w in snapshot.warnings[:5]:
            console.print(f" • [yellow]{w}[/yellow]")
        if len(snapshot.warnings) > 5:
            console.print(f" • [dim]...and {len(snapshot.warnings) - 5} more warnings[/dim]")


# ================= Task Chain Commands =================

@chain_app.command(name="create")
def chain_create(
    title: str = typer.Option(..., "--title", "-t", help="Title of the maintenance task chain"),
    repo: str = typer.Option("default", "--repo", "-r", help="Repository identifier"),
    desc: str = typer.Option("", "--desc", "-d", help="Description of the chain"),
) -> None:
    """Create a new maintenance task chain."""
    service = _get_service()
    try:
        chain = service.create_chain(title=title, repository_id=repo, description=desc)
        console.print(f"[bold green]✓[/bold green] Created task chain: [bold cyan]{chain.id}[/bold cyan] ({chain.title})")
    except Exception as e:
        console.print(f"[bold red]Failed to create chain:[/bold red] {e}")
        raise typer.Exit(code=1)


@chain_app.command(name="task-add")
def task_add(
    chain_id: str = typer.Option(..., "--chain", "-c", help="Target task chain ID"),
    title: str = typer.Option(..., "--title", "-t", help="Title of the task"),
    desc: str = typer.Option("", "--desc", "-d", help="Description of the task"),
    order: int = typer.Option(0, "--order", help="Sequential order index"),
    criterion: Optional[List[str]] = typer.Option(None, "--criterion", help="Acceptance criterion (repeatable)"),
) -> None:
    """Add a maintenance task to an existing chain."""
    service = _get_service()
    try:
        task = service.add_task(
            chain_id=chain_id,
            title=title,
            description=desc,
            order_index=order,
            acceptance_criteria=criterion or [],
        )
        console.print(
            f"[bold green]✓[/bold green] Added task [bold cyan]{task.id}[/bold cyan]: {task.title} "
            f"([green]{task.status.value}[/green], {len(task.acceptance_criteria)} obligations)"
        )
    except Exception as e:
        console.print(f"[bold red]Failed to add task:[/bold red] {e}")
        raise typer.Exit(code=1)


@chain_app.command(name="dep-add")
def dep_add(
    chain_id: str = typer.Option(..., "--chain", "-c", help="Target task chain ID"),
    pred: str = typer.Option(..., "--pred", "-p", help="Predecessor task ID (must finish first)"),
    succ: str = typer.Option(..., "--succ", "-s", help="Successor task ID (dependent)"),
) -> None:
    """Add a directed predecessor -> successor dependency edge."""
    service = _get_service()
    try:
        dep = service.add_dependency(
            chain_id=chain_id,
            predecessor_task_id=pred,
            successor_task_id=succ,
        )
        console.print(
            f"[bold green]✓[/bold green] Added dependency: [cyan]{dep.predecessor_task_id}[/cyan] ➔ [cyan]{dep.successor_task_id}[/cyan]"
        )
    except Exception as e:
        console.print(f"[bold red]Failed to add dependency:[/bold red] {e}")
        raise typer.Exit(code=1)


@chain_app.command(name="validate")
def chain_validate(
    chain_id: str = typer.Option(..., "--chain", "-c", help="Target task chain ID"),
) -> None:
    """Validate DAG acyclicity, missing dependencies, and identify blocked tasks."""
    service = _get_service()
    try:
        report = service.validate_chain(chain_id)
        if report.is_valid:
            console.print(f"[bold green]✓ Valid DAG:[/bold green] {report.explanation}")
            if report.blocked_tasks:
                console.print(f"[yellow]Currently blocked tasks ({len(report.blocked_tasks)}):[/yellow]")
                for task_id, unmet in report.blocked_tasks.items():
                    console.print(f"  • [bold]{task_id}[/bold] waiting on: {', '.join(unmet)}")
        else:
            console.print(f"[bold red]✗ Invalid DAG:[/bold red] {report.explanation}")
            raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[bold red]Validation error:[/bold red] {e}")
        raise typer.Exit(code=1)


@chain_app.command(name="plan")
def chain_plan(
    chain_id: str = typer.Option(..., "--chain", "-c", help="Target task chain ID"),
) -> None:
    """Display the stable topological execution order for tasks in a chain."""
    service = _get_service()
    try:
        plan = service.get_execution_plan(chain_id)
        table = Table(title=f"Execution Plan (Topological Order) — Chain {chain_id}", show_lines=True)
        table.add_column("Step", justify="right", style="bold")
        table.add_column("Task ID", style="cyan")
        table.add_column("Title")
        table.add_column("Status")
        table.add_column("Obligations", justify="right")

        for idx, task in enumerate(plan, start=1):
            status_color = "green" if task.status == TaskStatus.COMPLETED else ("yellow" if task.status == TaskStatus.READY else "red")
            table.add_row(
                str(idx),
                task.id,
                task.title,
                f"[{status_color}]{task.status.value}[/{status_color}]",
                str(len(task.acceptance_criteria)),
            )

        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Failed to generate plan:[/bold red] {e}")
        raise typer.Exit(code=1)


@chain_app.command(name="status")
def chain_status(
    chain_id: str = typer.Option(..., "--chain", "-c", help="Target task chain ID"),
) -> None:
    """Display comprehensive status for tasks in a chain."""
    service = _get_service()
    try:
        chain = service.get_chain(chain_id)
        if not chain:
            console.print(f"[bold red]Task chain '{chain_id}' not found.[/bold red]")
            raise typer.Exit(code=1)

        tasks = service.repo.get_tasks_for_chain(chain_id)
        report = service.validate_chain(chain_id)

        header = Table(show_header=False, box=None)
        header.add_row("[bold]Chain ID:[/bold]", chain.id)
        header.add_row("[bold]Title:[/bold]", chain.title)
        header.add_row("[bold]Status:[/bold]", chain.status.value)
        header.add_row("[bold]Total Tasks:[/bold]", str(len(tasks)))
        console.print(Panel(header, title="Task Chain Overview", border_style="cyan"))

        table = Table(title="Tasks in Chain", show_lines=True)
        table.add_column("Task ID", style="cyan")
        table.add_column("Title")
        table.add_column("Status")
        table.add_column("Prerequisites Status")

        for t in tasks:
            blocked_by = report.blocked_tasks.get(t.id, [])
            if blocked_by:
                prereq_str = f"[yellow]Waiting on: {', '.join(blocked_by)}[/yellow]"
            else:
                prereq_str = "[green]Prerequisites satisfied[/green]"

            table.add_row(t.id, t.title, t.status.value, prereq_str)

        console.print(table)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[bold red]Failed to get status:[/bold red] {e}")
        raise typer.Exit(code=1)


@chain_app.command(name="obligations")
def chain_obligations(
    chain_id: str = typer.Option(..., "--chain", "-c", help="Target task chain ID"),
) -> None:
    """Display the full acceptance obligation ledger (active, superseded, withdrawn)."""
    service = _get_service()
    try:
        obligations = service.get_obligations_for_chain(chain_id)
        table = Table(title=f"Obligation Ledger — Chain {chain_id}", show_lines=True)
        table.add_column("Obligation ID", style="cyan")
        table.add_column("Source Task", style="dim")
        table.add_column("Description")
        table.add_column("Status")
        table.add_column("Verifier Ref", style="dim")
        table.add_column("Status Reason")

        for ob in obligations:
            if ob.status == ObligationStatus.ACTIVE:
                status_fmt = "[bold green]active[/bold green]"
            elif ob.status == ObligationStatus.SUPERSEDED:
                status_fmt = "[yellow]superseded[/yellow]"
            else:
                status_fmt = "[dim red]withdrawn[/dim red]"

            table.add_row(
                ob.id,
                ob.source_task_id,
                ob.description,
                status_fmt,
                ob.verifier_ref or "-",
                ob.status_reason or "-",
            )

        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Failed to list obligations:[/bold red] {e}")
        raise typer.Exit(code=1)


@chain_app.command(name="checkpoint")
def chain_checkpoint(
    chain_id: str = typer.Option(..., "--chain", "-c", help="Target task chain ID"),
) -> None:
    """Persist an atomic checkpoint snapshot of the chain."""
    service = _get_service()
    try:
        cp = service.create_checkpoint(chain_id)
        console.print(
            f"[bold green]✓[/bold green] Created checkpoint #[bold cyan]{cp.checkpoint_number}[/bold cyan] "
            f"([dim]{cp.id}[/dim]) for chain [bold]{chain_id}[/bold]"
        )
    except Exception as e:
        console.print(f"[bold red]Failed to create checkpoint:[/bold red] {e}")
        raise typer.Exit(code=1)


@chain_app.command(name="resume")
def chain_resume(
    chain_id: str = typer.Option(..., "--chain", "-c", help="Target task chain ID"),
) -> None:
    """Resume a chain from its persisted state/checkpoint."""
    service = _get_service()
    try:
        chain = service.resume_chain(chain_id)
        console.print(f"[bold green]✓[/bold green] Resumed task chain [bold cyan]{chain.id}[/bold cyan] ({chain.title})")
    except Exception as e:
        console.print(f"[bold red]Failed to resume chain:[/bold red] {e}")
        raise typer.Exit(code=1)


# ================= Patch Commands =================

@patch_app.command(name="validate")
def patch_validate(
    diff_file: Path = typer.Option(
        ...,
        "--diff",
        "-d",
        help="Path to unified diff file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """Validate unified diff syntax and security boundaries."""
    try:
        content = diff_file.read_text(encoding="utf-8")
        file_diffs = UnifiedDiffParser.parse(content)
        changed_paths = PatchSecurityValidator.validate_patch_security(file_diffs)
        patch_hash = UnifiedDiffParser.compute_patch_hash(content)

        table = Table(title=f"Patch Validation — {diff_file.name}", show_lines=True)
        table.add_column("File Target", style="cyan")
        table.add_column("Type")
        table.add_column("Hunks", justify="right")
        table.add_column("Added", justify="right", style="green")
        table.add_column("Removed", justify="right", style="red")

        for fd in file_diffs:
            change_type = "Created" if fd.is_creation else ("Deleted" if fd.is_deletion else "Modified")
            target = fd.new_path if not fd.is_deletion else fd.old_path
            table.add_row(
                target,
                change_type,
                str(len(fd.hunks)),
                f"+{fd.added_lines}",
                f"-{fd.removed_lines}",
            )

        console.print(table)
        console.print(f"[bold green]✓ Valid Patch:[/bold green] SHA-256 = `{patch_hash}` ({len(changed_paths)} files changed)")
    except Exception as e:
        console.print(f"[bold red]Patch validation failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@patch_app.command(name="propose")
def patch_propose(
    task_id: str = typer.Option(..., "--task", "-t", help="Target task ID"),
    diff_file: Path = typer.Option(
        ...,
        "--diff",
        "-d",
        help="Path to unified diff file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    base_sha: str = typer.Option(..., "--base-sha", "-b", help="Exact base commit SHA"),
) -> None:
    """Validate, hash, and register a patch proposal for a task."""
    service = _get_service()
    try:
        content = diff_file.read_text(encoding="utf-8")
        patch = service.propose_patch(task_id=task_id, diff_content=content, base_sha=base_sha)
        console.print(
            f"[bold green]✓[/bold green] Registered patch [bold cyan]{patch.id}[/bold cyan] "
            f"bound to task [bold]{task_id}[/bold] and base [dim]{patch.base_sha[:10]}...[/dim] "
            f"(Hash: [yellow]{patch.patch_hash[:16]}...[/yellow])"
        )
    except Exception as e:
        console.print(f"[bold red]Failed to propose patch:[/bold red] {e}")
        raise typer.Exit(code=1)


# ================= Verification Commands =================

@verify_app.command(name="run")
def verify_run_cmd(
    task_id: str = typer.Option(..., "--task", "-t", help="Task ID being verified"),
    patch_id: str = typer.Option(..., "--patch", "-p", help="Patch ID to verify"),
    repo_path: Path = typer.Option(
        Path("."),
        "--repo",
        "-r",
        help="Path to repository root",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    fake_sandbox: bool = typer.Option(
        False,
        "--fake-sandbox",
        help="Use deterministic fake sandbox runner for local testing",
    ),
) -> None:
    """Execute isolated patch verification and obligation re-checking."""
    service = _get_service()
    runner = FakeSandboxRunner() if fake_sandbox else DockerSandboxRunner()

    with console.status("[bold blue]Executing isolated verification pipeline...[/bold blue]"):
        try:
            vrun, report = service.verify_patch(
                task_id=task_id,
                patch_id=patch_id,
                repo_path=repo_path,
                sandbox_runner=runner,
            )
        except Exception as e:
            console.print(f"[bold red]Verification execution failed:[/bold red] {e}")
            raise typer.Exit(code=1)

    _display_verification_report(vrun, report)


@verify_app.command(name="report")
def verify_report_cmd(
    run_id: str = typer.Option(..., "--run", help="Verification run ID"),
) -> None:
    """Display the full evidence report for a verification run."""
    service = _get_service()
    try:
        vrun = service.get_verification_run(run_id)
        if not vrun:
            console.print(f"[bold red]Verification run '{run_id}' not found.[/bold red]")
            raise typer.Exit(code=1)

        report = service.get_evidence_report(run_id)
        if not report:
            console.print(f"[bold red]Evidence report for run '{run_id}' not found.[/bold red]")
            raise typer.Exit(code=1)

        _display_verification_report(vrun, report)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[bold red]Failed to load report:[/bold red] {e}")
        raise typer.Exit(code=1)


def _display_verification_report(vrun: VerificationRun, report: EvidenceReport) -> None:
    """Render formatted verification report table and evidence summary."""
    status_color = "green" if report.verification_conclusion == CheckStatus.PASSED else "red"
    header = Table(show_header=False, box=None)
    header.add_row("[bold]Verification Run:[/bold]", vrun.id)
    header.add_row("[bold]Task ID:[/bold]", report.task_id)
    header.add_row("[bold]Base Commit SHA:[/bold]", report.base_sha)
    header.add_row("[bold]Patch Hash:[/bold]", report.patch_hash[:16] + "...")
    header.add_row("[bold]Sandbox Runner:[/bold]", f"{vrun.sandbox_type.value} ({vrun.image_tag})")
    header.add_row("[bold]Conclusion:[/bold]", f"[{status_color}]{report.verification_conclusion.value}[/{status_color}]")

    console.print(
        Panel(
            header,
            title="[bold cyan]RepoContinuum — Verification Evidence Report[/bold cyan]",
            border_style="cyan",
        )
    )

    # Checks table
    checks_table = Table(title="Executed Checks", show_lines=True)
    checks_table.add_column("Check Name", style="bold")
    checks_table.add_column("Status")
    checks_table.add_column("Exit Code", justify="right")
    checks_table.add_column("Duration", justify="right")
    checks_table.add_column("Message")

    for chk in report.checks_executed:
        chk_color = "green" if chk.status == CheckStatus.PASSED else "red"
        checks_table.add_row(
            chk.name,
            f"[{chk_color}]{chk.status.value}[/{chk_color}]",
            str(chk.exit_code if chk.exit_code is not None else "-"),
            f"{chk.duration_ms}ms",
            chk.message,
        )
    console.print(checks_table)

    # Earlier obligations rechecked
    if report.earlier_obligations_rechecked:
        ob_table = Table(title="Earlier Obligations Re-verified", show_lines=True)
        ob_table.add_column("Obligation ID", style="cyan")
        ob_table.add_column("Description")
        ob_table.add_column("Verifier Ref", style="dim")
        ob_table.add_column("Result")

        for o in report.earlier_obligations_rechecked:
            if o.is_regression:
                res_str = "[bold red]REGRESSION DETECTED[/bold red]"
            elif o.status == CheckStatus.PASSED:
                res_str = "[green]PASSED[/green]"
            else:
                res_str = f"[yellow]{o.status.value}[/yellow]"
            ob_table.add_row(o.obligation_id, o.description, o.verifier_ref or "-", res_str)

        console.print(ob_table)

    # Regressions alert
    if report.regressions_detected:
        console.print("\n[bold red]⚠️ REGRESSIONS DETECTED:[/bold red]")
        for reg in report.regressions_detected:
            console.print(f" • [red]{reg}[/red]")


if __name__ == "__main__":
    app()
