"""Unit tests for dependency graph, cycle detection, and stable topological sorting."""

import pytest
from repocontinuum.domain.planning import MaintenanceTask, TaskDependency, TaskStatus
from repocontinuum.planning.dag import (
    CycleDetectedError,
    DependencyGraph,
)


def _make_task(task_id: str, order_index: int = 0, status: TaskStatus = TaskStatus.CREATED) -> MaintenanceTask:
    return MaintenanceTask(
        id=task_id,
        chain_id="chain-test",
        title=f"Task {task_id}",
        order_index=order_index,
        status=status,
    )


def test_simple_acyclic_dag_ordering() -> None:
    """Verify linear dependency A -> B -> C yields stable topological order [A, B, C]."""
    tasks = [_make_task("A", 1), _make_task("B", 2), _make_task("C", 3)]
    deps = [
        TaskDependency(id="d1", chain_id="chain-test", predecessor_task_id="A", successor_task_id="B"),
        TaskDependency(id="d2", chain_id="chain-test", predecessor_task_id="B", successor_task_id="C"),
    ]

    graph = DependencyGraph(tasks, deps)
    report = graph.validate("chain-test")

    assert report.is_valid is True
    assert report.has_cycles is False
    assert report.topological_order == ["A", "B", "C"]


def test_direct_cycle_detection() -> None:
    """Verify direct cycle A -> B -> A is detected and rejected."""
    tasks = [_make_task("A"), _make_task("B")]
    deps = [
        TaskDependency(id="d1", chain_id="chain-test", predecessor_task_id="A", successor_task_id="B"),
        TaskDependency(id="d2", chain_id="chain-test", predecessor_task_id="B", successor_task_id="A"),
    ]

    graph = DependencyGraph(tasks, deps)
    report = graph.validate("chain-test")

    assert report.is_valid is False
    assert report.has_cycles is True
    assert len(report.cycle_paths) > 0


def test_transitive_cycle_detection() -> None:
    """Verify transitive cycle A -> B -> C -> A is detected."""
    tasks = [_make_task("A"), _make_task("B"), _make_task("C")]
    deps = [
        TaskDependency(id="d1", chain_id="chain-test", predecessor_task_id="A", successor_task_id="B"),
        TaskDependency(id="d2", chain_id="chain-test", predecessor_task_id="B", successor_task_id="C"),
        TaskDependency(id="d3", chain_id="chain-test", predecessor_task_id="C", successor_task_id="A"),
    ]

    graph = DependencyGraph(tasks, deps)
    report = graph.validate("chain-test")

    assert report.is_valid is False
    assert report.has_cycles is True
    assert any("A" in c and "B" in c and "C" in c for c in report.cycle_paths)


def test_missing_dependency_rejection() -> None:
    """Verify dependency referencing an unregistered task is flagged as invalid."""
    tasks = [_make_task("A")]
    deps = [
        TaskDependency(id="d1", chain_id="chain-test", predecessor_task_id="A", successor_task_id="UNKNOWN_TASK"),
    ]

    graph = DependencyGraph(tasks, deps)
    report = graph.validate("chain-test")

    assert report.is_valid is False
    assert len(report.missing_dependencies) == 1
    assert "UNKNOWN_TASK" in report.missing_dependencies[0]


def test_stable_deterministic_ordering_for_independent_tasks() -> None:
    """Verify lexicographical tie-breaking produces deterministic topological order."""
    # Tasks B and A both have no dependencies; order_index and ID tie-breaks
    tasks = [_make_task("task-B", order_index=1), _make_task("task-A", order_index=1)]
    deps = []

    graph1 = DependencyGraph(tasks, deps)
    report1 = graph1.validate("chain-test")

    # Invert input order
    graph2 = DependencyGraph(list(reversed(tasks)), deps)
    report2 = graph2.validate("chain-test")

    assert report1.topological_order == report2.topological_order
    assert report1.topological_order == ["task-A", "task-B"]


def test_blocked_task_identification() -> None:
    """Verify that tasks with uncompleted predecessors are correctly marked blocked."""
    tasks = [
        _make_task("A", status=TaskStatus.IN_PROGRESS),
        _make_task("B", status=TaskStatus.CREATED),
    ]
    deps = [
        TaskDependency(id="d1", chain_id="chain-test", predecessor_task_id="A", successor_task_id="B"),
    ]

    graph = DependencyGraph(tasks, deps)
    report = graph.validate("chain-test")

    assert report.is_valid is True
    assert "B" in report.blocked_tasks
    assert report.blocked_tasks["B"] == ["A"]
