"""Unit tests for benchmark manifest parsing and metric formulas."""

import pytest
from pathlib import Path
from benchmarks.evaluator import BenchmarkEvaluator, MetricSummary, TaskResult


@pytest.fixture
def evaluator():
    root = Path(__file__).resolve().parent.parent.parent
    manifest_path = root / "benchmarks" / "manifest.yaml"
    return BenchmarkEvaluator(manifest_path)


def test_manifest_loads_and_validates(evaluator):
    """Verify benchmark manifest contains 10 chains and required fields."""
    chains = evaluator.manifest.get("chains", [])
    assert len(chains) == 10

    for chn in chains:
        assert "chain_id" in chn
        assert "base_commit_sha" in chn
        assert "tasks" in chn
        assert len(chn["tasks"]) >= 2
        for t in chn["tasks"]:
            assert "task_id" in t
            assert "acceptance_criteria" in t
            assert "impacted_test_labels" in t


def test_metric_formula_calculations(evaluator):
    """Test mathematical formulas for all 12 benchmark metrics."""
    # Construct synthetic task results:
    # 2 chains, 4 tasks total:
    # Task 1 (chain 1): passed, 0 regressions, 0 rechecked, 2/2 reqs, 2 impacted / 2 selected
    # Task 2 (chain 1): passed, 0 regressions, 1 rechecked, 2/2 reqs, 1 impacted / 2 selected
    # Task 3 (chain 2): passed, 1 regression, 1 rechecked, 1/2 reqs, 1 impacted / 1 selected
    # Task 4 (chain 2): failed, 0 regressions, 2 rechecked, 0/2 reqs, 1 impacted / 2 selected
    tasks = [
        TaskResult(
            task_id="t1",
            chain_id="c1",
            baseline_id="test",
            success=True,
            regressed_earlier_obligations=0,
            earlier_obligations_rechecked=0,
            active_requirements_passing=2,
            active_requirements_total=2,
            impacted_tests_selected=2,
            total_tests_selected=2,
            total_impacted_tests=2,
            patch_accepted=True,
            repair_attempts=0,
            latency_seconds=10.0,
            cost_usd=0.01,
            status="PASSED",
        ),
        TaskResult(
            task_id="t2",
            chain_id="c1",
            baseline_id="test",
            success=True,
            regressed_earlier_obligations=0,
            earlier_obligations_rechecked=1,
            active_requirements_passing=2,
            active_requirements_total=2,
            impacted_tests_selected=1,
            total_tests_selected=2,
            total_impacted_tests=1,
            patch_accepted=True,
            repair_attempts=1,
            latency_seconds=15.0,
            cost_usd=0.015,
            status="PASSED",
        ),
        TaskResult(
            task_id="t3",
            chain_id="c2",
            baseline_id="test",
            success=False,
            regressed_earlier_obligations=1,
            earlier_obligations_rechecked=1,
            active_requirements_passing=1,
            active_requirements_total=2,
            impacted_tests_selected=1,
            total_tests_selected=1,
            total_impacted_tests=1,
            patch_accepted=False,
            repair_attempts=0,
            latency_seconds=8.0,
            cost_usd=0.008,
            status="REGRESSION_DETECTED",
        ),
        TaskResult(
            task_id="t4",
            chain_id="c2",
            baseline_id="test",
            success=False,
            regressed_earlier_obligations=0,
            earlier_obligations_rechecked=2,
            active_requirements_passing=0,
            active_requirements_total=2,
            impacted_tests_selected=1,
            total_tests_selected=2,
            total_impacted_tests=1,
            patch_accepted=False,
            repair_attempts=2,
            latency_seconds=20.0,
            cost_usd=0.02,
            status="FAILED",
        ),
    ]

    metrics = evaluator._calculate_metrics(tasks, chains_count=2, completed_chains=1)

    # 1. Task success rate: 2 / 4 = 0.50
    assert metrics["task_success_rate"].value == 0.50
    assert metrics["task_success_rate"].numerator == 2
    assert metrics["task_success_rate"].denominator == 4

    # 2. Chain completion rate: 1 / 2 = 0.50
    assert metrics["task_chain_completion_rate"].value == 0.50
    assert metrics["task_chain_completion_rate"].numerator == 1
    assert metrics["task_chain_completion_rate"].denominator == 2

    # 3. Regression rate: 1 / (0+1+1+2) = 1 / 4 = 0.25
    assert metrics["regression_rate"].value == 0.25
    assert metrics["regression_rate"].numerator == 1
    assert metrics["regression_rate"].denominator == 4

    # 4. Regression-free chain rate: c1 has 0 regressions, c2 has 1 -> 1 / 2 = 0.50
    assert metrics["regression_free_chain_rate"].value == 0.50
    assert metrics["regression_free_chain_rate"].numerator == 1
    assert metrics["regression_free_chain_rate"].denominator == 2

    # 5. Retained functionality: (4 - 1) / 4 = 3 / 4 = 0.75
    assert metrics["retained_functionality_at_checkpoint"].value == 0.75
    assert metrics["retained_functionality_at_checkpoint"].numerator == 3

    # 6. Conformance to active requirements: (2+2+1+0) / (2+2+2+2) = 5 / 8 = 0.625
    assert metrics["conformance_to_active_requirements"].value == 0.625
    assert metrics["conformance_to_active_requirements"].numerator == 5
    assert metrics["conformance_to_active_requirements"].denominator == 8

    # 7. Test selection precision: (2+1+1+1) / (2+2+1+2) = 5 / 7 = 0.7143
    assert metrics["test_selection_precision"].value == 0.7143

    # 8. Test selection recall: (2+1+1+1) / (2+1+1+1) = 5 / 5 = 1.00
    assert metrics["test_selection_recall"].value == 1.00

    # 9. Patch acceptance: 2 / 4 = 0.50
    assert metrics["patch_acceptance_rate"].value == 0.50

    # 10. Repair attempts avg: (0+1+0+2) / 4 = 3 / 4 = 0.75
    assert metrics["repair_attempts_avg"].value == 0.75

    # 11. Latency: sorted [8.0, 10.0, 15.0, 20.0] -> median 15.0
    assert metrics["median_latency_seconds"].value == 15.0
    assert metrics["p95_latency_seconds"].value == 20.0

    # 12. Cost per successful task: (0.01 + 0.015 + 0.008 + 0.02) / 2 = 0.053 / 2 = 0.0265
    assert metrics["cost_per_successful_task"].value == 0.0265
