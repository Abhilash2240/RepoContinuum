"""Unit tests for RepoContinuum Typer CLI task chain commands."""

import os
from pathlib import Path
from typer.testing import CliRunner
from repocontinuum.cli import app

runner = CliRunner()


def test_cli_chain_workflow(tmp_path: Path, monkeypatch) -> None:
    """Verify complete chain lifecycle via CLI commands using an isolated database."""
    test_db = tmp_path / "cli_test.db"
    monkeypatch.setenv("REPOCONTINUUM_DATABASE_URL", f"sqlite:///{test_db}")

    # 1. Create chain
    res_chain = runner.invoke(app, ["chain", "create", "--title", "CLI Test Chain", "--repo", "repo-1"])
    assert res_chain.exit_code == 0
    assert "Created task chain:" in res_chain.stdout

    # Extract chain ID from output: "Created task chain: chn-xxxx (CLI Test Chain)"
    chain_id = res_chain.stdout.split("Created task chain:")[1].split()[0].strip()

    # 2. Add Task 1
    res_t1 = runner.invoke(
        app,
        [
            "chain",
            "task-add",
            "--chain",
            chain_id,
            "--title",
            "Task 1",
            "--criterion",
            "Criterion A",
            "--order",
            "1",
        ],
    )
    assert res_t1.exit_code == 0
    t1_id = res_t1.stdout.split("Added task")[1].split(":")[0].strip()

    # 3. Add Task 2
    res_t2 = runner.invoke(
        app,
        [
            "chain",
            "task-add",
            "--chain",
            chain_id,
            "--title",
            "Task 2",
            "--criterion",
            "Criterion B",
            "--order",
            "2",
        ],
    )
    assert res_t2.exit_code == 0
    t2_id = res_t2.stdout.split("Added task")[1].split(":")[0].strip()

    # 4. Add dependency: Task 1 -> Task 2
    res_dep = runner.invoke(
        app,
        ["chain", "dep-add", "--chain", chain_id, "--pred", t1_id, "--succ", t2_id],
    )
    assert res_dep.exit_code == 0
    assert "Added dependency:" in res_dep.stdout

    # 5. Validate chain
    res_val = runner.invoke(app, ["chain", "validate", "--chain", chain_id])
    assert res_val.exit_code == 0
    assert "Valid DAG:" in res_val.stdout

    # 6. Display plan
    res_plan = runner.invoke(app, ["chain", "plan", "--chain", chain_id])
    assert res_plan.exit_code == 0
    assert "Execution Plan" in res_plan.stdout
    assert "Task 1" in res_plan.stdout
    assert "Task 2" in res_plan.stdout

    # 7. Display status
    res_status = runner.invoke(app, ["chain", "status", "--chain", chain_id])
    assert res_status.exit_code == 0
    assert "Task Chain Overview" in res_status.stdout

    # 8. Display obligations
    res_obs = runner.invoke(app, ["chain", "obligations", "--chain", chain_id])
    assert res_obs.exit_code == 0
    assert "Obligation Ledger" in res_obs.stdout
    assert "Criterion A" in res_obs.stdout

    # 9. Create checkpoint
    res_cp = runner.invoke(app, ["chain", "checkpoint", "--chain", chain_id])
    assert res_cp.exit_code == 0
    assert "Created checkpoint #" in res_cp.stdout

    # 10. Resume chain
    res_resume = runner.invoke(app, ["chain", "resume", "--chain", chain_id])
    assert res_resume.exit_code == 0
    assert "Resumed task chain" in res_resume.stdout
