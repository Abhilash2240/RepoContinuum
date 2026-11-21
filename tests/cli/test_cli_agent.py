"""CLI tests for bounded LLM agent subcommands."""

import re
import subprocess
from pathlib import Path
import pytest
from typer.testing import CliRunner

from repocontinuum.cli import app
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.repository import TaskChainRepository
from repocontinuum.planning.service import TaskChainService

runner = CliRunner()


@pytest.fixture
def cli_agent_env(tmp_path: Path, monkeypatch):
    """Set up an isolated database and git repo for CLI agent tests."""
    test_db = tmp_path / "cli_agent_test.db"
    db_url = f"sqlite:///{test_db.as_posix()}"
    monkeypatch.setenv("REPOCONTINUUM_DATABASE_URL", db_url)
    monkeypatch.setenv("REPOCONTINUUM_LLM_PROVIDER", "fake")

    repo_dir = tmp_path / "cli_agent_git_repo"
    repo_dir.mkdir()
    (repo_dir / "calc.py").write_text("def subtract(a, b):\n    return a - b\n", encoding="utf-8")

    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "CLIAgentTester"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "agent@cli.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)

    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True
    ).stdout.strip()

    # Pre-populate chain and task using CLI
    res_chain = runner.invoke(app, ["chain", "create", "--title", "CLI Agent Chain", "--repo", "cli-agent-repo"])
    assert res_chain.exit_code == 0
    chain_id = res_chain.stdout.split("Created task chain:")[1].split()[0].strip()

    res_task = runner.invoke(
        app,
        [
            "chain",
            "task-add",
            "--chain",
            chain_id,
            "--title",
            "Implement multiply",
            "--criterion",
            "Multiply must work",
        ],
    )
    assert res_task.exit_code == 0
    task_id = res_task.stdout.split("Added task")[1].split(":")[0].strip()

    return {
        "repo_dir": repo_dir,
        "base_sha": base_sha,
        "chain_id": chain_id,
        "task_id": task_id,
    }


def test_cli_agent_lifecycle(cli_agent_env):
    """Test full agent CLI command flow: analyze -> plan -> approve -> propose -> verify -> status -> report."""
    task_id = cli_agent_env["task_id"]
    repo_dir = str(cli_agent_env["repo_dir"])

    # 1. Analyze
    res_analyze = runner.invoke(app, ["agent", "analyze", "--task", task_id, "--repo", repo_dir])
    assert res_analyze.exit_code == 0, res_analyze.stdout
    assert "Issue Analysis" in res_analyze.stdout
    assert "Agent Run:" in res_analyze.stdout

    run_match = re.search(r"arun-[a-f0-9]+", res_analyze.stdout)
    assert run_match is not None
    run_id = run_match.group(0)

    # 2. Plan
    res_plan = runner.invoke(app, ["agent", "plan", "--task", task_id, "--run", run_id, "--repo", repo_dir])
    assert res_plan.exit_code == 0, res_plan.stdout
    assert "Proposed Plan" in res_plan.stdout
    assert "Human approval required" in res_plan.stdout

    # 3. Approve Plan
    res_approve = runner.invoke(app, ["agent", "approve-plan", "--task", task_id, "--run", run_id, "--approver", "dev-lead"])
    assert res_approve.exit_code == 0, res_approve.stdout
    assert "Plan Approved" in res_approve.stdout

    # 4. Propose Patch
    res_prop = runner.invoke(app, ["agent", "propose", "--task", task_id, "--run", run_id, "--repo", repo_dir])
    assert res_prop.exit_code == 0, res_prop.stdout
    assert "Patch Proposed" in res_prop.stdout

    # 5. Verify (with fake sandbox)
    res_verify = runner.invoke(app, ["agent", "verify", "--task", task_id, "--run", run_id, "--repo", repo_dir, "--fake-sandbox"])
    assert res_verify.exit_code == 0, res_verify.stdout
    assert "VERIFICATION PASSED" in res_verify.stdout

    # 6. Status
    res_status = runner.invoke(app, ["agent", "status", "--run", run_id])
    assert res_status.exit_code == 0, res_status.stdout
    assert "Agent Run Status" in res_status.stdout
    assert run_id in res_status.stdout

    # 7. Report
    res_report = runner.invoke(app, ["agent", "report", "--run", run_id])
    assert res_report.exit_code == 0, res_report.stdout
    assert "Task Plan" in res_report.stdout
