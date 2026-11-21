"""Integration tests for VerificationEngine: isolated sandbox runs, regression detection, and fail-closed safety."""

import subprocess
from pathlib import Path
from typing import List

import pytest

from repocontinuum.domain.planning import MaintenanceTask, Obligation, ObligationStatus, TaskStatus
from repocontinuum.domain.verification import (
    CheckStatus,
    Patch,
    PatchStatus,
    VerificationRunStatus,
)
from repocontinuum.execution.sandbox import (
    BaseSandboxRunner,
    DockerSandboxRunner,
    FakeSandboxRunner,
    SandboxResult,
)
from repocontinuum.patching.diff_parser import UnifiedDiffParser
from repocontinuum.verification.engine import VerificationEngine


@pytest.fixture
def sample_git_repo(tmp_path: Path) -> tuple[Path, str]:
    """Create a temporary git repository with initial commit."""
    repo_dir = tmp_path / "target_repo"
    repo_dir.mkdir()
    (repo_dir / "math_mod.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (repo_dir / "test_math.py").write_text(
        "from math_mod import add\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)

    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True
    ).stdout.strip()

    return repo_dir, sha


def test_verification_engine_successful_run(sample_git_repo):
    """Test successful verification with FakeSandboxRunner."""
    repo_dir, base_sha = sample_git_repo

    diff_content = """--- a/math_mod.py
+++ b/math_mod.py
@@ -1,2 +1,3 @@
 def add(a, b):
     return a + b
+
+def sub(a, b):
+    return a - b
"""
    patch_hash = UnifiedDiffParser.compute_patch_hash(diff_content)

    task = MaintenanceTask(
        id="task-100",
        chain_id="chain-1",
        title="Add sub function",
        status=TaskStatus.READY,
    )
    patch = Patch(
        id="patch-100",
        task_id=task.id,
        repository_id="default",
        base_sha=base_sha,
        patch_hash=patch_hash,
        diff_content=diff_content,
        changed_paths=["math_mod.py"],
        total_added_lines=3,
        total_removed_lines=0,
    )

    fake_runner = FakeSandboxRunner(
        canned_results={
            "python -m py_compile math_mod.py": SandboxResult(
                exit_code=0,
                stdout="Compiled successfully",
                stderr="",
                duration_ms=45,
                status=CheckStatus.PASSED,
                executed_in_sandbox=True,
                message="Compilation passed",
            )
        }
    )

    engine = VerificationEngine(sandbox_runner=fake_runner)
    vrun, report = engine.verify_patch(
        repo_path=repo_dir,
        task=task,
        patch=patch,
        earlier_active_obligations=[],
        check_commands=[["python", "-m", "py_compile", "math_mod.py"]],
    )

    assert vrun.status == VerificationRunStatus.COMPLETED
    assert not vrun.has_regressions
    assert report.verification_conclusion == CheckStatus.PASSED
    assert len(report.checks_executed) == 1
    assert report.checks_executed[0].status == CheckStatus.PASSED
    assert report.patch_hash == patch_hash
    # Check that original repo file was untouched
    assert "sub" not in (repo_dir / "math_mod.py").read_text(encoding="utf-8")


def test_verification_engine_detects_regression_on_earlier_obligation(sample_git_repo):
    """Test that when a patch causes an earlier active obligation to fail, a regression is flagged."""
    repo_dir, base_sha = sample_git_repo

    # Patch that breaks math_mod.py
    diff_content = """--- a/math_mod.py
+++ b/math_mod.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a + b
+    return a * b
"""
    patch_hash = UnifiedDiffParser.compute_patch_hash(diff_content)

    task = MaintenanceTask(
        id="task-200",
        chain_id="chain-1",
        title="Multiply instead of add",
        status=TaskStatus.READY,
    )
    patch = Patch(
        id="patch-200",
        task_id=task.id,
        repository_id="default",
        base_sha=base_sha,
        patch_hash=patch_hash,
        diff_content=diff_content,
        changed_paths=["math_mod.py"],
        total_added_lines=1,
        total_removed_lines=1,
    )

    earlier_obligation = Obligation(
        id="ob-1",
        chain_id="chain-1",
        source_task_id="task-099",
        description="Addition must remain accurate",
        status=ObligationStatus.ACTIVE,
        verifier_ref="test_math.py:test_add",
    )

    # Fake runner where compile passes, but test_math.py fails
    fake_runner = FakeSandboxRunner(
        canned_results={
            "python -m py_compile math_mod.py": SandboxResult(
                exit_code=0,
                stdout="Compiled ok",
                stderr="",
                duration_ms=40,
                status=CheckStatus.PASSED,
                executed_in_sandbox=True,
                message="Compilation passed",
            ),
            "python -m pytest test_math.py": SandboxResult(
                exit_code=1,
                stdout="FAILED test_math.py::test_add - assert 2 == 3",
                stderr="",
                duration_ms=120,
                status=CheckStatus.FAILED,
                executed_in_sandbox=True,
                message="Test failed: regression detected",
            ),
        }
    )

    engine = VerificationEngine(sandbox_runner=fake_runner)
    vrun, report = engine.verify_patch(
        repo_path=repo_dir,
        task=task,
        patch=patch,
        earlier_active_obligations=[earlier_obligation],
        check_commands=[["python", "-m", "py_compile", "math_mod.py"]],
    )

    assert vrun.status == VerificationRunStatus.REGRESSION_DETECTED
    assert vrun.has_regressions is True
    assert report.verification_conclusion == CheckStatus.FAILED
    assert len(report.regressions_detected) == 1
    assert "Obligation 'ob-1'" in report.regressions_detected[0]
    assert len(report.earlier_obligations_rechecked) == 1
    assert report.earlier_obligations_rechecked[0].is_regression is True


def test_verification_engine_handles_inconclusive_obligation(sample_git_repo):
    """Test that obligations without executable verifier references are reported as INCONCLUSIVE."""
    repo_dir, base_sha = sample_git_repo

    diff_content = """--- a/math_mod.py
+++ b/math_mod.py
@@ -1,2 +1,3 @@
 def add(a, b):
     return a + b
+# end
"""
    patch_hash = UnifiedDiffParser.compute_patch_hash(diff_content)
    task = MaintenanceTask(id="task-300", chain_id="chain-1", title="Comment", status=TaskStatus.READY)
    patch = Patch(
        id="patch-300",
        task_id=task.id,
        repository_id="default",
        base_sha=base_sha,
        patch_hash=patch_hash,
        diff_content=diff_content,
        changed_paths=["math_mod.py"],
        total_added_lines=1,
        total_removed_lines=0,
    )

    # Obligation with no verifier_ref
    non_executable_ob = Obligation(
        id="ob-manual",
        chain_id="chain-1",
        source_task_id="task-050",
        description="Manual visual check required",
        status=ObligationStatus.ACTIVE,
        verifier_ref=None,
    )

    fake_runner = FakeSandboxRunner(
        canned_results={
            "python -m py_compile math_mod.py": SandboxResult(
                exit_code=0,
                stdout="Ok",
                stderr="",
                duration_ms=30,
                status=CheckStatus.PASSED,
                executed_in_sandbox=True,
                message="Ok",
            )
        }
    )

    engine = VerificationEngine(sandbox_runner=fake_runner)
    vrun, report = engine.verify_patch(
        repo_path=repo_dir,
        task=task,
        patch=patch,
        earlier_active_obligations=[non_executable_ob],
        check_commands=[["python", "-m", "py_compile", "math_mod.py"]],
    )

    assert vrun.status == VerificationRunStatus.COMPLETED
    assert not vrun.has_regressions
    assert len(report.earlier_obligations_rechecked) == 1
    recheck = report.earlier_obligations_rechecked[0]
    assert recheck.status == CheckStatus.INCONCLUSIVE
    assert "No executable test verifier declared" in recheck.message


def test_verification_engine_docker_fail_closed_when_daemon_stopped(sample_git_repo):
    """Test that DockerSandboxRunner fails closed (NOT_RUN) when daemon is stopped and does not fall back to host."""
    repo_dir, base_sha = sample_git_repo

    diff_content = """--- a/math_mod.py
+++ b/math_mod.py
@@ -1,2 +1,3 @@
 def add(a, b):
     return a + b
+# fail closed test
"""
    patch_hash = UnifiedDiffParser.compute_patch_hash(diff_content)
    task = MaintenanceTask(id="task-400", chain_id="chain-1", title="Docker test", status=TaskStatus.READY)
    patch = Patch(
        id="patch-400",
        task_id=task.id,
        repository_id="default",
        base_sha=base_sha,
        patch_hash=patch_hash,
        diff_content=diff_content,
        changed_paths=["math_mod.py"],
        total_added_lines=1,
        total_removed_lines=0,
    )

    docker_runner = DockerSandboxRunner()
    # Ensure is_available is false if daemon is not running
    engine = VerificationEngine(sandbox_runner=docker_runner)

    vrun, report = engine.verify_patch(
        repo_path=repo_dir,
        task=task,
        patch=patch,
        earlier_active_obligations=[],
        check_commands=[["python", "-m", "py_compile", "math_mod.py"]],
    )

    # In our test environment, Docker daemon is not running, so it must fail closed
    if not docker_runner.is_available():
        assert report.verification_conclusion == CheckStatus.NOT_RUN
        assert vrun.status == VerificationRunStatus.FAILED
        assert any(c.status == CheckStatus.NOT_RUN for c in report.checks_executed)
        assert any(c.executed_in_sandbox is False for c in report.checks_executed)


def test_verification_engine_rejects_hash_tampering(sample_git_repo):
    """Test that if the patch content hash was altered, verification rejects it immediately."""
    repo_dir, base_sha = sample_git_repo

    diff_content = """--- a/math_mod.py
+++ b/math_mod.py
@@ -1,2 +1,3 @@
 def add(a, b):
     return a + b
+# Tampered
"""
    task = MaintenanceTask(id="task-500", chain_id="chain-1", title="Tampered", status=TaskStatus.READY)
    patch = Patch(
        id="patch-500",
        task_id=task.id,
        repository_id="default",
        base_sha=base_sha,
        patch_hash="tampered_sha256_hash_value_1234567890abcdef",
        diff_content=diff_content,
        changed_paths=["math_mod.py"],
        total_added_lines=1,
        total_removed_lines=0,
    )

    fake_runner = FakeSandboxRunner()
    engine = VerificationEngine(sandbox_runner=fake_runner)

    vrun, report = engine.verify_patch(
        repo_path=repo_dir,
        task=task,
        patch=patch,
        earlier_active_obligations=[],
    )

    assert vrun.status == VerificationRunStatus.FAILED
    assert report.verification_conclusion == CheckStatus.FAILED
    assert any("hash mismatch" in r.lower() for r in report.outstanding_risks)


def test_verification_engine_rejects_path_traversal_patch(sample_git_repo):
    """Test that path traversal patches fail before any execution occurs."""
    repo_dir, base_sha = sample_git_repo

    traversal_diff = """--- a/../../../etc/shadow
+++ b/../../../etc/shadow
@@ -0,0 +1,1 @@
+root:x:0:0:root:/root:/bin/bash
"""
    patch_hash = UnifiedDiffParser.compute_patch_hash(traversal_diff)
    task = MaintenanceTask(id="task-600", chain_id="chain-1", title="Traversal", status=TaskStatus.READY)
    patch = Patch(
        id="patch-600",
        task_id=task.id,
        repository_id="default",
        base_sha=base_sha,
        patch_hash=patch_hash,
        diff_content=traversal_diff,
        changed_paths=["../../../etc/shadow"],
        total_added_lines=1,
        total_removed_lines=0,
    )

    fake_runner = FakeSandboxRunner()
    engine = VerificationEngine(sandbox_runner=fake_runner)

    vrun, report = engine.verify_patch(
        repo_path=repo_dir,
        task=task,
        patch=patch,
        earlier_active_obligations=[],
    )

    assert vrun.status == VerificationRunStatus.FAILED
    assert report.verification_conclusion == CheckStatus.FAILED
    assert any("traversal" in r.lower() or "relative" in r.lower() for r in report.outstanding_risks)
