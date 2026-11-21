"""Integration tests for the bounded LLM agent workflow and repair loop."""

import subprocess
from pathlib import Path
import pytest

from repocontinuum.agent.config import AgentSettings
from repocontinuum.agent.providers.fake import FakeLLMProvider
from repocontinuum.agent.schemas.issue_analysis import IssueAnalysis
from repocontinuum.agent.schemas.patch_proposal import PatchProposal
from repocontinuum.agent.schemas.task_plan import TaskPlan
from repocontinuum.agent.service import AgentService
from repocontinuum.domain.agent import AgentRunStatus
from repocontinuum.domain.planning import Obligation, ObligationStatus, TaskStatus
from repocontinuum.domain.verification import CheckStatus
from repocontinuum.execution.sandbox import FakeSandboxRunner, SandboxResult
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.repository import TaskChainRepository
from repocontinuum.planning.service import TaskChainService


@pytest.fixture
def workflow_test_env(tmp_path: Path):
    """Create a temporary git repository and task chain service for workflow testing."""
    repo_dir = tmp_path / "agent_workflow_repo"
    repo_dir.mkdir()
    math_file = repo_dir / "math_ops.py"
    math_file.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    test_file = repo_dir / "test_math_ops.py"
    test_file.write_text(
        "from math_ops import add\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "AgentTester"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "agent@tester.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)

    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True
    ).stdout.strip()

    db_path = tmp_path / "workflow_test.db"
    db = DatabaseManager(database_url=f"sqlite:///{db_path.as_posix()}")
    db.create_tables()
    repo = TaskChainRepository(db)
    service = TaskChainService(repo)

    chain = service.create_chain(title="Agent Maintenance Chain", repository_id="agent-repo")
    task = service.add_task(
        chain_id=chain.id,
        title="Add multiply operation",
        description="Implement multiply(a, b) in math_ops.py",
        acceptance_criteria=["Must calculate product correctly"],
    )

    return {
        "repo_dir": repo_dir,
        "base_sha": base_sha,
        "chain": chain,
        "task": task,
        "service": service,
    }


def test_end_to_end_agent_workflow_successful_run(workflow_test_env):
    """Verify complete end-to-end workflow: analyze -> plan -> approve -> propose -> verify."""
    repo_dir = workflow_test_env["repo_dir"]
    base_sha = workflow_test_env["base_sha"]
    task = workflow_test_env["task"]
    service = workflow_test_env["service"]

    # Configure canned responses in FakeLLMProvider
    fake_provider = FakeLLMProvider()

    canned_analysis = IssueAnalysis(
        problem_summary="Add multiply function to math_ops.py",
        observed_behaviour="Only add function exists",
        expected_behaviour="multiply(a, b) returns a * b",
        acceptance_criteria=["multiply(2, 3) == 6"],
        likely_affected_files=["math_ops.py"],
        likely_affected_symbols=["multiply"],
        relevant_tests=["test_math_ops.py"],
        risk_level="low",
        assumptions=[],
        confidence=0.95,
    )
    fake_provider.set_canned_response(IssueAnalysis, canned_analysis)

    canned_plan = TaskPlan(
        task_id=task.id,
        objective="Implement multiply function",
        ordered_steps=["Edit math_ops.py to add multiply", "Compile and verify"],
        affected_files=["math_ops.py"],
        affected_symbols=["multiply"],
        test_strategy="py_compile math_ops.py",
        active_obligations=[],
        risks=[],
        assumptions=[],
        unresolved_questions=[],
        expected_completion_conditions=["math_ops.py contains multiply"],
    )
    fake_provider.set_canned_response(TaskPlan, canned_plan)

    valid_diff = """--- a/math_ops.py
+++ b/math_ops.py
@@ -1,2 +1,5 @@
 def add(a, b):
     return a + b
+
+def multiply(a, b):
+    return a * b
"""
    canned_patch = PatchProposal(
        task_id=task.id,
        base_commit_sha=base_sha,
        summary="Add multiply function",
        unified_diff=valid_diff,
        changed_paths=["math_ops.py"],
        intended_behaviour="Multiplies numbers",
        affected_obligations=[],
        verification_plan=["python -m py_compile math_ops.py"],
        assumptions=[],
        known_limitations=[],
    )
    fake_provider.set_canned_response(PatchProposal, canned_patch)

    agent_service = AgentService(service=service, provider=fake_provider)

    # 1. Analyze Task
    arun, analysis = agent_service.analyze_task(task_id=task.id, repo_path=repo_dir)
    assert arun.status == AgentRunStatus.ANALYSIS_COMPLETED
    assert analysis.problem_summary.startswith("Add multiply")

    # 2. Plan Task
    arun2, plan = agent_service.plan_task(task_id=task.id, repo_path=repo_dir, run_id=arun.id)
    assert arun2.status == AgentRunStatus.PLAN_PROPOSED
    assert len(plan.ordered_steps) == 2

    # 3. Guard: Propose patch before plan approval must fail!
    with pytest.raises(ValueError) as exc_guard:
        agent_service.propose_patch(task_id=task.id, run_id=arun2.id, repo_path=repo_dir)
    assert "approval required" in str(exc_guard.value).lower()

    # 4. Human approves plan
    arun3 = agent_service.approve_plan(task_id=task.id, run_id=arun2.id, approver="senior-engineer")
    assert arun3.status == AgentRunStatus.PLAN_APPROVED
    assert arun3.plan_approved_by == "senior-engineer"

    # Task status in database must now be PLANNED
    updated_task = service.repo.get_task(task.id)
    assert updated_task.status == TaskStatus.PLANNED

    # 5. Propose Patch
    arun4, prop = agent_service.propose_patch(task_id=task.id, run_id=arun3.id, repo_path=repo_dir)
    assert arun4.status == AgentRunStatus.PATCH_PROPOSED
    assert arun4.proposed_patch_id is not None
    assert arun4.proposed_patch_hash is not None

    # 6. Verify with fake sandbox runner
    fake_sandbox = FakeSandboxRunner(
        command_responses={
            "python -m py_compile math_ops.py": SandboxResult(
                status=CheckStatus.PASSED,
                exit_code=0,
                duration_ms=25,
                stdout="Compiled ok",
                stderr="",
                executed_in_sandbox=True,
            )
        }
    )

    arun5, vrun, report = agent_service.verify_and_repair(
        task_id=task.id,
        run_id=arun4.id,
        repo_path=repo_dir,
        sandbox_runner=fake_sandbox,
        check_commands=[["python", "-m", "py_compile", "math_ops.py"]],
    )

    assert arun5.status == AgentRunStatus.VERIFICATION_PASSED
    assert vrun.status.value == "COMPLETED"
    assert not vrun.has_regressions
    assert report.verification_conclusion == CheckStatus.PASSED


def test_agent_repair_loop_on_initial_failure(workflow_test_env):
    """Verify that when an initial patch fails verification, the agent enters bounded repair."""
    repo_dir = workflow_test_env["repo_dir"]
    base_sha = workflow_test_env["base_sha"]
    task = workflow_test_env["task"]
    service = workflow_test_env["service"]

    # Initial broken patch with a syntax error
    broken_diff = """--- a/math_ops.py
+++ b/math_ops.py
@@ -1,2 +1,3 @@
 def add(a, b):
     return a + b
+def broken(
"""
    # Repaired patch with valid syntax
    repaired_diff = """--- a/math_ops.py
+++ b/math_ops.py
@@ -1,2 +1,4 @@
 def add(a, b):
     return a + b
+def multiply(a, b):
+    return a * b
"""

    fake_provider = FakeLLMProvider()

    canned_plan = TaskPlan(
        task_id=task.id,
        objective="Fix math_ops.py",
        ordered_steps=["Edit math_ops.py"],
        affected_files=["math_ops.py"],
        affected_symbols=["multiply"],
        test_strategy="py_compile",
        active_obligations=[],
        risks=[],
        assumptions=[],
        unresolved_questions=[],
        expected_completion_conditions=["ok"],
    )
    fake_provider.set_canned_response(TaskPlan, canned_plan)

    initial_patch = PatchProposal(
        task_id=task.id,
        base_commit_sha=base_sha,
        summary="Initial attempt",
        unified_diff=broken_diff,
        changed_paths=["math_ops.py"],
        intended_behaviour="Adds broken function",
        affected_obligations=[],
        verification_plan=["python -m py_compile math_ops.py"],
        assumptions=[],
        known_limitations=[],
    )
    fake_provider.set_canned_response(PatchProposal, initial_patch)

    agent_service = AgentService(service=service, provider=fake_provider)

    arun, _ = agent_service.plan_task(task_id=task.id, repo_path=repo_dir)
    agent_service.approve_plan(task_id=task.id, run_id=arun.id)
    arun2, _ = agent_service.propose_patch(task_id=task.id, run_id=arun.id, repo_path=repo_dir)

    # Now change canned response to the repaired patch for the repair iteration
    repaired_patch = PatchProposal(
        task_id=task.id,
        base_commit_sha=base_sha,
        summary="Repaired attempt",
        unified_diff=repaired_diff,
        changed_paths=["math_ops.py"],
        intended_behaviour="Adds multiply correctly",
        affected_obligations=[],
        verification_plan=["python -m py_compile math_ops.py"],
        assumptions=[],
        known_limitations=[],
    )
    fake_provider.set_canned_response(PatchProposal, repaired_patch)

    # Sandbox runner: First run fails, second run passes
    attempt = 0

    class DualOutcomeSandbox(FakeSandboxRunner):
        def run(self, command_args, workspace_path, timeout_sec=60):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                return SandboxResult(
                    status=CheckStatus.FAILED,
                    exit_code=1,
                    duration_ms=20,
                    stdout="",
                    stderr="SyntaxError: unexpected EOF while parsing",
                    executed_in_sandbox=True,
                )
            return SandboxResult(
                status=CheckStatus.PASSED,
                exit_code=0,
                duration_ms=20,
                stdout="Compiled ok",
                stderr="",
                executed_in_sandbox=True,
            )

    sandbox = DualOutcomeSandbox()
    arun3, vrun, report = agent_service.verify_and_repair(
        task_id=task.id,
        run_id=arun2.id,
        repo_path=repo_dir,
        sandbox_runner=sandbox,
        check_commands=[["python", "-m", "py_compile", "math_ops.py"]],
    )

    assert arun3.status == AgentRunStatus.VERIFICATION_PASSED
    assert arun3.attempt_number == 2
    assert vrun.status.value == "COMPLETED"


def test_agent_repair_budget_exhaustion(workflow_test_env):
    """Verify that when repair attempts reach max_repair_attempts, BUDGET_EXHAUSTED is recorded."""
    repo_dir = workflow_test_env["repo_dir"]
    base_sha = workflow_test_env["base_sha"]
    task = workflow_test_env["task"]
    service = workflow_test_env["service"]

    diff = """--- a/math_ops.py
+++ b/math_ops.py
@@ -1,2 +1,3 @@
 def add(a, b):
     return a + b
+# broken
"""
    fake_provider = FakeLLMProvider()
    canned_plan = TaskPlan(
        task_id=task.id,
        objective="Obj",
        ordered_steps=["Step 1"],
        test_strategy="strat",
    )
    fake_provider.set_canned_response(TaskPlan, canned_plan)

    patch_prop = PatchProposal(
        task_id=task.id,
        base_commit_sha=base_sha,
        summary="Broken",
        unified_diff=diff,
        changed_paths=["math_ops.py"],
        intended_behaviour="B",
    )
    fake_provider.set_canned_response(PatchProposal, patch_prop)

    settings = AgentSettings(agent_max_repair_attempts=2)
    agent_service = AgentService(service=service, settings=settings, provider=fake_provider)

    arun, _ = agent_service.plan_task(task_id=task.id, repo_path=repo_dir)
    agent_service.approve_plan(task_id=task.id, run_id=arun.id)
    arun2, _ = agent_service.propose_patch(task_id=task.id, run_id=arun.id, repo_path=repo_dir)

    # Sandbox runner always fails
    always_fail_sandbox = FakeSandboxRunner(
        default_status=CheckStatus.FAILED,
        default_exit_code=1,
        default_stderr="Compilation error",
    )

    # First verify_and_repair consumes attempt 2 and fails
    arun3, vrun, report = agent_service.verify_and_repair(
        task_id=task.id,
        run_id=arun2.id,
        repo_path=repo_dir,
        sandbox_runner=always_fail_sandbox,
        check_commands=[["python", "-m", "py_compile", "math_ops.py"]],
    )

    # Since it failed attempt 2 (which is the max), subsequent call must be BUDGET_EXHAUSTED
    arun4, _, _ = agent_service.verify_and_repair(
        task_id=task.id,
        run_id=arun3.id,
        repo_path=repo_dir,
        sandbox_runner=always_fail_sandbox,
        check_commands=[["python", "-m", "py_compile", "math_ops.py"]],
    )

    assert arun4.status == AgentRunStatus.BUDGET_EXHAUSTED
    assert arun4.failure_category == "MAX_REPAIR_ATTEMPTS_EXCEEDED"
