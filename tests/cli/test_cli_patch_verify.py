"""CLI tests for patch validation, proposal, and isolated verification commands."""

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from repocontinuum.cli import app

runner = CliRunner()


@pytest.fixture
def cli_test_env(tmp_path: Path, monkeypatch):
    """Set up an isolated database and sample git repo for CLI tests."""
    test_db = tmp_path / "cli_test.db"
    monkeypatch.setenv("REPOCONTINUUM_DATABASE_URL", f"sqlite:///{test_db.as_posix()}")

    repo_dir = tmp_path / "cli_git_repo"
    repo_dir.mkdir()
    (repo_dir / "calculator.py").write_text("def mul(a, b):\n    return a * b\n", encoding="utf-8")

    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "CLITester"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "cli@test.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)

    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True
    ).stdout.strip()

    # Create chain and task using CLI
    res_chain = runner.invoke(app, ["chain", "create", "--title", "CLI Test Chain", "--repo", "cli-repo"])
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
            "Implement div",
            "--criterion",
            "Must divide",
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


def test_cli_patch_validate_success(tmp_path: Path):
    """Test 'patch validate' on a valid unified diff."""
    diff_file = tmp_path / "test.patch"
    diff_file.write_text(
        """--- a/calculator.py
+++ b/calculator.py
@@ -1,2 +1,3 @@
 def mul(a, b):
     return a * b
+
+def div(a, b):
    return a / b
""",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["patch", "validate", "--diff", str(diff_file)])
    assert result.exit_code == 0
    assert "Valid Patch" in result.stdout
    assert "calculator.py" in result.stdout


def test_cli_patch_validate_traversal_rejected(tmp_path: Path):
    """Test 'patch validate' rejects path traversal."""
    diff_file = tmp_path / "traversal.patch"
    diff_file.write_text(
        """--- a/../../secret.txt
+++ b/../../secret.txt
@@ -0,0 +1,1 @@
+leak
""",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["patch", "validate", "--diff", str(diff_file)])
    assert result.exit_code != 0
    assert "failed" in result.stdout.lower() or "traversal" in result.stdout.lower()


def test_cli_patch_propose_and_verify_run(cli_test_env):
    """Test proposing a patch, running verification with fake sandbox, and querying evidence report."""
    diff_file = cli_test_env["repo_dir"] / "my_change.patch"
    diff_file.write_text(
        """--- a/calculator.py
+++ b/calculator.py
@@ -1,2 +1,4 @@
 def mul(a, b):
     return a * b
+def div(a, b):
+    return a / b
""",
        encoding="utf-8",
    )

    # 1. Propose patch
    propose_result = runner.invoke(
        app,
        [
            "patch",
            "propose",
            "--task",
            cli_test_env["task_id"],
            "--diff",
            str(diff_file),
            "--base-sha",
            cli_test_env["base_sha"],
        ],
    )
    assert propose_result.exit_code == 0, propose_result.stdout
    assert "Registered patch" in propose_result.stdout

    # Extract patch ID from stdout
    import re
    match = re.search(r"pat-[a-f0-9]+", propose_result.stdout)
    assert match is not None
    patch_id = match.group(0)

    # 2. Run verification with --fake-sandbox
    verify_result = runner.invoke(
        app,
        [
            "verify",
            "run",
            "--task",
            cli_test_env["task_id"],
            "--patch",
            patch_id,
            "--repo",
            str(cli_test_env["repo_dir"]),
            "--fake-sandbox",
        ],
    )
    assert verify_result.exit_code == 0, verify_result.stdout
    assert "RepoContinuum — Verification Evidence Report" in verify_result.stdout
    assert "Executed Checks" in verify_result.stdout

    # Extract run ID from stdout
    run_match = re.search(r"vrun-[a-f0-9]+", verify_result.stdout)
    assert run_match is not None
    run_id = run_match.group(0)

    # 3. Query report via CLI
    report_result = runner.invoke(app, ["verify", "report", "--run", run_id])
    assert report_result.exit_code == 0, report_result.stdout
    assert "Verification Run:" in report_result.stdout
    assert run_id in report_result.stdout
