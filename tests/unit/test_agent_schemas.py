"""Unit tests for structured Pydantic response schemas."""

import pytest
from pydantic import ValidationError

from repocontinuum.agent.schemas.issue_analysis import IssueAnalysis
from repocontinuum.agent.schemas.patch_proposal import PatchProposal
from repocontinuum.agent.schemas.task_plan import TaskPlan
from repocontinuum.agent.schemas.tool_intent import ToolIntent


def test_issue_analysis_validation_success():
    """Verify IssueAnalysis schema with valid fields."""
    analysis = IssueAnalysis(
        problem_summary="Division by zero in calculate_ratio()",
        observed_behaviour="ZeroDivisionError raised when total is 0",
        expected_behaviour="Returns 0.0 or raises custom ValidationError",
        acceptance_criteria=["Zero denominator returns 0.0", "Existing ratios unchanged"],
        ambiguous_requirements=[],
        likely_affected_files=["src/math/ratio.py"],
        likely_affected_symbols=["calculate_ratio"],
        relevant_tests=["tests/test_ratio.py::test_calculate_ratio_zero"],
        dependency_candidates=[],
        risk_level="low",
        assumptions=["0 is a valid denominator mapping to 0.0"],
        confidence=0.92,
    )
    assert analysis.problem_summary.startswith("Division by zero")
    assert analysis.confidence == 0.92
    assert analysis.risk_level == "low"


def test_issue_analysis_validation_failure_on_invalid_confidence():
    """Verify IssueAnalysis rejects confidence out of bounds [0.0, 1.0]."""
    with pytest.raises(ValidationError):
        IssueAnalysis(
            problem_summary="Summary",
            observed_behaviour="Observed",
            expected_behaviour="Expected",
            confidence=1.5,  # Invalid
        )


def test_task_plan_validation():
    """Verify TaskPlan schema requirements."""
    plan = TaskPlan(
        task_id="tsk-100",
        objective="Implement safe zero denominator check",
        ordered_steps=[
            "Inspect ratio.py",
            "Add if denominator == 0: return 0.0",
            "Run pytest tests/test_ratio.py",
        ],
        required_predecessors=[],
        affected_files=["src/math/ratio.py"],
        affected_symbols=["calculate_ratio"],
        test_strategy="Run existing tests plus new zero denominator test",
        active_obligations=["ob-ratio-accuracy"],
        risks=["Callers expecting exception might need update"],
        assumptions=[],
        unresolved_questions=[],
        expected_completion_conditions=["test_calculate_ratio_zero passes"],
    )
    assert len(plan.ordered_steps) == 3
    assert plan.task_id == "tsk-100"


def test_tool_intent_schema():
    """Verify ToolIntent schema structure."""
    intent = ToolIntent(
        tool_name="get_file_content",
        arguments={"file_path": "src/main.py", "start_line": 1, "end_line": 20},
        purpose="Inspect imports",
        expected_result="List of imports",
    )
    assert intent.tool_name == "get_file_content"
    assert intent.arguments["file_path"] == "src/main.py"


def test_patch_proposal_schema():
    """Verify PatchProposal schema structure."""
    diff = """--- a/ratio.py
+++ b/ratio.py
@@ -1,2 +1,4 @@
 def calculate_ratio(a, b):
+    if b == 0:
+        return 0.0
     return a / b
"""
    proposal = PatchProposal(
        task_id="tsk-100",
        base_commit_sha="a1b2c3d4e5f67890123456789012345678901234",
        summary="Safely handle zero denominator",
        unified_diff=diff,
        changed_paths=["ratio.py"],
        intended_behaviour="Return 0.0 on zero division",
        affected_obligations=["ob-ratio-accuracy"],
        verification_plan=["python -m pytest tests/test_ratio.py"],
        assumptions=[],
        known_limitations=["Assumes float return"],
    )
    assert proposal.task_id == "tsk-100"
    assert len(proposal.changed_paths) == 1
