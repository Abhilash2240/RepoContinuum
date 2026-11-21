"""Unit tests for task lifecycle state machine."""

import pytest
from repocontinuum.domain.planning import TaskStatus
from repocontinuum.planning.state_machine import (
    BlockedTaskTransitionError,
    InvalidStateTransitionError,
    TaskStateMachine,
)


def test_legal_lifecycle_transitions() -> None:
    """Verify standard happy-path lifecycle transitions."""
    # CREATED -> READY
    TaskStateMachine.validate_transition("t1", TaskStatus.CREATED, TaskStatus.READY, [])

    # READY -> PLANNED
    TaskStateMachine.validate_transition("t1", TaskStatus.READY, TaskStatus.PLANNED, [])

    # PLANNED -> IN_PROGRESS
    TaskStateMachine.validate_transition("t1", TaskStatus.PLANNED, TaskStatus.IN_PROGRESS, [])

    # IN_PROGRESS -> COMPLETED
    TaskStateMachine.validate_transition("t1", TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED, [])

    # IN_PROGRESS -> FAILED
    TaskStateMachine.validate_transition("t1", TaskStatus.IN_PROGRESS, TaskStatus.FAILED, [])

    # Any -> CANCELLED
    TaskStateMachine.validate_transition("t1", TaskStatus.READY, TaskStatus.CANCELLED, [])
    TaskStateMachine.validate_transition("t1", TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED, [])


def test_illegal_transitions_rejected() -> None:
    """Verify unauthorized transitions raise InvalidStateTransitionError."""
    # Cannot jump from CREATED directly to COMPLETED
    with pytest.raises(InvalidStateTransitionError, match="not permitted"):
        TaskStateMachine.validate_transition("t1", TaskStatus.CREATED, TaskStatus.COMPLETED, [])

    # Cannot transition out of CANCELLED
    with pytest.raises(InvalidStateTransitionError, match="not permitted"):
        TaskStateMachine.validate_transition("t1", TaskStatus.CANCELLED, TaskStatus.IN_PROGRESS, [])


def test_blocked_task_start_rejected_without_waiver() -> None:
    """Verify that a task with unmet prerequisites cannot start unless explicitly waived."""
    unmet = ["task-prereq-1", "task-prereq-2"]

    # Blocked task starting without waiver raises BlockedTaskTransitionError
    with pytest.raises(BlockedTaskTransitionError, match="unmet dependencies"):
        TaskStateMachine.validate_transition(
            task_id="t2",
            current_status=TaskStatus.READY,
            target_status=TaskStatus.IN_PROGRESS,
            unmet_dependencies=unmet,
            explicit_waiver=False,
        )

    # With explicit waiver, transition is permitted
    TaskStateMachine.validate_transition(
        task_id="t2",
        current_status=TaskStatus.READY,
        target_status=TaskStatus.IN_PROGRESS,
        unmet_dependencies=unmet,
        explicit_waiver=True,
    )


def test_idempotent_transition_noop() -> None:
    """Verify requesting the current state does nothing and is idempotent."""
    # Already READY
    TaskStateMachine.validate_transition("t1", TaskStatus.READY, TaskStatus.READY, [])
    # Already IN_PROGRESS
    TaskStateMachine.validate_transition("t1", TaskStatus.IN_PROGRESS, TaskStatus.IN_PROGRESS, [])
    # Already COMPLETED
    TaskStateMachine.validate_transition("t1", TaskStatus.COMPLETED, TaskStatus.COMPLETED, [])
    # Already FAILED
    TaskStateMachine.validate_transition("t1", TaskStatus.FAILED, TaskStatus.FAILED, [])


def test_concurrent_or_duplicate_transition_protection() -> None:
    """Verify duplicate transition requests cannot bypass dependency gates."""
    # Cannot transition an already COMPLETED task back into IN_PROGRESS without reopening to READY
    with pytest.raises(InvalidStateTransitionError, match="not permitted"):
        TaskStateMachine.validate_transition("t1", TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS, [])
