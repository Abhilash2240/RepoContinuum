"""Dependency graph modeling, cycle detection, and stable topological sorting."""

from __future__ import annotations

from typing import Dict, List, Set, Tuple
import networkx as nx

from repocontinuum.domain.planning import (
    DAGValidationReport,
    MaintenanceTask,
    TaskDependency,
    TaskStatus,
)


class DependencyGraphError(Exception):
    """Base exception for dependency graph validation errors."""


class CycleDetectedError(DependencyGraphError):
    """Raised when a dependency cycle is discovered."""

    def __init__(self, cycle_path: List[str]):
        self.cycle_path = cycle_path
        path_str = " -> ".join(cycle_path)
        super().__init__(f"Cycle detected in task dependencies: {path_str}")


class MissingDependencyError(DependencyGraphError):
    """Raised when a dependency references an unknown task."""

    def __init__(self, missing_task_ids: List[str]):
        self.missing_task_ids = missing_task_ids
        super().__init__(f"Dependencies reference missing tasks: {', '.join(missing_task_ids)}")


class DependencyGraph:
    """Directed Acyclic Graph manager for task dependencies."""

    def __init__(self, tasks: List[MaintenanceTask], dependencies: List[TaskDependency]):
        self.tasks_by_id: Dict[str, MaintenanceTask] = {t.id: t for t in tasks}
        self.dependencies = dependencies
        self.graph = nx.DiGraph()

        # Add all known task nodes
        for task_id in self.tasks_by_id:
            self.graph.add_node(task_id)

        # Add edges for all valid dependencies
        for dep in self.dependencies:
            if dep.predecessor_task_id in self.tasks_by_id and dep.successor_task_id in self.tasks_by_id:
                self.graph.add_edge(dep.predecessor_task_id, dep.successor_task_id)

    def validate(self, chain_id: str = "") -> DAGValidationReport:
        """Validate DAG invariants, detect cycles, find missing dependencies, and compute plan."""
        missing: List[str] = []

        # Check for edges referencing unknown tasks
        for dep in self.dependencies:
            if dep.predecessor_task_id not in self.tasks_by_id:
                missing.append(f"Predecessor '{dep.predecessor_task_id}' not found")
            if dep.successor_task_id not in self.tasks_by_id:
                missing.append(f"Successor '{dep.successor_task_id}' not found")

        if missing:
            return DAGValidationReport(
                chain_id=chain_id,
                is_valid=False,
                has_cycles=False,
                cycle_paths=[],
                missing_dependencies=missing,
                topological_order=[],
                blocked_tasks={},
                explanation=f"Chain validation failed due to missing task references: {'; '.join(missing)}",
            )

        # Cycle detection
        try:
            cycles = list(nx.simple_cycles(self.graph))
        except Exception:
            cycles = []

        if cycles:
            formatted_cycles = [cycle + [cycle[0]] for cycle in cycles]
            cycle_desc = " | ".join(" -> ".join(c) for c in formatted_cycles)
            return DAGValidationReport(
                chain_id=chain_id,
                is_valid=False,
                has_cycles=True,
                cycle_paths=formatted_cycles,
                missing_dependencies=[],
                topological_order=[],
                blocked_tasks={},
                explanation=f"Chain contains circular dependencies: {cycle_desc}",
            )

        # Stable topological ordering with deterministic tie-breaking
        # Sort by (order_index, task_id)
        def sort_key(node_id: str) -> Tuple[int, str]:
            task = self.tasks_by_id[node_id]
            return (task.order_index, task.id)

        try:
            topological_order = list(nx.lexicographical_topological_sort(self.graph, key=sort_key))
        except Exception as e:
            # Fallback to standard topological sort if lexicographical fails
            topological_order = list(nx.topological_sort(self.graph))

        # Determine blocked tasks
        blocked_tasks: Dict[str, List[str]] = {}
        for task_id in topological_order:
            predecessors = list(self.graph.predecessors(task_id))
            uncompleted = [
                pred_id
                for pred_id in predecessors
                if self.tasks_by_id[pred_id].status != TaskStatus.COMPLETED
            ]
            if uncompleted:
                blocked_tasks[task_id] = uncompleted

        explanation = (
            f"Chain is a valid DAG with {len(topological_order)} tasks. "
            f"{len(blocked_tasks)} tasks currently have unmet dependencies."
        )

        return DAGValidationReport(
            chain_id=chain_id,
            is_valid=True,
            has_cycles=False,
            cycle_paths=[],
            missing_dependencies=[],
            topological_order=topological_order,
            blocked_tasks=blocked_tasks,
            explanation=explanation,
        )

    def get_predecessors(self, task_id: str) -> List[str]:
        """Return list of predecessor task IDs that must complete before this task."""
        if not self.graph.has_node(task_id):
            return []
        return list(self.graph.predecessors(task_id))

    def get_successors(self, task_id: str) -> List[str]:
        """Return list of successor task IDs that depend on this task."""
        if not self.graph.has_node(task_id):
            return []
        return list(self.graph.successors(task_id))

    def is_task_blocked(self, task_id: str) -> Tuple[bool, List[str]]:
        """Check if a task is blocked and return uncompleted predecessor IDs."""
        predecessors = self.get_predecessors(task_id)
        unmet = [
            pred_id
            for pred_id in predecessors
            if pred_id in self.tasks_by_id and self.tasks_by_id[pred_id].status != TaskStatus.COMPLETED
        ]
        return (len(unmet) > 0, unmet)
