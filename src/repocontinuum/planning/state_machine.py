"""Task lifecycle state machine enforcing valid transitions and dependency gates."""

from __future__ import annotations

from typing import Dict, List, Set
from repocontinuum.domain.planning import TaskStatus


class StateTransitionError(Exception):
    """Base exception for invalid task lifecycle state transitions."""


class InvalidStateTransitionError(StateTransitionError):
    """Raised when a task attempts an unauthorized or illegal state transition."""

    def __init__(self, current_state: TaskStatus, target_state: TaskStatus, reason: str):
        self.current_state = current_state
        self.target_state = target_state
        self.reason = reason
        super().__init__(
            f"Cannot transition task from {current_state.value} to {target_state.value}: {reason}"
        )


class BlockedTaskTransitionError(StateTransitionError):
    """Raised when an attempt is made to start a blocked task with unmet dependencies."""

    def __init__(self, task_id: str, unmet_predecessors: List[str]):
        self.task_id = task_id
        self.unmet_predecessors = unmet_predecessors
        pre_list = ", ".join(unmet_predecessors)
        super().__init__(
            f"Task '{task_id}' cannot start: unmet dependencies on [{pre_list}]."
        )


class TaskStateMachine:
    """Enforces legal lifecycle transitions for maintenance tasks."""

    LEGAL_TRANSITIONS: Dict[TaskStatus, Set[TaskStatus]] = {
        TaskStatus.CREATED: {
            TaskStatus.READY,
            TaskStatus.PLANNED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.BLOCKED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.READY: {
            TaskStatus.PLANNED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.BLOCKED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.PLANNED: {
            TaskStatus.IN_PROGRESS,
            TaskStatus.BLOCKED,
            TaskStatus.READY,
            TaskStatus.CANCELLED,
        },
        TaskStatus.BLOCKED: {
            TaskStatus.READY,
            TaskStatus.IN_PROGRESS,  # Only permitted if explicitly waived
            TaskStatus.CANCELLED,
        },
        TaskStatus.IN_PROGRESS: {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.FAILED: {
            TaskStatus.READY,
            TaskStatus.IN_PROGRESS,
            TaskStatus.CANCELLED,
        },
        TaskStatus.COMPLETED: {
            TaskStatus.READY,  # Can reopen if regression detected in later tasks
            TaskStatus.CANCELLED,
        },
        TaskStatus.CANCELLED: set(),
    }

    @classmethod
    def validate_transition(
        cls,
        task_id: str,
        current_status: TaskStatus,
        target_status: TaskStatus,
        unmet_dependencies: List[str],
        explicit_waiver: bool = False,
    ) -> None:
        """Validate if a transition is legal according to rules and dependency status."""
        if current_status == target_status:
            return  # Idempotent no-op

        allowed_targets = cls.LEGAL_TRANSITIONS.get(current_status, set())
        if target_status not in allowed_targets:
            raise InvalidStateTransitionError(
                current_state=current_status,
                target_state=target_status,
                reason=f"Transition from {current_status.value} to {target_status.value} is not permitted by lifecycle rules.",
            )

        # Enforce prerequisite dependency gate for IN_PROGRESS
        if target_status == TaskStatus.IN_PROGRESS:
            if unmet_dependencies and not explicit_waiver:
                raise BlockedTaskTransitionError(task_id, unmet_dependencies)
